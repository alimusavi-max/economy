from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(50))
    frequency: Mapped[Optional[str]] = mapped_column(String(50))
    dbnomics_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    update_interval_days: Mapped[int] = mapped_column(Integer, default=30)
    last_updated: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    data_points: Mapped[List["EconomicData"]] = relationship(back_populates="indicator")


class EconomicData(Base):
    __tablename__ = "economic_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    indicator: Mapped["Indicator"] = relationship(back_populates="data_points")

    __table_args__ = (
        Index("idx_indicator_date", "indicator_id", "date", unique=True),
    )


class AssetMarketData(Base):
    __tablename__ = "asset_market_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    close_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_asset_date", "symbol", "date", unique=True),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dashboard_items: Mapped[List["UserDashboardItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserDashboardItem(Base):
    __tablename__ = "user_dashboard_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    indicator_symbol: Mapped[str] = mapped_column(String(50), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="dashboard_items")

    __table_args__ = (
        UniqueConstraint("user_id", "indicator_symbol", name="uq_user_dashboard_symbol"),
    )
