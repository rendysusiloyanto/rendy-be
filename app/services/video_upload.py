"""Shared helpers for video upload and stream token (used by videos router and learning)."""
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import UploadFile, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.video import Video

VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
CHUNK_SIZE = 1024 * 1024  # 1 MB


def create_video_stream_token(video_id: str) -> str:
    """Short-lived JWT for video stream URL (no Bearer needed in <video src>)."""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.video_stream_token_expire_minutes)
    payload = {"video_id": video_id, "exp": expire, "type": "video_stream"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def video_upload_dir() -> Path:
    settings = get_settings()
    if settings.video_upload_dir:
        return Path(settings.video_upload_dir)
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "videos"


def save_video_upload(file: UploadFile, db: Session) -> Video:
    """Create a Video record and save file to disk. Caller must db.commit()."""
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in VIDEO_CONTENT_TYPES and not (file.filename or "").lower().endswith((".mp4", ".webm", ".ogg", ".mov")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a video (e.g. video/mp4). Allowed: mp4, webm, ogg, mov.",
        )
    video_upload_dir().mkdir(parents=True, exist_ok=True)
    video_id = str(uuid.uuid4())
    ext = Path(file.filename or "video").suffix or ".mp4"
    if len(ext) > 10:
        ext = ".mp4"
    path = video_upload_dir() / f"{video_id}{ext}"
    with path.open("wb") as f:
        while chunk := file.file.read(CHUNK_SIZE):
            f.write(chunk)
    video = Video(id=video_id, path=path.name, original_filename=file.filename, content_type=ct or "video/mp4")
    db.add(video)
    return video
