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
        except Exception:
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
    """دانلود دیتای تاریخی از سرورهای بانک مرکزی اروپا.

    برای ۷ نماد منتخب (ECB_DFR و ...) از کلید SDMX دقیق استفاده می‌شود.
    برای سایر نمادهای کشف‌شده (ECB_<flow_id>) کل dataflow دریافت و
    نماینده‌ترین سری (طولانی‌ترین) ذخیره می‌شود.
    """
    symbol = symbol.upper()

    if symbol in ECB_SDMX_KEYS:
        # نمادهای منتخب: یک سری مشخص و تک‌مقداری
        sdmx_path = ECB_SDMX_KEYS[symbol]
        pick_representative = False
    elif symbol.startswith("ECB_"):
        # نماد کشف‌شده در سطح dataflow؛ کل مجموعه را می‌گیریم و یک سری را برمی‌گزینیم
        flow_id = symbol[4:].strip()
        if not flow_id:
            return {"success": False, "message": "نماد ECB نامعتبر است."}
        sdmx_path = flow_id
        pick_representative = True
    else:
        return {"success": False, "message": "نماد معتبر ECB نیست."}

    print(f"در حال دانلود دیتای {symbol} از بانک مرکزی اروپا...")

    # lastNObservations برای جلوگیری از دانلود حجیم dataflowهای بزرگ
    url = f"https://data-api.ecb.europa.eu/service/data/{sdmx_path}?format=csvdata"
    if pick_representative:
        url += "&detail=dataonly"

    success = False
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, timeout=20)
            if response.status_code == 200:
                success = True
                break
            await asyncio.sleep(3)
        except Exception:
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

    def _parse_date(date_str):
        s = date_str.strip()
        try:
            if len(s) == 4:            # سالانه: 2023
                return date(int(s), 1, 1)
            if len(s) == 7 and "-Q" in s.upper():  # فصلی: 2023-Q1
                y, q = s.upper().split("-Q")
                return date(int(y), (int(q) - 1) * 3 + 1, 1)
            if len(s) == 7:            # ماهانه: 2023-01
                return datetime.strptime(s + "-01", "%Y-%m-%d").date()
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    # گروه‌بندی ردیف‌ها بر اساس کلید سری؛ ستون KEY هر سری را یکتا می‌کند
    series_rows: dict = {}
    for row in reader:
        date_str = row.get('TIME_PERIOD') or row.get('TIME_PERIOD ')
        value_str = row.get('OBS_VALUE')
        if not date_str or value_str in (None, ""):
            continue
        d = _parse_date(date_str)
        if d is None:
            continue
        try:
            value = float(value_str)
        except (ValueError, TypeError):
            continue
        key = row.get('KEY') or row.get('SERIES_KEY') or symbol
        series_rows.setdefault(key, []).append((d, value))

    if not series_rows:
        return {"success": False, "message": f"داده‌ای برای {symbol} از ECB یافت نشد."}

    if pick_representative:
        # نماینده‌ترین سری = سری با بیشترین تعداد مشاهده
        best_key = max(series_rows, key=lambda k: len(series_rows[k]))
        chosen = series_rows[best_key]
        if best_key != symbol:
            indicator.name = f"{indicator.name} [{best_key}]"[:255]
    else:
        # نمادهای منتخب فقط یک سری دارند
        chosen = [pt for pts in series_rows.values() for pt in pts]

    records_to_insert = [
        {"indicator_id": indicator.id, "date": d, "value": v}
        for d, v in chosen
    ]

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