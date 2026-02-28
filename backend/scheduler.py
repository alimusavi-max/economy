from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.database import AsyncSessionLocal
from services.market_service import fetch_and_store_market_data
from services.fred_service import fetch_and_store_fred_series
import asyncio
# ساخت یک نمونه از زمان‌بند ناهمگام
scheduler = AsyncIOScheduler()

async def update_daily_data():
    """این تابع وظیفه دارد دیتابیس را با آخرین اطلاعات روز آپدیت کند"""
    print("🔄 در حال شروع آپدیت خودکار روزانه داده‌ها...")
    
    # باز کردن یک اتصال جدید به دیتابیس برای کارهای پس‌زمینه
    async with AsyncSessionLocal() as session:
        try:
            # ۱. آپدیت بازارهای مالی (بیت‌کوین، طلا، شاخص بورس)
            await fetch_and_store_market_data(session, "BTC-USD")
            await fetch_and_store_market_data(session, "GC=F")  # Gold
            await fetch_and_store_market_data(session, "^GSPC") # S&P 500
            
            # ۲. آپدیت شاخص‌های اقتصاد کلان
            await fetch_and_store_fred_series(session, "CPIAUCSL", "US Inflation", "Monthly")
            await fetch_and_store_fred_series(session, "IRNBCA", "Current Account Balance", "Monthly")
            
            print("✅ آپدیت خودکار تمام نمادها با موفقیت انجام شد.")
        except Exception as e:
            print(f"❌ خطا در آپدیت خودکار: {e}")

def start_scheduler():
    """روشن کردن موتور زمان‌بندی"""
    # تنظیم برای اجرا در ساعت 08:00 صبح هر روز
    # برای تست کردن می‌توانی از این حالت استفاده کنی: scheduler.add_job(update_daily_data, 'interval', minutes=1)
    scheduler.add_job(update_daily_data, 'cron', hour=8, minute=0)
    scheduler.start()
    print("⏰ موتور زمان‌بندی (Scheduler) روشن شد و منتظر زمان مقرر است.")