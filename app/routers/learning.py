import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin, BLACKLIST_MESSAGE
from app.database import get_db
from app.models.learning import Learning
from app.models.user import User
from app.models.video import Video
from app.schemas.learning import LearningCreate, LearningUpdate, LearningListResponse, LearningResponse
from app.services.video_upload import save_video_upload, video_upload_dir

router = APIRouter(prefix="/api/learning", tags=["learning"])

# Thumbnail upload dir (relative to backend)
def _thumbnail_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "learning_thumbnails"

def _ensure_thumbnail_dir():
    _thumbnail_dir().mkdir(parents=True, exist_ok=True)

# Blacklisted users can see list (thumbnail + title). Opening detail (video, full description) is blocked.


@router.get("")
def list_learnings(
    published_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List learnings. video_url field is not sent at all for non-premium users."""
    q = db.query(Learning).order_by(Learning.created_at.desc())
    if published_only:
        q = q.filter(Learning.is_published == True)
    items = q.all()
    show_video = user.is_premium
    body = []
    for x in items:
        d = {
            "id": x.id,
            "title": x.title,
            "description": x.description,
            "thumbnail": f"/api/learning/{x.id}/thumbnail" if x.thumbnail_path else x.thumbnail,
            "is_published": x.is_published,
            "is_premium": x.is_premium,
            "created_at": x.created_at.isoformat(),
            "updated_at": x.updated_at.isoformat(),
        }
        if show_video:
            if x.video_id:
                d["video_id"] = x.video_id
                d["video_stream_url"] = f"/api/learning/{x.id}/video-stream-url"
            else:
                d["video_url"] = x.video_url
        body.append(d)
    return JSONResponse(content=body)


@router.get("/admin", response_model=list[LearningResponse])
def admin_list_learnings(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Admin: list all learnings (including unpublished)."""
    items = db.query(Learning).order_by(Learning.created_at.desc()).all()
    return [
        LearningResponse(
            id=x.id,
            title=x.title,
            description=x.description,
            thumbnail=f"/api/learning/{x.id}/thumbnail" if x.thumbnail_path else x.thumbnail,
            content=x.content,
            video_url=x.video_url,
            video_id=x.video_id,
            is_published=x.is_published,
            is_premium=x.is_premium,
            created_at=x.created_at.isoformat(),
            updated_at=x.updated_at.isoformat(),
        )
        for x in items
    ]


@router.get("/{learning_id}/thumbnail")
def get_learning_thumbnail(
    learning_id: str,
    db: Session = Depends(get_db),
):
    """Serve uploaded thumbnail image for a learning (public)."""
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item or not item.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    path = _thumbnail_dir() / item.thumbnail_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{learning_id}/video-stream-url")
def get_learning_video_stream_url(
    learning_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Premium only: returns stream URL. Client must call it with Authorization: Bearer (no shareable link)."""
    if not user.is_premium:
        raise HTTPException(status_code=403, detail="Premium required")
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item or not item.video_id:
        raise HTTPException(status_code=404, detail="No uploaded video for this learning")
    url = f"/api/videos/stream/{item.video_id}"
    return {"url": url, "auth_required": True}


@router.get("/{learning_id}")
def get_learning(
    learning_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Detail learning. video_url/video_stream_url only for premium."""
    if user.is_blacklisted:
        raise HTTPException(status_code=403, detail=BLACKLIST_MESSAGE)
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Learning not found")
    show_video = user.is_premium
    d = {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "thumbnail": f"/api/learning/{item.id}/thumbnail" if item.thumbnail_path else item.thumbnail,
        "content": item.content,
        "is_published": item.is_published,
        "is_premium": item.is_premium,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
    if show_video:
        if item.video_id:
            d["video_id"] = item.video_id
            d["video_stream_url"] = f"/api/learning/{item.id}/video-stream-url"
        else:
            d["video_url"] = item.video_url
    return JSONResponse(content=d)


@router.post("", response_model=LearningResponse)
def create_learning(
    title: str = Form(...),
    description: str | None = Form(None),
    content: str | None = Form(None),
    is_published: bool = Form(False),
    is_premium: bool = Form(False),
    thumbnail: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    thumbnail_url: str | None = Form(None),
    video_url: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """
    Create learning. Form: title (required), description, content, is_published, is_premium,
    thumbnail_url (external URL), video_url (external URL).
    Optional files: thumbnail (image), video (video file). Uploaded video is stream-only (premium).
    """
    item = Learning(
        title=title,
        description=(description or "").strip() or None,
        content=(content or "").strip() or None,
        thumbnail=(thumbnail_url or "").strip() or None,
        video_url=(video_url or "").strip() or None,
        is_published=is_published,
        is_premium=is_premium,
    )
    db.add(item)
    db.flush()
    if thumbnail and thumbnail.filename and thumbnail.content_type and thumbnail.content_type.startswith("image/"):
        _ensure_thumbnail_dir()
        path = _thumbnail_dir() / f"{item.id}.png"
        with path.open("wb") as f:
            shutil.copyfileobj(thumbnail.file, f)
        item.thumbnail_path = path.name
    if video and video.filename:
        vid = save_video_upload(video, db)
        db.flush()  # Ensure Video row is inserted before setting learning.video_id (FK)
        item.video_id = vid.id
    db.commit()
    db.refresh(item)
    return LearningResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        thumbnail=f"/api/learning/{item.id}/thumbnail" if item.thumbnail_path else item.thumbnail,
        content=item.content,
        video_url=item.video_url,
        video_id=item.video_id,
        is_published=item.is_published,
        is_premium=item.is_premium,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.put("/{learning_id}", response_model=LearningResponse)
def update_learning(
    learning_id: str,
    title: str | None = Form(None),
    description: str | None = Form(None),
    content: str | None = Form(None),
    is_published: bool | None = Form(None),
    is_premium: bool | None = Form(None),
    thumbnail_url: str | None = Form(None),
    video_url: str | None = Form(None),
    thumbnail: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Update learning. Form fields optional. Optional files: thumbnail, video (replaces uploaded video)."""
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Learning not found")
    if title is not None:
        item.title = title
    if description is not None:
        item.description = (description or "").strip() or None
    if content is not None:
        item.content = (content or "").strip() or None
    if thumbnail_url is not None:
        item.thumbnail = (thumbnail_url or "").strip() or None
    if video_url is not None:
        item.video_url = (video_url or "").strip() or None
        if video_url:
            item.video_id = None
    if is_published is not None:
        item.is_published = is_published
    if is_premium is not None:
        item.is_premium = is_premium
    if thumbnail and thumbnail.filename and thumbnail.content_type and thumbnail.content_type.startswith("image/"):
        _ensure_thumbnail_dir()
        path = _thumbnail_dir() / f"{item.id}.png"
        with path.open("wb") as f:
            shutil.copyfileobj(thumbnail.file, f)
        item.thumbnail_path = path.name
    if video and video.filename:
        vid = save_video_upload(video, db)
        db.flush()  # Ensure Video row is inserted before updating learning.video_id (FK)
        item.video_id = vid.id
        item.video_url = None
    db.commit()
    db.refresh(item)
    return LearningResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        thumbnail=f"/api/learning/{item.id}/thumbnail" if item.thumbnail_path else item.thumbnail,
        content=item.content,
        video_url=item.video_url,
        video_id=item.video_id,
        is_published=item.is_published,
        is_premium=item.is_premium,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.delete("/{learning_id}")
def delete_learning(
    learning_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Learning not found")
    db.delete(item)
    db.commit()
    return {"message": "Learning deleted"}
