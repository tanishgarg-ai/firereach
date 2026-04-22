import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from database import Base


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    icp = Column(String(500), nullable=False)
    sendMode = Column(String(50), default="auto", nullable=False)
    targetCompany = Column(String(255), nullable=True)
    testRecipientEmail = Column(String(255), nullable=True)
    result = Column(JSON, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="searchHistory")
