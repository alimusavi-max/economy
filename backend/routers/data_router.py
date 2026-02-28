from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from database.models import Indicator, EconomicData

router = APIRouter(prefix="/api/data", tags=["Data API"])

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