import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class PaymentSession(Base):
    __tablename__ = "payment_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    userName = Column(String(255), nullable=False)
    plan = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    expiresAt = Column(DateTime, nullable=False)
    paymentUrl = Column(String(1024), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    paidAt = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="paymentSessions")
