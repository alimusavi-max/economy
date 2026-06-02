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


async def auto_discover_ilo(session: AsyncSession):
    """کاوشگر اتوماتیک سازمان بین‌المللی کار (ILO) - دریافت لیست Dataflow‌ها"""
    print("در حال شروع کاوشگر سازمان بین‌المللی کار (ILO)...")

    url = "https://sdmx.ilo.org/rest/dataflow/ILO/all/latest"
    headers = {**HEADERS, "Accept": "application/vnd.sdmx.structure+json;version=1.0"}

    response_json = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=30)
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    records_to_insert = []

    if response_json:
        try:
            dataflows = (
                response_json.get("data", {}).get("dataflows", [])
                or response_json.get("DataStructures", [])
            )
            for flow in dataflows:
                flow_id = (flow.get("id") or "").upper().strip()
                name = flow.get("name") or flow_id
                if flow_id:
                    records_to_insert.append({
                        "symbol": f"ILO_{flow_id}"[:50],
                        "name": f"ILO: {name}"[:255],
                        "source": "ILO",
                        "frequency": "Mixed",
                        "update_interval_days": 90,
                    })
        except Exception as e:
            print(f"خطا در پارس کردن دیتای ILO: {e}")

    # بک‌آپ هسته‌های اصلی ILO
    if not records_to_insert:
        print("استفاده از لیست بک‌آپ برای شاخص‌های اصلی ILO...")
        core_ilo = [
            {"id": "UNE_TUNE_SEX_AGE_NB", "name": "نرخ بیکاری بر اساس جنسیت و سن"},
            {"id": "EAP_TEAP_SEX_AGE_NB", "name": "جمعیت فعال اقتصادی"},
            {"id": "EMP_TEMP_SEX_AGE_NB", "name": "اشتغال بر اساس جنسیت و سن"},
            {"id": "HOW_TEMP_SEX_ECO_NB", "name": "ساعات کار بر اساس بخش"},
            {"id": "EAR_INEE_SEX_ECO_NB", "name": "دستمزد بر اساس بخش اقتصادی"},
            {"id": "SDG_0831_SEX_RT", "name": "SDG 8.3.1 - نرخ اشتغال غیررسمی"},
        ]
        for ds in core_ilo:
            records_to_insert.append({
                "symbol": f"ILO_{ds['id']}"[:50],
                "name": f"ILO: {ds['name']}"[:255],
                "source": "ILO",
                "frequency": "Mixed",
                "update_interval_days": 90,
            })

    if not records_to_insert:
        return 0

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر ILO تمام شد! {result.rowcount} شاخص ثبت شد.")
    return result.rowcount


async def fetch_and_store_ilo_data(session: AsyncSession, symbol: str):
    """دانلود دیتای تاریخی از سازمان بین‌المللی کار (ILO)"""
    symbol = symbol.upper()
    flow_id = symbol.replace("ILO_", "", 1)
    print(f"در حال دانلود دیتای {symbol} از ILO...")

    url = f"https://sdmx.ilo.org/rest/data/ILO,{flow_id}/all?format=genericdata"
    headers = {**HEADERS, "Accept": "application/vnd.sdmx.data+csv;version=1.0"}

    success = False
    response = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=60)
            if response.status_code == 200:
                success = True
                break
            elif response.status_code == 404:
                return {"success": False, "message": "دیتایی برای این شاخص ILO یافت نشد."}
        except Exception:
            pass
        await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای ILO."}

    indicator_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = indicator_result.scalar_one_or_none()
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
        stmt = insert(EconomicData).values(batch).on_conflict_do_nothing(index_elements=["indicator_id", "date"])
        res = await session.execute(stmt)
        inserted_count += res.rowcount

    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()

    print(f"موفق! {inserted_count} رکورد برای {symbol} از ILO ذخیره شد.")
    return {"success": True, "new_records": inserted_count}
