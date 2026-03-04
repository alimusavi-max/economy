import os
import requests
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, EconomicData

FRED_API_KEY = os.getenv("FRED_API_KEY")

async def fetch_and_store_fred_series(session: AsyncSession, series_id: str, name: str, frequency: str):
    print(f"در حال دریافت {name} ({series_id})...")
    
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    
    # اضافه کردن هدر مرورگر واقعی برای جلوگیری از بلاک شدن توسط فایروال FRED
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # استفاده از httpx.AsyncClient به جای requests
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=15.0)
            
        if response.status_code != 200:
            return {"success": False, "message": f"خطا در دریافت دیتا از FRED: {response.status_code} - {response.text}"}
            
        data = response.json()
    except Exception as e:
        return {"success": False, "message": f"خطای شبکه در اتصال به FRED: {str(e)}"}

    observations = data.get('observations', [])

    result = await session.execute(select(Indicator).where(Indicator.symbol == series_id))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        # اگر شاخص وجود نداشت آن را با تنظیمات پیش‌فرض (مثلا آپدیت ۳۰ روزه) می‌سازیم
        indicator = Indicator(symbol=series_id, name=name, source="FRED", frequency=frequency, update_interval_days=30)
        session.add(indicator)
        await session.commit()
        await session.refresh(indicator)

    records_to_insert = []
    for obs in observations:
        try:
            val = float(obs['value']) 
            date_obj = datetime.strptime(obs['date'], "%Y-%m-%d").date()
            
            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": val
            })
        except (ValueError, TypeError):
            continue

    inserted_count = 0
    if records_to_insert:
        stmt = insert(EconomicData).values(records_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
        result = await session.execute(stmt)
        inserted_count = result.rowcount
    
    # آپدیت کردن تاریخ آخرین دریافت موفق
    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()
    
    return {
        "success": True, 
        "message": "عملیات موفقیت‌آمیز بود.",
        "total_records_fetched": len(records_to_insert),
        "new_records_saved": inserted_count
    }