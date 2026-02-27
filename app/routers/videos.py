"""
Video upload (admin) and streaming (premium only).
Stream requires Bearer token + premium user so links are not shareable.
Supports raw file stream (Range), HLS, and DASH (FFmpeg-converted). See:
https://dev.to/ethand91/flask-video-streaming-app-tutorial-1dm3
"""
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.responses import Response, StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.services.video_upload import save_video_upload, video_upload_dir, video_streams_dir, CHUNK_SIZE
from app.services.ffmpeg_streams import ensure_hls_dash_for_video

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _upload_dir() -> Path:
    return video_upload_dir()


def _streams_dir() -> Path:
    return video_streams_dir()


def _ensure_upload_dir():
    _upload_dir().mkdir(parents=True, exist_ok=True)


def _safe_stream_file_path(video_id: str, format_type: str, relative_path: str) -> Path | None:
    """Resolve path under streams_dir/video_id/format_type. Return None if invalid (path traversal)."""
    base = (_streams_dir() / video_id / format_type).resolve()
    if not base.is_dir():
        return None
    try:
        full = (base / relative_path).resolve()
        full.relative_to(base)  # raises ValueError if path escaped
    except (ValueError, OSError):
        return None
    if not full.is_file():
        return None
    return full


def _media_type_for_filename(filename: str) -> str:
    """Return media type for HLS/DASH segment and playlist files."""
    lower = filename.lower()
    if lower.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if lower.endswith(".ts"):
        return "video/MP2T"
    if lower.endswith(".m4s") or lower.endswith(".mpd"):
        return "application/dash+xml" if lower.endswith(".mpd") else "video/iso.segment"
    return "application/octet-stream"


def _stream_file_range(path: Path, request: Request, content_type: str):
    """Handle Range request for video streaming. Returns Response with 206 or 200."""
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        # No range: return full file (could be heavy for 16min video; browser usually sends range)
        def full_stream():
            with open(path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    yield chunk

        return StreamingResponse(
            full_stream(),
            status_code=200,
            media_type=content_type or "video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": "inline",
            },
        )

    # Parse Range: bytes=start-end
    m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not m:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
    start_s, end_s = m.groups()
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else file_size - 1
    if start > end or start < 0:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
    end = min(end, file_size - 1)
    length = end - start + 1

    def range_stream():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                read_size = min(CHUNK_SIZE, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        range_stream(),
        status_code=206,
        media_type=content_type or "video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Content-Disposition": "inline",
        },
    )


# ---------- Admin: upload & list ----------


@router.get("")
def list_videos(
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """Admin: list all uploaded videos (id, original_filename, created_at)."""
    items = db.query(Video).order_by(Video.created_at.desc()).all()
    return [
        {"id": v.id, "original_filename": v.original_filename, "content_type": v.content_type, "created_at": v.created_at.isoformat()}
        for v in items
    ]


@router.post("")
def upload_video(
    file: UploadFile = File(...),
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """
    Admin: upload a video file. Converts to HLS and DASH via FFmpeg (sync).
    Returns id and stream URLs. Premium users get stream with Bearer token.
    """
    video = save_video_upload(file, db)
    db.commit()
    db.refresh(video)

    source_path = _upload_dir() / video.path
    _streams_dir().mkdir(parents=True, exist_ok=True)
    hls_ok, dash_ok = ensure_hls_dash_for_video(video.id, source_path, _streams_dir())

    payload = {
        "id": video.id,
        "message": "Stream with Authorization: Bearer <token> (premium only).",
        "hls_ready": hls_ok,
    }
    if hls_ok:
        payload["hls_url"] = f"/api/videos/stream/{video.id}/hls/playlist.m3u8"
    return payload


# ---------- Premium: get stream URL (no token; client must send Bearer) ----------


@router.get("/{video_id}/stream-url")
def get_stream_url(
    video_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Premium only: returns the stream URL. Client must call GET /api/videos/stream/{id}
    with Authorization: Bearer <token> to play (no shareable link).
    """
    if not user.is_premium:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium required to stream videos.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    path = _upload_dir() / video.path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found.")

    base = _streams_dir() / video_id
    hls_playlist = base / "hls" / "playlist.m3u8"

    payload = {"auth_required": True}
    if hls_playlist.is_file():
        payload["hls_url"] = f"/api/videos/stream/{video_id}/hls/playlist.m3u8"
    return payload


# ---------- HLS/DASH stream (Bearer + premium; must be before /stream/{video_id}) ----------


@router.get("/stream/{video_id}/hls/{path:path}")
def stream_hls(
    video_id: str,
    path: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve HLS playlist and segments. Premium only. Requires Authorization: Bearer."""
    if not user.is_premium:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium required to stream videos.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    file_path = _safe_stream_file_path(video_id, "hls", path)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HLS file not found.")
    return FileResponse(
        file_path,
        media_type=_media_type_for_filename(file_path.name),
        headers={"Content-Disposition": "inline"},
    )


@router.get("/stream/{video_id}/dash/{path:path}")
def stream_dash(
    video_id: str,
    path: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve DASH manifest and segments. Premium only. Requires Authorization: Bearer."""
    if not user.is_premium:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium required to stream videos.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    file_path = _safe_stream_file_path(video_id, "dash", path)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DASH file not found.")
    return FileResponse(
        file_path,
        media_type=_media_type_for_filename(file_path.name),
        headers={"Content-Disposition": "inline"},
    )


# ---------- Raw stream (Bearer + premium only; no query token) ----------


@router.get("/stream/{video_id}")
def stream_video(
    video_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream video. Requires Authorization: Bearer <jwt> and premium user.
    No shareable link; only the logged-in premium user can access.
    Supports Range requests for seeking. Content-Disposition: inline (play, not download).
    """
    if not user.is_premium:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium required to stream videos.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    path = _upload_dir() / video.path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found.")
    return _stream_file_range(path, request, video.content_type or "video/mp4")
