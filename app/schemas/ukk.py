from pydantic import BaseModel


class ProxmoxNodeCreate(BaseModel):
    host: str
    user: str = "root"
    password: str


class ProxmoxNodeResponse(BaseModel):
    id: str
    host: str
    user: str
    password: str  # tampilkan untuk admin (bisa diganti mask nanti)
    created_at: str

    class Config:
        from_attributes = True
