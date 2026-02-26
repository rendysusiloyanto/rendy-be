from pydantic import BaseModel


class LearningCreate(BaseModel):
    title: str
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool = False
    is_premium: bool = False


class LearningUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool | None = None
    is_premium: bool | None = None


class LearningListResponse(BaseModel):
    """Response for learning list (without is_published and content). Frontend: video_url only present if user is premium."""
    id: str
    title: str
    description: str | None
    thumbnail: str | None
    video_url: str | None = None
    is_premium: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class LearningDetailResponse(BaseModel):
    """Detail response for user (without is_published). video_url only present if user is premium."""
    id: str
    title: str
    description: str | None
    thumbnail: str | None
    content: str | None
    video_url: str | None = None
    is_premium: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class LearningResponse(BaseModel):
    id: str
    title: str
    description: str | None
    thumbnail: str | None
    content: str | None
    video_url: str | None
    video_id: str | None = None
    is_published: bool
    is_premium: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
