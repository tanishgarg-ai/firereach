import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan = Column(String(50), default="FREE", nullable=False)
    monthlyCredits = Column(Integer, default=30, nullable=False)
    creditsRemaining = Column(Integer, default=30, nullable=False)
    nextResetAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    periodStart = Column(DateTime, default=datetime.utcnow, nullable=False)
    periodEnd = Column(DateTime, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscriptions")
