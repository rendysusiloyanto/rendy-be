from pydantic import BaseModel


class AnnouncementCreate(BaseModel):
    title: str
    content: str | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str | None
    attachment_filename: str | None
    has_attachment: bool = False
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
