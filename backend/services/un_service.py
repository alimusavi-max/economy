import asyncio
import csv
import io
import requests
from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import EconomicData, Indicator

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

# شاخص‌های هسته SDG سازمان ملل به عنوان بک‌آپ
CORE_UN_FLOWS = [
    {"id": "DF_SDG_01_01", "name": "SDG 1.1.1 - نسبت جمعیت زیر خط فقر"},
    {"id": "DF_SDG_02_01", "name": "SDG 2.1.1 - شاخص فقر مواد غذایی"},
    {"id": "DF_SDG_03_01", "name": "SDG 3.1.1 - نرخ مرگ و میر مادران"},
    {"id": "DF_SDG_04_01", "name": "SDG 4.1.1 - نرخ تکمیل تحصیلات ابتدایی"},
    {"id": "DF_SDG_07_01", "name": "SDG 7.1.1 - دسترسی به برق"},
    {"id": "DF_SDG_13_01", "name": "SDG 13.1.1 - تعداد مرگ ناشی از بلایای طبیعی"},
]


async def auto_discover_un(session: AsyncSession):
    """
    کاوشگر اتوماتیک سازمان ملل متحد (UN) از طریق SDMX API
    """
    print("در حال شروع کاوشگر سازمان ملل متحد (UN)...")

    url = "https://data.un.org/ws/rest/dataflow/UNDATA/all/latest"
    sdmx_headers = {
        **HEADERS,
        "Accept": "application/vnd.sdmx.structure+json;version=1.0",
    }

    response_json = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=sdmx_headers, timeout=30
            )
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    records_to_insert = []

    # پردازش پاسخ SDMX سازمان ملل
    if response_json:
        try:
            dataflows = (
                response_json.get("data", {}).get("dataflows", [])
                or []
            )
            for flow in dataflows:
                flow_id = (flow.get("id") or "").upper().strip()
                names = flow.get("names") or flow.get("name") or {}
                if isinstance(names, dict):
                    name = names.get("en") or names.get("fr") or flow_id
                else:
                    name = str(names) if names else flow_id
                if flow_id:
                    records_to_insert.append({
                        "symbol": f"UN_{flow_id}"[:50],
                        "name": f"UN: {name}"[:255],
                        "source": "UN",
                        "frequency": "Annual",
                        "update_interval_days": 90,
                    })
        except Exception as e:
            print(f"خطا در پارس کردن دیتای UN: {e}")

    # لیست بک‌آپ اگر API پاسخ نداد
    if not records_to_insert:
        print("استفاده از لیست بک‌آپ برای شاخص‌های کلیدی SDG سازمان ملل...")
        for ds in CORE_UN_FLOWS:
            records_to_insert.append({
                "symbol": f"UN_{ds['id']}"[:50],
                "name": f"UN: {ds['name']}"[:255],
                "source": "UN",
                "frequency": "Annual",
                "update_interval_days": 90,
            })

    if not records_to_insert:
        return 0

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر UN تمام شد! {result.rowcount} شاخص سازمان ملل ثبت شد.")
    return result.rowcount


async def fetch_and_store_un_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی از سازمان ملل متحد (UN) با استفاده از SDMX-CSV
    """
    symbol = symbol.upper()
    flow_id = symbol.replace("UN_", "", 1)
    print(f"در حال دانلود دیتای {symbol} از سرورهای سازمان ملل متحد...")

    url = f"https://data.un.org/ws/rest/data/UNDATA,{flow_id}/all?format=sdmx-csv"
    fetch_headers = {
        **HEADERS,
        "Accept": "application/vnd.sdmx.data+csv",
    }

    success = False
    response = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=fetch_headers, timeout=60
            )
            if response.status_code == 200:
                success = True
                break
            elif response.status_code == 404:
                return {"success": False, "message": "دیتایی برای این شاخص UN یافت نشد."}
        except Exception:
            pass
        await asyncio.sleep(5)

    if not success or response is None:
        return {"success": False, "message": "خطا در ارتباط با سرورهای سازمان ملل متحد."}

    # پیدا کردن indicator در دیتابیس
    ind_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = ind_result.scalar_one_or_none()
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

    reader = csv.DictReader(io.StringIO(response.text))
    records_to_insert = []

    for row in reader:
        try:
            date_str = row.get("TIME_PERIOD") or row.get("time_period") or row.get("Time")
            value_str = row.get("OBS_VALUE") or row.get("obs_value") or row.get("Value")

            if not date_str or not value_str:
                continue

            date_str = date_str.strip()
            if len(date_str) == 4:
                date_obj = date(int(date_str), 1, 1)
            elif "Q" in date_str:
                year, q = date_str.split("-Q")
                month = (int(q) * 3) - 2
                date_obj = date(int(year), month, 1)
            elif len(date_str) == 7:
                date_obj = datetime.strptime(date_str, "%Y-%m").date()
            else:
                date_obj = datetime.strptime(date_str[:10], "%Y-%m-%d").date()

            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": float(value_str),
            })
        except Exception:
            continue

    inserted_count = 0
    batch_size = 3000
    for i in range(0, len(records_to_insert), batch_size):
        batch = records_to_insert[i:i + batch_size]
        stmt = insert(EconomicData).values(batch).on_conflict_do_nothing(
            index_elements=["indicator_id", "date"]
        )
        res = await session.execute(stmt)
        inserted_count += res.rowcount

    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()

    print(f"موفق! {inserted_count} رکورد برای {symbol} از UN ذخیره شد.")
    return {"success": True, "new_records": inserted_count}
