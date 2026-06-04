import asyncio
import sys
from sqlalchemy import select
from database.database import AsyncSessionLocal
from database.models import Indicator
from services.alphavantage_service import fetch_and_store_alphavantage
from services.bis_service import fetch_and_store_bis_data
from services.dbnomics_service import fetch_and_store_dbnomics_data
from services.ecb_service import fetch_and_store_ecb_data
from services.eurostat_service import fetch_and_store_eurostat_data
from services.fao_service import fetch_and_store_fao_data
from services.fred_service import fetch_and_store_fred_series
from services.ilo_service import fetch_and_store_ilo_data
from services.imf_service import fetch_and_store_imf_data
from services.market_service import fetch_and_store_market_data
from services.oecd_service import fetch_and_store_oecd_data
from services.treasury_service import fetch_and_store_treasury_data
from services.un_service import fetch_and_store_un_data
from services.worldbank_service import fetch_world_bank_data


async def run_miner(target_source=None):
    print("==================================================")
    print(" ⛏️  موتور معدن‌چی اقتصاد جهانی (Master Miner) روشن شد ")
    print("==================================================\n")

    async with AsyncSessionLocal() as session:
        query = select(Indicator)
        if target_source:
            query = query.where(Indicator.source == target_source.upper())

        result = await session.execute(query)
        indicators = result.scalars().all()

        total = len(indicators)
        print(f"📊 تعداد {total} شاخص برای استخراج در صف قرار گرفت.\n")

        if total == 0:
            print("شاخصی یافت نشد! آیا کاوشگرها (Spiders) را اجرا کرده‌اید؟")
            return

        for index, ind in enumerate(indicators):
            print(f"[{index+1}/{total}] در حال استخراج ⬅️ {ind.symbol} ({ind.source})...")

            try:
                res = None

                if ind.source == "FRED":
                    res = await fetch_and_store_fred_series(session, ind.symbol, ind.name, ind.frequency or "Monthly")
                    await asyncio.sleep(1.5)

                elif ind.source == "WORLDBANK":
                    parts = ind.symbol.split("_", 2)
                    if len(parts) == 3:
                        _, country, wb_id = parts
                        res = await fetch_world_bank_data(session, country, wb_id, ind.name)
                    else:
                        res = await fetch_world_bank_data(session, "all", ind.symbol, ind.name)
                    await asyncio.sleep(2)

                elif ind.source == "YAHOO":
                    res = await fetch_and_store_market_data(session, ind.symbol)
                    await asyncio.sleep(1.5)

                elif ind.source == "ECB":
                    res = await fetch_and_store_ecb_data(session, ind.symbol)
                    await asyncio.sleep(1.5)

                elif ind.source == "DBNOMICS":
                    res = await fetch_and_store_dbnomics_data(session, ind.symbol)
                    await asyncio.sleep(1)

                elif ind.source == "BIS":
                    res = await fetch_and_store_bis_data(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "IMF":
                    res = await fetch_and_store_imf_data(session, ind.symbol)
                    await asyncio.sleep(1)

                elif ind.source == "OECD":
                    res = await fetch_and_store_oecd_data(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "EUROSTAT":
                    res = await fetch_and_store_eurostat_data(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "ALPHAVANTAGE":
                    res = await fetch_and_store_alphavantage(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "ILO":
                    res = await fetch_and_store_ilo_data(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "TREASURY":
                    res = await fetch_and_store_treasury_data(session, ind.symbol)
                    await asyncio.sleep(1)

                elif ind.source == "FAO":
                    res = await fetch_and_store_fao_data(session, ind.symbol)
                    await asyncio.sleep(2)

                elif ind.source == "UN":
                    res = await fetch_and_store_un_data(session, ind.symbol)
                    await asyncio.sleep(2)

                else:
                    print(f"   ⚠️ منبع ناشناخته: {ind.source} — رد شد.")
                    continue

                if res and isinstance(res, dict):
                    if res.get("success"):
                        print(f"   ✅ {ind.symbol}: {res.get('new_records', '?')} رکورد جدید")
                    else:
                        print(f"   ⚠️ {ind.symbol}: {res.get('message', 'خطای ناشناخته')}")

            except Exception as e:
                print(f"   ❌ خطا در دانلود شاخص {ind.symbol}: {e}")
                print("   🔄 استراحت ۵ ثانیه‌ای برای بازیابی ارتباط...")
                await asyncio.sleep(5)

    print("\n✅ عملیات معدن‌چی با موفقیت به پایان رسید!")


if __name__ == "__main__":
    source_arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        asyncio.run(run_miner(source_arg))
    except KeyboardInterrupt:
        print("\n🛑 معدن‌چی با دستور شما متوقف شد.")
