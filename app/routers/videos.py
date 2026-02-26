"""
Video upload (admin) and streaming (premium only).
Stream URL uses a short-lived token so <video src> can load without custom headers.
Range requests supported for seeking. Content-Disposition: inline to discourage download.
"""
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.services.video_upload import save_video_upload, video_upload_dir, CHUNK_SIZE

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _upload_dir() -> Path:
    return video_upload_dir()


def _ensure_upload_dir():
    _upload_dir().mkdir(parents=True, exist_ok=True)


def _create_stream_token(video_id: str) -> str:
    from app.services.video_upload import create_video_stream_token
    return create_video_stream_token(video_id)


def _decode_stream_token(token: str) -> str | None:
    """Return video_id if token valid, else None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "video_stream":
            return None
        return payload.get("video_id")
    except JWTError:
        return None


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
    Admin: upload a video file. Returns id and stream URL pattern.
    Frontend should call GET /api/videos/{id}/stream-url (with auth) to get a playable URL with token.
    """
    video = save_video_upload(file, db)
    db.commit()
    db.refresh(video)
    return {
        "id": video.id,
        "url": f"/api/videos/stream/{video.id}",
        "message": "Use GET /api/videos/{id}/stream-url with Bearer token (premium) to get a playable URL with token.",
    }


# ---------- Premium: get stream URL (with token) ----------


@router.get("/{video_id}/stream-url")
def get_stream_url(
    video_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Premium only: get a short-lived URL to stream the video (for use in <video src="...">).
    Token expires in 1 hour (configurable). Non-premium users get 403.
    """
    if not user.is_premium:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium required to stream videos.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    path = _upload_dir() / video.path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found.")
    token = _create_stream_token(video_id)
    url = f"/api/videos/stream/{video_id}?token={token}"
    return {"url": url, "expires_in_minutes": get_settings().video_stream_token_expire_minutes}


# ---------- Stream (token in query; no Bearer) ----------


@router.get("/stream/{video_id}")
def stream_video(
    video_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Stream video by token (from stream-url). No Bearer needed; token is in query.
    Supports Range requests for seeking. Content-Disposition: inline (play, not download).
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing stream token. Use GET /api/videos/{id}/stream-url with Bearer (premium).")
    decoded_id = _decode_stream_token(token)
    if not decoded_id or decoded_id != video_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired stream token.")
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    path = _upload_dir() / video.path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found.")
    return _stream_file_range(path, request, video.content_type or "video/mp4")
