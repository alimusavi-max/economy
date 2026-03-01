from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database.database import get_db
from database.models import Indicator, EconomicData

router = APIRouter(prefix="/api/data", tags=["Data API"])

# مدلی برای دریافت اطلاعات از فرانت‌اند هنگام تغییر زمان‌بندی
class UpdateIntervalRequest(BaseModel):
    update_interval_days: int

# ۱. مسیر دریافت لیست تمام نمادهای موجود (باید بالای مسیر /{symbol} باشد)
@router.get("/symbols/available")
async def get_available_symbols(db: AsyncSession = Depends(get_db)):
    """
    دریافت لیست تمام شاخص‌ها و نمادهای موجود در دیتابیس
    برای نمایش در فرانت‌اند (تنظیمات آپدیت و لیست کشویی)
    """
    result = await db.execute(select(Indicator).order_by(Indicator.name))
    indicators = result.scalars().all()
    
    return [
        {
            "id": ind.id,
            "symbol": ind.symbol,
            "name": ind.name,
            "source": ind.source,
            "frequency": ind.frequency,
            "update_interval_days": ind.update_interval_days,
            "last_updated": ind.last_updated
        }
        for ind in indicators
    ]

# ۲. مسیر جدید برای تنظیم بازه زمانی آپدیت از طریق پنل
@router.put("/symbols/{symbol}/interval")
async def update_symbol_interval(symbol: str, request: UpdateIntervalRequest, db: AsyncSession = Depends(get_db)):
    """
    تغییر بازه زمانی آپدیت یک نماد (مثلا از ۳۰ روز به ۱ روز)
    """
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")
        
    indicator.update_interval_days = request.update_interval_days
    db.add(indicator)
    await db.commit()
    
    return {"success": True, "message": f"بازه آپدیت نماد {symbol} به {request.update_interval_days} روز تغییر یافت."}

# ۳. مسیر دریافت دیتای نمودار (کد قبلی شما)
@router.get("/{symbol}")
async def get_economic_data(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    دریافت اطلاعات یک شاخص اقتصادی برای نمایش در نمودار فرانت‌اند
    """
    # ۱. پیدا کردن شناسنامه شاخص در دیتابیس
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        raise HTTPException(status_code=404, detail="شاخص مورد نظر در دیتابیس یافت نشد. ابتدا آن را Fetch کنید.")

    # ۲. استخراج تمام داده‌های زمانیِ مرتبط با این شاخص (مرتب شده بر اساس تاریخ)
    data_result = await db.execute(
        select(EconomicData)
        .where(EconomicData.indicator_id == indicator.id)
        .order_by(EconomicData.date.asc())
    )
    records = data_result.scalars().all()

    # ۳. فرمت کردن خروجی دقیقاً مطابق نیاز کتابخانه‌های رسم نمودار (مثل Recharts)
    chart_data = [{"date": str(r.date), "value": r.value} for r in records]

    return {
        "indicator": {
            "name": indicator.name,
            "symbol": indicator.symbol,
            "source": indicator.source
        },
        "total_records": len(chart_data),
        "data": chart_data
    }