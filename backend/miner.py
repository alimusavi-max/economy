import asyncio
import sys
from sqlalchemy import select
from database.database import AsyncSessionLocal
from database.models import Indicator

# ایمپورت توابع استخراج (Fetchers)
from services.fred_service import fetch_and_store_fred_series
from services.worldbank_service import fetch_world_bank_data
from services.market_service import fetch_and_store_market_data
from services.ecb_service import fetch_and_store_ecb_data

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
                    await asyncio.sleep(1.5) # جلوگیری از بلاک شدن IP (Rate Limit)
                    
                elif ind.source == "WORLDBANK":
                    # ارسال کلمه all برای دریافت دیتای همه کشورهای دنیا به صورت یکجا
                    original_id = ind.symbol.replace("WB_ALL_", "") if "WB_ALL_" in ind.symbol else ind.symbol
                    await fetch_world_bank_data(session, "all", original_id, ind.name)
                    await asyncio.sleep(2)
                    
                elif ind.source == "YAHOO":
                    await fetch_and_store_market_data(session, ind.symbol)
                    await asyncio.sleep(1.5)
                    
                elif ind.source == "ECB":
                    await fetch_and_store_ecb_data(session, ind.symbol)
                    await asyncio.sleep(1.5)
                    
                elif ind.source in ["EUROSTAT", "BIS", "IMF", "OECD"]:
                    # این غول‌ها از سیستم پیچیده SDMX استفاده می‌کنند که موتور اختصاصی خودش را می‌طلبد
                    print(f"   ⏳ نیازمند موتور پردازشگر SDMX (در برنامه‌ی توسعه بعدی). عبور...")
                    
                else:
                    print(f"   ⚠️ منبع ناشناخته: {ind.source}")
                    
            except Exception as e:
                print(f"   ❌ خطا در دانلود شاخص {ind.symbol}: {e}")
                print("   🔄 در حال استراحت ۵ ثانیه‌ای برای بازیابی ارتباط...")
                await asyncio.sleep(5)

    print("\n✅ عملیات معدن‌چی با موفقیت به پایان رسید!")

if __name__ == "__main__":
    # امکان دریافت نام منبع از ترمینال (مثلاً: python miner.py FRED)
    source_arg = sys.argv[1] if len(sys.argv) > 1 else None
    
    # اجرای حلقه ناهمگام (Async)
    try:
        asyncio.run(run_miner(source_arg))
    except KeyboardInterrupt:
        print("\n🛑 معدن‌چی با دستور شما (Ctrl+C) متوقف شد. دیتای دانلود شده تا الان، در دیتابیس محفوظ است.")