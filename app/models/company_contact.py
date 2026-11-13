from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True
    )
    heading: Mapped[str] = mapped_column(String(255), nullable=False, default="Visítanos o escríbenos")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    hours: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    instagram_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    facebook_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    whatsapp_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
