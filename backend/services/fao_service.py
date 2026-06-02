import asyncio
import requests
from datetime import date
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import EconomicData, Indicator

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}


async def auto_discover_fao(session: AsyncSession):
    """کاوشگر اتوماتیک سازمان خواروبار و کشاورزی ملل متحد (FAO)"""
    print("در حال شروع کاوشگر FAO...")

    url = "https://www.fao.org/faostat/api/v1/en/groupsanddomains"
    response_json = None

    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    records_to_insert = []

    if response_json and "data" in response_json:
        for item in response_json["data"]:
            code = (item.get("Code") or "").upper().strip()
            label = item.get("Label") or code
            if code:
                records_to_insert.append({
                    "symbol": f"FAO_{code}"[:50],
                    "name": f"FAO: {label}"[:255],
                    "source": "FAO",
                    "frequency": "Annual",
                    "update_interval_days": 180,
                })
    else:
        print("خطا در ارتباط با FAO؛ استفاده از لیست بک‌آپ...")
        core_fao = [
            {"code": "QCL", "label": "تولید محصولات کشاورزی"},
            {"code": "FBS", "label": "ترازنامه غذا"},
            {"code": "FOOD", "label": "شاخص‌های امنیت غذایی"},
            {"code": "PRICES", "label": "قیمت تولیدکننده"},
            {"code": "TRADE", "label": "تجارت محصولات کشاورزی"},
            {"code": "LAND", "label": "استفاده از زمین کشاورزی"},
        ]
        for ds in core_fao:
            records_to_insert.append({
                "symbol": f"FAO_{ds['code']}",
                "name": f"FAO: {ds['label']}",
                "source": "FAO",
                "frequency": "Annual",
                "update_interval_days": 180,
            })

    if not records_to_insert:
        return 0

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر FAO تمام شد! {result.rowcount} دامنه ثبت شد.")
    return result.rowcount


async def fetch_and_store_fao_data(session: AsyncSession, symbol: str):
    """دانلود دیتای سالانه از FAO برای یک دامنه"""
    symbol = symbol.upper()
    domain_code = symbol.replace("FAO_", "", 1)
    print(f"در حال دانلود دیتای {symbol} از FAO...")

    url = (
        f"https://www.fao.org/faostat/api/v1/en/data/{domain_code}"
        f"?area=WLD&elements=all&years=1990:2024&format=json&per_page=50000"
    )

    success = False
    response = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=HEADERS, timeout=60)
            if response.status_code == 200:
                success = True
                break
            elif response.status_code == 404:
                return {"success": False, "message": "دیتایی برای این دامنه FAO یافت نشد."}
        except Exception:
            pass
        await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای FAO."}

    indicator_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = indicator_result.scalar_one_or_none()
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

    data_json = response.json()
    items = data_json.get("data", [])

    # گروه‌بندی بر اساس سال و میانگین‌گیری
    year_values: dict = {}
    year_counts: dict = {}
    for item in items:
        try:
            year = int(item.get("Year", 0))
            value = item.get("Value")
            if not year or value is None or value == "":
                continue
            val = float(value)
            year_values[year] = year_values.get(year, 0.0) + val
            year_counts[year] = year_counts.get(year, 0) + 1
        except Exception:
            continue

    records_to_insert = []
    for year, total in year_values.items():
        count = year_counts[year]
        avg_val = total / count if count > 0 else total
        records_to_insert.append({
            "indicator_id": indicator.id,
            "date": date(year, 1, 1),
            "value": avg_val,
        })

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

    print(f"موفق! {inserted_count} رکورد برای {symbol} از FAO ذخیره شد.")
    return {"success": True, "new_records": inserted_count}
