import asyncio
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from database.database import AsyncSessionLocal
from database.models import Indicator

from services.fred_service import fetch_and_store_fred_series
from services.market_service import fetch_and_store_market_data
from services.worldbank_service import fetch_world_bank_data
from services.ecb_service import fetch_and_store_ecb_data
from services.dbnomics_service import fetch_and_store_dbnomics_data
from services.imf_service import fetch_and_store_imf_data
from services.oecd_service import fetch_and_store_oecd_data
from services.bis_service import fetch_and_store_bis_data
from services.eurostat_service import fetch_and_store_eurostat_data
from services.alphavantage_service import fetch_and_store_alphavantage


async def check_and_update_stale_data():
    print(f"[{date.today()}] شروع بررسی دوره‌ای برای آپدیت دیتاهای قدیمی...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Indicator))
        indicators = result.scalars().all()

        today = date.today()

        for ind in indicators:
            if ind.last_updated is not None and (today - ind.last_updated).days < ind.update_interval_days:
                continue

            print(f"آپدیت {ind.symbol} ({ind.source}) - آخرین آپدیت: {ind.last_updated}")

            try:
                if ind.source == "FRED":
                    await fetch_and_store_fred_series(session, ind.symbol, ind.name, ind.frequency or "Monthly")
                elif ind.source == "YAHOO":
                    await fetch_and_store_market_data(session, ind.symbol)
                elif ind.source == "WORLDBANK":
                    parts = ind.symbol.split("_", 2)
                    if len(parts) == 3:
                        _, country, wb_id = parts
                        await fetch_world_bank_data(session, country, wb_id, ind.name)
                elif ind.source == "ECB":
                    await fetch_and_store_ecb_data(session, ind.symbol)
                elif ind.source == "DBNOMICS":
                    await fetch_and_store_dbnomics_data(session, ind.symbol)
                elif ind.source == "IMF":
                    await fetch_and_store_imf_data(session, ind.symbol)
                elif ind.source == "OECD":
                    await fetch_and_store_oecd_data(session, ind.symbol)
                elif ind.source == "BIS":
                    await fetch_and_store_bis_data(session, ind.symbol)
                elif ind.source == "EUROSTAT":
                    await fetch_and_store_eurostat_data(session, ind.symbol)
                elif ind.source == "ALPHAVANTAGE":
                    await fetch_and_store_alphavantage(session, ind.symbol)
            except Exception as e:
                print(f"خطا در آپدیت {ind.symbol}: {e}")

            await asyncio.sleep(2)


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_update_stale_data, trigger='cron', hour=2, minute=0)
    scheduler.start()
    print("سیستم زمان‌بندی (Scheduler) با موفقیت راه‌اندازی شد.")
