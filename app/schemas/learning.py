from pydantic import BaseModel


# variant: "introduction" = simple/nginx static; "full" = stream (FFmpeg HLS)
LEARNING_VARIANT_INTRODUCTION = "introduction"
LEARNING_VARIANT_FULL = "full"


class LearningCreate(BaseModel):
    title: str
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool = False
    is_premium: bool = False
    variant: str = LEARNING_VARIANT_INTRODUCTION


class LearningUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool | None = None
    is_premium: bool | None = None
    variant: str | None = None


class LearningListResponse(BaseModel):
    """Response for learning list (without is_published and content)."""
    id: str
    title: str
    thumbnail: str | None
    is_published: bool
    is_premium: bool
    variant: str
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
    variant: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
