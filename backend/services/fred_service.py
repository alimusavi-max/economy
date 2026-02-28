import os
import requests
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, EconomicData

FRED_API_KEY = os.getenv("FRED_API_KEY")

async def fetch_and_store_fred_series(session: AsyncSession, series_id: str, name: str, frequency: str):
    """
    دریافت دیتا از FRED و ذخیره هوشمند در دیتابیس
    """
    print(f"در حال دریافت {name} ({series_id})...")
    
    # ۱. دریافت داده از API
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    response = requests.get(url)
    
    if response.status_code != 200:
        return {"success": False, "message": f"خطا در دریافت دیتا از FRED: {response.status_code}"}
        
    data = response.json()
    observations = data.get('observations', [])

    # ۲. بررسی اینکه آیا این شاخص در دیتابیس ما ثبت شده است یا خیر؟
    result = await session.execute(select(Indicator).where(Indicator.symbol == series_id))
    indicator = result.scalar_one_or_none()
    
    # اگر ثبت نشده بود، آن را می‌سازیم
    if not indicator:
        indicator = Indicator(symbol=series_id, name=name, source="FRED", frequency=frequency)
        session.add(indicator)
        await session.commit()
        await session.refresh(indicator)

    # ۳. آماده‌سازی داده‌ها برای ذخیره
    records_to_insert = []
    for obs in observations:
        try:
            # گاهی FRED برای روزهای تعطیل مقدار "." می‌فرستد که ارور می‌دهد
            val = float(obs['value']) 
            date_obj = datetime.strptime(obs['date'], "%Y-%m-%d").date()
            
            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": val
            })
        except ValueError:
            continue # رد شدن از مقادیر نامعتبر

    if not records_to_insert:
        return {"success": True, "message": "دیتای جدیدی برای ذخیره یافت نشد."}

    # ۴. ذخیره در دیتابیس با قابلیت ON CONFLICT DO NOTHING (رد کردن داده‌های تکراری)
    stmt = insert(EconomicData).values(records_to_insert)
    stmt = stmt.on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
    
    # اجرای دستور
    result = await session.execute(stmt)
    await session.commit()
    
    # محاسبه تعداد رکوردهای جدیدی که واقعاً ذخیره شدند
    inserted_count = result.rowcount
    
    return {
        "success": True, 
        "message": f"عملیات موفقیت‌آمیز بود.",
        "total_records_fetched": len(records_to_insert),
        "new_records_saved": inserted_count
    }