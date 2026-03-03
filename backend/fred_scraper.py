import asyncio
import os
from datetime import date as dt_date, datetime

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import EconomicData, Indicator

load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY در فایل .env تنظیم نشده است.")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL در فایل .env تنظیم نشده است.")

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _upsert_indicator(session: AsyncSession, series_id: str, series_name: str) -> Indicator:
    result = await session.execute(select(Indicator).where(Indicator.symbol == series_id))
    indicator = result.scalar_one_or_none()

    if indicator is None:
        indicator = Indicator(
            symbol=series_id,
            name=series_name,
            source="FRED",
            frequency="Monthly",
            update_interval_days=30,
            last_updated=dt_date.today(),
        )
        session.add(indicator)
        await session.commit()
        await session.refresh(indicator)
    return indicator


async def fetch_and_insert_fred_data(series_id: str, series_name: str):
    print(f"🦅 در حال دریافت دیتای {series_name} ({series_id}) از فدرال رزرو آمریکا...")
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=20.0)
            response.raise_for_status()
            payload = response.json()

        observations = payload.get("observations", [])
        print(f"✅ دانلود موفق! {len(observations)} رکورد برای {series_id} دریافت شد.")

        cleaned_records = []
        for obs in observations:
            try:
                if obs.get("value") == ".":
                    continue
                date_obj = datetime.strptime(obs["date"], "%Y-%m-%d").date()
                cleaned_records.append({"date": date_obj, "value": float(obs["value"])})
            except (KeyError, ValueError):
                continue

        async with SessionLocal() as session:
            indicator = await _upsert_indicator(session, series_id, series_name)

            if cleaned_records:
                records_to_insert = [
                    {
                        "indicator_id": indicator.id,
                        "date": item["date"],
                        "value": item["value"],
                    }
                    for item in cleaned_records
                ]

                stmt = insert(EconomicData).values(records_to_insert)
                stmt = stmt.on_conflict_do_nothing(index_elements=["indicator_id", "date"])
                result = await session.execute(stmt)

                indicator.last_updated = dt_date.today()
                session.add(indicator)
                await session.commit()
                print(
                    f"🎉 {series_name}: {result.rowcount} رکورد جدید ذخیره شد (از {len(cleaned_records)} رکورد معتبر).\n"
                )
            else:
                print(f"⚠️ رکورد معتبری برای {series_id} پیدا نشد.\n")

    except Exception as exc:
        print(f"❌ خطایی در دریافت {series_id} رخ داد: {exc}\n")


async def main():
    await fetch_and_insert_fred_data("M2SL", "حجم پول آمریکا")
    await fetch_and_insert_fred_data("UNRATE", "نرخ بیکاری آمریکا")


if __name__ == "__main__":
    asyncio.run(main())
