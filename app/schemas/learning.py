from pydantic import BaseModel


class LearningCreate(BaseModel):
    title: str
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool = False


class LearningUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    content: str | None = None
    video_url: str | None = None
    is_published: bool | None = None


class LearningResponse(BaseModel):
    id: str
    title: str
    description: str | None
    thumbnail: str | None
    content: str | None
    video_url: str | None
    is_published: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
