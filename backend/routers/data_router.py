from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from database.database import get_db
from database.models import EconomicData, Indicator

router = APIRouter(prefix="/api/data", tags=["Data API"])


class UpdateIntervalRequest(BaseModel):
    update_interval_days: int


@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    خلاصه مناسب داشبورد:
    - تعداد کل شاخص‌ها
    - تعداد شاخص‌های دارای داده
    - تعداد رکوردهای اقتصادی
    - تفکیک منبعی برای ویجت/کارت‌های داشبورد
    """
    total_indicators_q = await db.execute(select(func.count(Indicator.id)))
    total_indicators = total_indicators_q.scalar() or 0

    indicators_with_data_q = await db.execute(
        select(func.count(func.distinct(EconomicData.indicator_id)))
    )
    indicators_with_data = indicators_with_data_q.scalar() or 0

    total_points_q = await db.execute(select(func.count(EconomicData.id)))
    total_points = total_points_q.scalar() or 0

    by_source_q = await db.execute(
        select(
            Indicator.source,
            func.count(Indicator.id).label("indicator_count"),
            func.count(func.distinct(EconomicData.indicator_id)).label("with_data_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
        .group_by(Indicator.source)
        .order_by(Indicator.source.asc())
    )

    by_source = [
        {
            "source": row.source,
            "indicators": int(row.indicator_count or 0),
            "indicators_with_data": int(row.with_data_count or 0),
        }
        for row in by_source_q.all()
    ]

    return {
        "totals": {
            "indicators": int(total_indicators),
            "indicators_with_data": int(indicators_with_data),
            "economic_data_points": int(total_points),
        },
        "sources": by_source,
        "generated_at": date.today(),
    }


@router.get("/symbols/available")
async def get_available_symbols(
    db: AsyncSession = Depends(get_db),
    source: Optional[str] = Query(default=None, description="فیلتر منبع مثل FRED/IMF/OECD"),
    with_data_only: bool = Query(default=False, description="فقط شاخص‌هایی که دیتای زمانی دارند"),
    limit: int = Query(default=300, ge=1, le=2000),
):
    """
    دریافت لیست شاخص‌ها برای فرانت.
    خروجی غنی‌تر شده تا داشبورد بتواند وضعیت نمایش/فیلتر را بهتر مدیریت کند.
    """
    query = (
        select(
            Indicator.id,
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            Indicator.frequency,
            Indicator.update_interval_days,
            Indicator.last_updated,
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
    )

    if source:
        query = query.where(Indicator.source == source.upper())

    query = query.group_by(
        Indicator.id,
        Indicator.symbol,
        Indicator.name,
        Indicator.source,
        Indicator.frequency,
        Indicator.update_interval_days,
        Indicator.last_updated,
    )

    if with_data_only:
        query = query.having(func.count(EconomicData.id) > 0)

    query = query.order_by(Indicator.source.asc(), Indicator.name.asc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "name": row.name,
            "source": row.source,
            "frequency": row.frequency,
            "update_interval_days": row.update_interval_days,
            "last_updated": row.last_updated,
            "data_points_count": int(row.data_points_count or 0),
            "has_data": int(row.data_points_count or 0) > 0,
        }
        for row in rows
    ]


@router.put("/symbols/{symbol}/interval")
async def update_symbol_interval(symbol: str, request: UpdateIntervalRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()

    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")

    indicator.update_interval_days = request.update_interval_days
    db.add(indicator)
    await db.commit()

    return {"success": True, "message": f"بازه آپدیت نماد {symbol} به {request.update_interval_days} روز تغییر یافت."}


@router.get("/{symbol}")
async def get_economic_data(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()

    if not indicator:
        raise HTTPException(status_code=404, detail="شاخص مورد نظر در دیتابیس یافت نشد. ابتدا آن را Fetch کنید.")

    data_result = await db.execute(
        select(EconomicData)
        .where(EconomicData.indicator_id == indicator.id)
        .order_by(EconomicData.date.asc())
    )
    records = data_result.scalars().all()

    chart_data = [{"date": str(r.date), "value": r.value} for r in records]

    return {
        "indicator": {
            "name": indicator.name,
            "symbol": indicator.symbol,
            "source": indicator.source,
        },
        "total_records": len(chart_data),
        "data": chart_data,
    }


@router.get("/lab/combine")
async def combine_indicators_data(
    sym1: str, 
    sym2: str, 
    operation: str, # "add", "sub", "mul", "div"
    db: AsyncSession = Depends(get_db)
):
    """موتور آزمایشگاه: ترکیب دیتای دو شاخص اقتصادی"""
    # دریافت اطلاعات شاخص اول
    ind1_res = await db.execute(select(Indicator).where(Indicator.symbol == sym1.upper()))
    ind1 = ind1_res.scalar_one_or_none()
    
    # دریافت اطلاعات شاخص دوم
    ind2_res = await db.execute(select(Indicator).where(Indicator.symbol == sym2.upper()))
    ind2 = ind2_res.scalar_one_or_none()

    if not ind1 or not ind2:
        raise HTTPException(status_code=404, detail="یکی از شاخص‌ها یافت نشد.")

    # دریافت دیتای هر دو شاخص
    data1_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind1.id))
    data2_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind2.id))
    
    # تبدیل به دیکشنری {تاریخ: مقدار} برای تطبیق سریع
    dict1 = {r.date: r.value for r in data1_res.scalars().all()}
    dict2 = {r.date: r.value for r in data2_res.scalars().all()}
    
    # پیدا کردن تاریخ‌های مشترک
    common_dates = sorted(list(set(dict1.keys()) & set(dict2.keys())))
    
    combined_data = []
    for d in common_dates:
        v1, v2 = dict1[d], dict2[d]
        try:
            if operation == "add": val = v1 + v2
            elif operation == "sub": val = v1 - v2
            elif operation == "mul": val = v1 * v2
            elif operation == "div": val = v1 / v2 if v2 != 0 else 0
            else: continue
            
            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception:
            continue
            
    return combined_data

class FormulaRequest(BaseModel):
    formula: str
    variables: Dict[str, str]

@router.post("/lab/formula")
async def compute_custom_formula(request: FormulaRequest, db: AsyncSession = Depends(get_db)):
    """موتور پیشرفته آزمایشگاه: محاسبه فرمول‌های ریاضی سفارشی روی دیتای سری زمانی"""
    import math
    
    series_data = {}
    
    # ۱. استخراج دیتای تمام متغیرهای ارسال شده (مثل A, B, C)
    for var_name, symbol in request.variables.items():
        ind_res = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
        ind = ind_res.scalar_one_or_none()
        if not ind:
            raise HTTPException(status_code=404, detail=f"نماد {symbol} یافت نشد.")
        
        data_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind.id))
        records = data_res.scalars().all()
        series_data[var_name] = {r.date: r.value for r in records}
    
    if not series_data:
        return []
        
    # ۲. پیدا کردن تاریخ‌های مشترک بین تمام شاخص‌ها
    common_dates = set.intersection(*[set(d.keys()) for d in series_data.values()])
    common_dates = sorted(list(common_dates))
    
    # محیط امن برای اجرای فرمول ریاضی
    safe_math_env = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}
    
    combined_data = []
    for d in common_dates:
        # جایگذاری مقدار هر متغیر در آن تاریخ خاص
        local_vars = {var_name: series_data[var_name][d] for var_name in request.variables.keys()}
        try:
            # اجرای فرمول (مثلا A / B * 100)
            val = eval(request.formula, {"__builtins__": {}}, {**safe_math_env, **local_vars})
            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception as e:
            continue
            
    return combined_data