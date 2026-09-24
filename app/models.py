from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from app.database import Base

class Photo(Base):
    __tablename__ = "photos"

    id = Column(String(36), primary_key=True, index=True)
    original_name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_kb = Column(Float, nullable=False)
    target_size_kb = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_name": self.original_name,
            "filename": self.filename,
            "file_size_kb": round(self.file_size_kb, 2),
            "target_size_kb": self.target_size_kb,
            "width": self.width,
            "height": self.height,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

class BlockedIP(Base):
    __tablename__ = "blocked_ips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(64), unique=True, index=True, nullable=False)
    reason = Column(String(255), nullable=False)
    failed_attempts = Column(Integer, default=1)
    blocked_at = Column(DateTime, default=datetime.utcnow)
    blocked_until = Column(DateTime, nullable=True)
    is_permanent = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "reason": self.reason,
            "failed_attempts": self.failed_attempts,
            "blocked_at": self.blocked_at.strftime("%Y-%m-%d %H:%M:%S") if self.blocked_at else "",
            "blocked_until": self.blocked_until.strftime("%Y-%m-%d %H:%M:%S") if self.blocked_until else "Never",
            "is_permanent": self.is_permanent
        }

class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), nullable=False)
    details = Column(String(512), nullable=True)
    endpoint = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
