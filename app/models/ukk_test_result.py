import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from app.database import Base


class UKKTestResult(Base):
    """Successful UKK test result (for leaderboard). One entry per user (first completion)."""
    __tablename__ = "ukk_test_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    total_score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    grade = Column(String(5), nullable=False)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
