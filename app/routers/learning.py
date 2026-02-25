from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin, BLACKLIST_MESSAGE
from app.database import get_db
from app.models.learning import Learning
from app.schemas.learning import LearningCreate, LearningUpdate, LearningResponse

router = APIRouter(prefix="/api/learning", tags=["learning"])

# Blacklisted boleh lihat list (thumbnail + title). Buka detail (video, deskripsi lengkap) diblokir.


@router.get("", response_model=list[LearningResponse])
def list_learnings(
    published_only: bool = True,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Daftar learning (harus login). Blacklisted tetap bisa lihat list (thumbnail + title)."""
    q = db.query(Learning).order_by(Learning.created_at.desc())
    if published_only:
        q = q.filter(Learning.is_published == True)
    items = q.all()
    return [
        LearningResponse(
            id=x.id,
            title=x.title,
            description=x.description,
            thumbnail=x.thumbnail,
            content=x.content,
            video_url=x.video_url,
            is_published=x.is_published,
            created_at=x.created_at.isoformat(),
            updated_at=x.updated_at.isoformat(),
        )
        for x in items
    ]


@router.get("/admin", response_model=list[LearningResponse])
def admin_list_learnings(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Admin: daftar semua learning (termasuk yang belum dipublikasi)."""
    items = db.query(Learning).order_by(Learning.created_at.desc()).all()
    return [
        LearningResponse(
            id=x.id,
            title=x.title,
            description=x.description,
            thumbnail=x.thumbnail,
            content=x.content,
            video_url=x.video_url,
            is_published=x.is_published,
            created_at=x.created_at.isoformat(),
            updated_at=x.updated_at.isoformat(),
        )
        for x in items
    ]


@router.get("/{learning_id}", response_model=LearningResponse)
def get_learning(
    learning_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Detail learning (harus login). User blacklisted tidak bisa buka detail (hanya bisa lihat list)."""
    if user.is_blacklisted:
        raise HTTPException(status_code=403, detail=BLACKLIST_MESSAGE)
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Learning tidak ditemukan")
    return LearningResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        thumbnail=item.thumbnail,
        content=item.content,
        video_url=item.video_url,
        is_published=item.is_published,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.post("", response_model=LearningResponse)
def create_learning(
    body: LearningCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    item = Learning(
        title=body.title,
        description=body.description,
        thumbnail=body.thumbnail,
        content=body.content,
        video_url=body.video_url,
        is_published=body.is_published,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return LearningResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        thumbnail=item.thumbnail,
        content=item.content,
        video_url=item.video_url,
        is_published=item.is_published,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.put("/{learning_id}", response_model=LearningResponse)
def update_learning(
    learning_id: str,
    body: LearningUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    item = db.query(Learning).filter(Learning.id == learning_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Learning tidak ditemukan")
    if body.title is not None:
        item.title = body.title
    if body.description is not None:
        item.description = body.description
    if body.thumbnail is not None:
        item.thumbnail = body.thumbnail
    if body.content is not None:
        item.content = body.content
    if body.video_url is not None:
        item.video_url = body.video_url
    if body.is_published is not None:
        item.is_published = body.is_published
    db.commit()
    db.refresh(item)
    return LearningResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        thumbnail=item.thumbnail,
        content=item.content,
        video_url=item.video_url,
        is_published=item.is_published,
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
        raise HTTPException(status_code=404, detail="Learning tidak ditemukan")
    db.delete(item)
    db.commit()
    return {"message": "Learning dihapus"}
