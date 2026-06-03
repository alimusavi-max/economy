import requests
import asyncio
import csv
import io
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, EconomicData

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
    """
    کاوشگر عمیق و اتوماتیک تمام پایگاه‌های داده بانک مرکزی اروپا (ECB)
    """
    print("🌍 در حال شروع کاوشگر عمیق بانک مرکزی اروپا (ECB)...")
    
    # آدرس رسمی SDMX 2.1 برای دریافت لیست تمام پایگاه‌های داده اروپا
    url = "https://data-api.ecb.europa.eu/service/dataflow/ECB/all/latest"
    headers = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}

    max_retries = 3
    response_json = None
    
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=20)
            if response.status_code == 200:
                response_json = response.json()
                break
            await asyncio.sleep(3)
        except:
            await asyncio.sleep(5)

    records_to_insert = []
    
    # پردازش دیتای اتوماتیک (سازگار با SDMX-JSON 1.0 و 2.0)
    dataflows = []
    if response_json:
        dataflows = (
            response_json.get("data", {}).get("dataflows")
            or response_json.get("data", {}).get("Dataflows")
            or response_json.get("Structures", {}).get("Dataflows")
            or response_json.get("Structures", {}).get("dataflows")
            or []
        )
    if dataflows:
        for flow in dataflows:
            flow_id = (flow.get("id") or "").upper().strip()
            raw_name = flow.get("name") or flow.get("names", {})
            name = (raw_name.get("en") if isinstance(raw_name, dict) else raw_name) or flow_id
            if flow_id:
                records_to_insert.append({
                    "symbol": f"ECB_{flow_id}"[:50],
                    "name": f"ECB: {name}"[:255],
                    "source": "ECB",
                    "frequency": "Mixed",
                    "update_interval_days": 30
                })
    else:
        print("خطا در ارتباط با سرورهای ECB یا پارس ساختار SDMX.")

    # تزریق به دیتابیس
    if records_to_insert:
        stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=['symbol'])
        result = await session.execute(stmt)
        await session.commit()
        print(f"🎉 کاوشگر ECB تمام شد! {result.rowcount} مجموعه داده کلان از اروپا ثبت شد.")
        return result.rowcount

    return 0

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
            response = await asyncio.to_thread(requests.get, url, timeout=20)
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
    
    # پیدا کردن indicator در دیتابیس
    indicator_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = indicator_result.scalar_one_or_none()
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

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
            value = float(value_str)

            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": value,
            })
        except Exception as e:
            continue

    inserted_count = 0
    batch_size = 3000
    for i in range(0, len(records_to_insert), batch_size):
        batch = records_to_insert[i:i + batch_size]
        stmt = insert(EconomicData).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
        res = await session.execute(stmt)
        inserted_count += res.rowcount

    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()

    return {
        "success": True,
        "message": f"دیتای {symbol} از ECB ذخیره شد.",
        "new_records": inserted_count
    }