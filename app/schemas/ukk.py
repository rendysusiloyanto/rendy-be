from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    full_name: str
    email: str
    total_score: int
    max_score: int
    percentage: float
    grade: str
    completed_at: str

    class Config:
        from_attributes = True


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
