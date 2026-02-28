from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import ForeignKey, String, Date, Float, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# ==========================================
# ۱. جدول متادیتا (شناسنامه شاخص‌های اقتصادی)
# ==========================================
class Indicator(Base):
    __tablename__ = "indicators"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), unique=True, index=True) # مثلا IRNBCA یا CPIAUCSL
    name: Mapped[str] = mapped_column(String(255)) # مثلا Inflation Rate
    source: Mapped[str] = mapped_column(String(50)) # FRED, WorldBank, AlphaVantage
    frequency: Mapped[Optional[str]] = mapped_column(String(50)) # Daily, Monthly, Quarterly
    
    # ارتباط با جدول داده‌های زمانی
    data_points: Mapped[List["EconomicData"]] = relationship(back_populates="indicator")

# ==========================================
# ۲. جدول دیتای سری زمانی (قلب تپنده پروژه)
# ==========================================
class EconomicData(Base):
    __tablename__ = "economic_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float) # مقدار شاخص در آن تاریخ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    indicator: Mapped["Indicator"] = relationship(back_populates="data_points")

    # ایندکس ترکیبی: جستجوی همزمان روی شناسه و تاریخ را فوق‌العاده سریع می‌کند
    # همچنین جلوی ثبت داده تکراری برای یک روز را می‌گیرد
    __table_args__ = (
        Index('idx_indicator_date', 'indicator_id', 'date', unique=True),
    )

# ==========================================
# ۳. جدول قیمت دارایی‌ها (بورس، طلا، نفت و ...)
# ==========================================
class AssetMarketData(Base):
    __tablename__ = "asset_market_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True) # مثلا IBM یا AAPL
    date: Mapped[date] = mapped_column(Date, index=True)
    close_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[Optional[float]] = mapped_column(Float)
    
    __table_args__ = (
        Index('idx_asset_date', 'symbol', 'date', unique=True),
    )