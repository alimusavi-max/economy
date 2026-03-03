import asyncio
from datetime import date

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Indicator, EconomicData


async def get_all_worldbank_indicators():
    """دریافت لیست کامل شاخص‌های بانک جهانی برای عملیات crawler."""
    url = "http://api.worldbank.org/v2/indicator?format=json&per_page=25000&page=1"
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        print(f"خطا در دریافت لیست شاخص‌های بانک جهانی: {response.status_code}")
        return []

    data = response.json()
    if len(data) < 2:
        return []

    return data[1] or []


async def fetch_world_bank_data(session: AsyncSession, country: str, indicator_id: str, name: str):
    """دریافت داده‌ی یک شاخص بانک جهانی برای یک کشور مشخص (یا all) و ذخیره در دیتابیس."""
    country_code = country.lower()
    symbol = f"WB_{country.upper()}_{indicator_id.upper()}"

    print(f"در حال دریافت {name} ({indicator_id}) برای {country}...")
    url = f"http://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_id}?format=json&per_page=20000"
    response = requests.get(url, timeout=30)

    if response.status_code != 200:
        return {"success": False, "message": f"خطا در دریافت دیتا از WorldBank: {response.status_code}"}

    payload = response.json()
    if len(payload) < 2 or not payload[1]:
        return {"success": False, "message": "داده‌ای از WorldBank دریافت نشد."}

    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()

    if not indicator:
        indicator = Indicator(
            symbol=symbol,
            name=name,
            source="WORLDBANK",
            frequency="Yearly",
            update_interval_days=180,
        )
        session.add(indicator)
        await session.commit()
        await session.refresh(indicator)

    records_to_insert = []
    for row in payload[1]:
        if row.get("value") is None or not row.get("date"):
            continue
        try:
            value = float(row["value"])
            year = int(row["date"])
            records_to_insert.append(
                {"indicator_id": indicator.id, "date": date(year, 1, 1), "value": value}
            )
        except (ValueError, TypeError):
            continue

    inserted_count = 0
    if records_to_insert:
        stmt = insert(EconomicData).values(records_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["indicator_id", "date"])
        result = await session.execute(stmt)
        inserted_count = result.rowcount

    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()

    return {
        "success": True,
        "message": "عملیات موفقیت‌آمیز بود.",
        "total_records_fetched": len(records_to_insert),
        "new_records_saved": inserted_count,
    }


async def auto_discover_worldbank_indicators(session: AsyncSession):
    """
    دریافت اتوماتیک لیست تمام شاخص‌های بانک جهانی با مکانیزم ضد قطعی
    """
    print("در حال شروع کاوشگر اتوماتیک بانک جهانی (WorldBank)...")
    page = 1
    total_added = 0
    max_retries = 3  # حداکثر ۳ بار تلاش در صورت قطعی

    while True:
        url = f"http://api.worldbank.org/v2/indicator?format=json&per_page=5000&page={page}"
        print(f"در حال دریافت صفحه {page} از بانک جهانی...")

        # --- مکانیزم تلاش مجدد (Retry Mechanism) ---
        success = False
        for attempt in range(max_retries):
            try:
                # استفاده از timeout تا در صورت قطعی اینترنت، برنامه قفل نکند
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    success = True
                    break  # خروج از حلقه تلاش مجدد
                else:
                    print(f"خطای سرور {response.status_code}. تلاش {attempt + 1} از {max_retries}...")
                    await asyncio.sleep(5)  # ۵ ثانیه صبر و تلاش دوباره
            except Exception as e:
                print(f"قطعی ارتباط: {e}. تلاش {attempt + 1} از {max_retries}...")
                await asyncio.sleep(10)  # ۱۰ ثانیه صبر در صورت قطعی اینترنت

        if not success:
            print(f"دریافت صفحه {page} پس از {max_retries} بار تلاش با شکست مواجه شد. عبور از این صفحه...")
            break
        # -------------------------------------------

        data = response.json()
        if len(data) < 2:
            break

        indicators_list = data[1]
        if not indicators_list:
            break

        records_to_insert = []
        for ind in indicators_list:
            records_to_insert.append({
                "symbol": ind["id"].upper(),
                "name": ind["name"],
                "source": "WORLDBANK",
                "frequency": "Yearly",
                "update_interval_days": 180,
            })

        if records_to_insert:
            stmt = insert(Indicator).values(records_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=["symbol"])
            result = await session.execute(stmt)
            await session.commit()
            total_added += result.rowcount

        pagination = data[0]
        if page >= pagination["pages"]:
            break

        page += 1
        await asyncio.sleep(1)  # یک ثانیه مکث بین هر صفحه برای جلوگیری از بلاک شدن توسط سرور

    print(f"کاوشگر بانک جهانی تمام شد! {total_added} شاخص جدید ثبت شد.")
    return total_added
