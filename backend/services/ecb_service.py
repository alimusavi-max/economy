import requests
import asyncio
import csv
import io
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, AssetMarketData

# دیکشنری ترجمه نمادهای خوانای ما به کلیدهای پیچیده SDMX بانک مرکزی اروپا
ECB_SDMX_KEYS = {
    "ECB_DFR": "FM/B.U2.EUR.4F.KR.DFR.CHG", # نرخ سپرده
    "ECB_MRO": "FM/B.U2.EUR.4F.KR.MRR_RT.LEV", # نرخ ریفایننس
    "ECB_MLF": "FM/B.U2.EUR.4F.KR.MLF.CHG", # نرخ وام‌دهی
    "ECB_HICP": "ICP/M.U2.N.000000.4.ANR", # تورم سالانه ناحیه یورو
    "ECB_UNEMP": "STS/M.I8.W.UNEM.UNEH.RT.N.A", # نرخ بیکاری
    "ECB_EURUSD": "EXR/D.USD.EUR.SP00.A", # نرخ رسمی برابری یورو به دلار
    "ECB_EURGBP": "EXR/D.GBP.EUR.SP00.A", # نرخ رسمی برابری یورو به پوند
}

async def auto_discover_ecb(session: AsyncSession):
    """تزریق شناسنامه حیاتی‌ترین شاخص‌های اقتصاد کلان اروپا به دیتابیس"""
    print("در حال شروع کاوشگر بانک مرکزی اروپا (ECB)...")
    
    ecb_core_indicators = [
        {"symbol": "ECB_DFR", "name": "نرخ تسهیلات سپرده (Deposit Facility Rate) - اروپا", "frequency": "Daily", "update_interval_days": 1},
        {"symbol": "ECB_MRO", "name": "نرخ عملیات ریفایننس (Main Refinancing Operations) - اروپا", "frequency": "Daily", "update_interval_days": 1},
        {"symbol": "ECB_MLF", "name": "نرخ تسهیلات وام‌دهی نهایی (Marginal Lending Facility) - اروپا", "frequency": "Daily", "update_interval_days": 1},
        {"symbol": "ECB_HICP", "name": "تورم ناحیه یورو (HICP - Annual Rate)", "frequency": "Monthly", "update_interval_days": 30},
        {"symbol": "ECB_UNEMP", "name": "نرخ بیکاری ناحیه یورو", "frequency": "Monthly", "update_interval_days": 30},
        {"symbol": "ECB_EURUSD", "name": "نرخ رسمی یورو به دلار (EUR/USD) - رفرنس ECB", "frequency": "Daily", "update_interval_days": 1},
        {"symbol": "ECB_EURGBP", "name": "نرخ رسمی یورو به پوند (EUR/GBP) - رفرنس ECB", "frequency": "Daily", "update_interval_days": 1},
    ]

    records_to_insert = []
    for ind in ecb_core_indicators:
        records_to_insert.append({
            "symbol": ind['symbol'],
            "name": ind['name'],
            "source": "ECB",
            "frequency": ind['frequency'],
            "update_interval_days": ind['update_interval_days']
        })

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=['symbol'])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر ECB تمام شد! {result.rowcount} شاخص کلان اروپا ثبت شد.")
    return result.rowcount

async def fetch_and_store_ecb_data(session: AsyncSession, symbol: str):
    """دانلود دیتای تاریخی از سرورهای بانک مرکزی اروپا"""
    symbol = symbol.upper()
    if symbol not in ECB_SDMX_KEYS:
        return {"success": False, "message": "این نماد در لیست کلیدهای معتبر ECB یافت نشد."}

    print(f"در حال دانلود دیتای {symbol} از بانک مرکزی اروپا...")
    sdmx_key = ECB_SDMX_KEYS[symbol]
    
    # استفاده از فرمت csvdata برای دریافت سبک و سریع اطلاعات از ECB
    url = f"https://data-api.ecb.europa.eu/service/data/{sdmx_key}?format=csvdata"
    
    success = False
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                success = True
                break
            await asyncio.sleep(3)
        except:
            await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای بانک مرکزی اروپا"}

    # خواندن دیتای CSV در حافظه
    csv_data = response.text
    reader = csv.DictReader(io.StringIO(csv_data))
    
    records_to_insert = []
    for row in reader:
        try:
            # ستون TIME_PERIOD تاریخ است و OBS_VALUE مقدار آن
            date_str = row.get('TIME_PERIOD')
            value_str = row.get('OBS_VALUE')
            
            if not date_str or not value_str:
                continue
                
            # گاهی تاریخ‌ها ماهانه (2023-01) هستند، روز اول ماه در نظر می‌گیریم
            if len(date_str) == 7:
                date_str += "-01"
                
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            close_price = float(value_str)
            
            records_to_insert.append({
                "symbol": symbol,
                "date": date_obj,
                "close_price": close_price,
                "volume": 0.0 # شاخص‌های کلان حجم ندارند
            })
        except Exception as e:
            continue

    if records_to_insert:
        stmt = insert(AssetMarketData).values(records_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'date'])
        result = await session.execute(stmt)
        
        # آپدیت تاریخ آخرین همگام‌سازی در جدول شناسنامه
        indicator_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
        indicator = indicator_result.scalar_one_or_none()
        if indicator:
            indicator.last_updated = date.today()
            session.add(indicator)
            
        await session.commit()
        
    return {
        "success": True, 
        "message": f"دیتای {symbol} از ECB ذخیره شد.",
        "new_records": len(records_to_insert)
    }