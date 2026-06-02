import asyncio
import requests
from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import EconomicData, Indicator

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

TREASURY_DATASETS = {
    "TREASURY_AVGRATES": {
        "url": "https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates",
        "date_field": "record_date",
        "value_field": "avg_interest_rate_amt",
        "name": "میانگین نرخ بهره اوراق قرضه آمریکا",
    },
    "TREASURY_DEBTPOS": {
        "url": "https://api.fiscaldata.treasury.gov/services/api/v1/debt/mspd/mspd_table_1",
        "date_field": "record_date",
        "value_field": "total_mil_amt",
        "name": "کل بدهی عمومی ایالات متحده (میلیون دلار)",
    },
}


async def auto_discover_treasury(session: AsyncSession):
    """ثبت شاخص‌های از پیش تعریف‌شده خزانه‌داری آمریکا"""
    print("در حال ثبت شاخص‌های خزانه‌داری ایالات متحده (US Treasury)...")

    records_to_insert = [
        {
            "symbol": symbol,
            "name": meta["name"],
            "source": "TREASURY",
            "frequency": "Monthly",
            "update_interval_days": 30,
        }
        for symbol, meta in TREASURY_DATASETS.items()
    ]

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر Treasury تمام شد! {result.rowcount} شاخص ثبت شد.")
    return result.rowcount


async def fetch_and_store_treasury_data(session: AsyncSession, symbol: str):
    """دانلود دیتا از API خزانه‌داری آمریکا (Fiscal Data)"""
    symbol = symbol.upper()

    if symbol not in TREASURY_DATASETS:
        return {"success": False, "message": "این نماد در لیست شاخص‌های Treasury یافت نشد."}

    meta = TREASURY_DATASETS[symbol]
    date_field = meta["date_field"]
    value_field = meta["value_field"]
    base_url = meta["url"]

    url = f"{base_url}?fields={date_field},{value_field}&sort=-{date_field}&per_page=10000&format=json"
    print(f"در حال دانلود دیتای {symbol} از خزانه‌داری آمریکا...")

    success = False
    response = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(requests.get, url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                success = True
                break
        except Exception:
            pass
        await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای Fiscal Data خزانه‌داری."}

    indicator_result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = indicator_result.scalar_one_or_none()
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

    data_json = response.json()
    items = data_json.get("data", [])

    records_to_insert = []
    for item in items:
        try:
            date_str = item.get(date_field, "").strip()
            value_str = str(item.get(value_field, "")).strip()

            if not date_str or not value_str:
                continue

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

    print(f"موفق! {inserted_count} رکورد برای {symbol} از Treasury ذخیره شد.")
    return {"success": True, "new_records": inserted_count}
