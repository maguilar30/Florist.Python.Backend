from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiscountCode(Base):
    __tablename__ = "discount_codes"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_discount_codes_company_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_redemptions: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    redemptions: Mapped[list["DiscountRedemption"]] = relationship(back_populates="discount_code")


class DiscountRedemption(Base):
    __tablename__ = "discount_code_redemptions"
    __table_args__ = (
        UniqueConstraint("discount_code_id", "customer_email", name="uq_discount_redemptions_code_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    discount_code_id: Mapped[int] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discount_code: Mapped[DiscountCode] = relationship(back_populates="redemptions")
