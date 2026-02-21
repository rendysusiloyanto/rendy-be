import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.database import Base


class ProxmoxNode(Base):
    __tablename__ = "proxmox_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    host = Column(String(255), nullable=False)
    user = Column(String(100), nullable=False, default="root")
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
