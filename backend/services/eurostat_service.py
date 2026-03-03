import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator

async def auto_discover_eurostat(session: AsyncSession):
    """
    دریافت اتوماتیک لیست پایگاه‌های داده از مرکز آمار اروپا (Eurostat SDMX 2.1)
    """
    print("🇪🇺 در حال شروع کاوشگر مرکز آمار اروپا (Eurostat)...")
    
    # آدرس رسمی API مرکز آمار اروپا برای دریافت تمام کاتالوگ‌ها
    url = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all"
    headers = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}

    max_retries = 3
    response_json = None
    
    # مکانیزم تلاش مجدد برای جلوگیری از خطای شبکه
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=25)
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    if not response_json or "data" not in response_json:
        print("❌ خطا در دریافت کاتالوگ Eurostat. آیا اینترنت متصل است؟")
        return 0

    records_to_insert = []
    
    try:
        dataflows = response_json["data"].get("dataflows", [])
        for flow in dataflows:
            flow_id = (flow.get("id") or "").upper().strip()
            name = flow.get("name") or flow_id
            if flow_id:
                records_to_insert.append({
                    "symbol": f"EUROSTAT_{flow_id}"[:50],
                    "name": f"Eurostat: {name}"[:255],  # برش نام برای جلوگیری از خطای طول دیتابیس
                    "source": "EUROSTAT",
                    "frequency": "Mixed",
                    "update_interval_days": 30
                })
    except Exception as e:
        print(f"❌ خطا در پارس کردن دیتای Eurostat: {e}")

    if not records_to_insert:
        return 0

    # تزریق یک‌جای هزاران رکورد به دیتابیس بدون تکرار
    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"🎉 کاوشگر Eurostat تمام شد! {result.rowcount} مجموعه داده دقیق از اروپا ثبت شد.")
    return result.rowcount