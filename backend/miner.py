import asyncio
import sys
from sqlalchemy import select
from database.database import AsyncSessionLocal
from database.models import Indicator
from services.imf_service import fetch_and_store_imf_data
# ایمپورت توابع استخراج (Fetchers)
from services.fred_service import fetch_and_store_fred_series
from services.worldbank_service import fetch_world_bank_data
from services.market_service import fetch_and_store_market_data
from services.ecb_service import fetch_and_store_ecb_data
from services.bis_service import fetch_and_store_bis_data # 👈 موتور جدید BIS اضافه شد
from services.dbnomics_service import fetch_and_store_dbnomics_data
from services.eurostat_service import fetch_and_store_eurostat_data
async def run_miner(target_source=None):
    print("==================================================")
    print(" ⛏️  موتور معدن‌چی اقتصاد جهانی (Master Miner) روشن شد ")
    print("==================================================\n")
    
    async with AsyncSessionLocal() as session:
        # ۱. پیدا کردن شاخص‌ها از دیتابیس
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

        # ۲. حلقه بی‌نهایت و صبور برای دانلود تک‌تک دیتاها
        for index, ind in enumerate(indicators):
            print(f"[{index+1}/{total}] در حال استخراج ⬅️ {ind.symbol} ({ind.source})...")
            
            try:
                if ind.source == "FRED":
                    await fetch_and_store_fred_series(session, ind.symbol, ind.name, ind.frequency or "Monthly")
                    await asyncio.sleep(1.5)
                    
                elif ind.source == "WORLDBANK":
                    original_id = ind.symbol.replace("WB_ALL_", "") if "WB_ALL_" in ind.symbol else ind.symbol
                    await fetch_world_bank_data(session, "all", original_id, ind.name)
                    await asyncio.sleep(2)
                    
                elif ind.source == "YAHOO":
                    await fetch_and_store_market_data(session, ind.symbol)
                    await asyncio.sleep(1.5)
                    
                elif ind.source == "ECB":
                    await fetch_and_store_ecb_data(session, ind.symbol)
                    await asyncio.sleep(1.5)


                elif ind.source == "DBNOMICS":
                    result = await fetch_and_store_dbnomics_data(session, ind.symbol)
                    if result.get("success"):
                        print(f"   📊 دیتای {ind.symbol} با موفقیت تزریق شد.")
                    else:
                        print(f"   ⚠️ پیام سرور: {result.get('message')}")
                    await asyncio.sleep(1)
                    
                # 👇 بخش جدید و اختصاصی برای بانک تسویه حساب‌های بین‌المللی (BIS)
                elif ind.source == "BIS":
                    result = await fetch_and_store_bis_data(session, ind.symbol)
                    if result.get("success"):
                        print(f"   📊 دیتای {ind.symbol} با موفقیت در دیتابیس تزریق شد.")
                    else:
                        print(f"   ⚠️ پیام سرور BIS: {result.get('message')}")
                    await asyncio.sleep(2)
                    
                # بقیه بانک‌ها که هنوز موتور SDMX ندارند
                # 👇 بخش جدید اضافه شده برای صندوق بین‌المللی پول
                elif ind.source == "IMF":
                    result = await fetch_and_store_imf_data(session, ind.symbol)
                    if result.get("success"):
                        print(f"   📊 دیتای {ind.symbol} با موفقیت تزریق شد.")
                    else:
                        print(f"   ⚠️ پیام سرور IMF: {result.get('message')}")
                    await asyncio.sleep(1) # استراحت ۱ ثانیه‌ای
                    
                # یوروستات و OECD هنوز موتور استخراج ندارند
                # 👇 آخرین قطعه پازل اقتصاد کلان (یوروستات)
                elif ind.source == "EUROSTAT":
                    result = await fetch_and_store_eurostat_data(session, ind.symbol)
                    if result.get("success"):
                        print(f"   📊 دیتای {ind.symbol} با موفقیت تزریق شد.")
                    else:
                        print(f"   ⚠️ پیام سرور Eurostat: {result.get('message')}")
                    await asyncio.sleep(2) # استراحت ۲ ثانیه‌ای برای فرار از بلاک شدن
                    
            except Exception as e:
                print(f"   ❌ خطا در دانلود شاخص {ind.symbol}: {e}")
                print("   🔄 در حال استراحت ۵ ثانیه‌ای برای بازیابی ارتباط...")
                await asyncio.sleep(5)

    print("\n✅ عملیات معدن‌چی با موفقیت به پایان رسید!")

if __name__ == "__main__":
    source_arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        asyncio.run(run_miner(source_arg))
    except KeyboardInterrupt:
        print("\n🛑 معدن‌چی با دستور شما متوقف شد.")