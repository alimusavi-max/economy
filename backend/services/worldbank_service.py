import requests
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, EconomicData

async def get_all_worldbank_indicators():
    """این تابع لیست تمام ۲۴,۰۰۰ شاخص موجود در بانک جهانی را استخراج می‌کند"""
    print("🔍 در حال جستجو برای یافتن تمام شاخص‌های بانک جهانی...")
    url = "https://api.worldbank.org/v2/indicator?format=json&per_page=30000"
    response = await asyncio.to_thread(requests.get, url)
    
    if response.status_code == 200 and len(response.json()) > 1:
        indicators = response.json()[1]
        print(f"🎯 تعداد {len(indicators)} شاخص مختلف در بانک جهانی پیدا شد!")
        return indicators
    return []

async def fetch_world_bank_data(session: AsyncSession, country_code: str, indicator_code: str, name: str):
    """دریافت دیتای یک شاخص. اگر country_code برابر all باشد، دیتای کل کشورهای دنیا را می‌گیرد!"""
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}?format=json&per_page=20000"
    
    response = await asyncio.to_thread(requests.get, url)
    if response.status_code != 200 or len(response.json()) < 2:
        return {"success": False}
        
    data = response.json()[1]
    
    # برای اینکه سرعت ذخیره در دیتابیس بالا برود، شناسنامه‌ها را کش می‌کنیم
    indicators_cache = {}
    records_to_insert = []
    
    for item in data:
        if item['value'] is not None and item.get('countryiso3code'):
            c_code = item['countryiso3code']
            symbol = f"WB_{c_code}_{indicator_code}".upper()
            
            # اگر این نماد قبلاً در دیتابیس ثبت نشده بود، آن را می‌سازیم
            if symbol not in indicators_cache:
                ind_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
                indicator = ind_result.scalar_one_or_none()
                
                if not indicator:
                    indicator = Indicator(
                        symbol=symbol, 
                        name=f"{item['country']['value']} - {name}", 
                        source="World Bank", 
                        frequency="Yearly"
                    )
                    session.add(indicator)
                    await session.commit()
                    await session.refresh(indicator)
                
                indicators_cache[symbol] = indicator.id

            date_obj = datetime.strptime(f"{item['date']}-01-01", "%Y-%m-%d").date()
            records_to_insert.append({
                "indicator_id": indicators_cache[symbol],
                "date": date_obj,
                "value": float(item['value'])
            })

    if records_to_insert:
        stmt = insert(EconomicData).values(records_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
        await session.execute(stmt)
        await session.commit()
        
    return {"success": True, "records_saved": len(records_to_insert)}