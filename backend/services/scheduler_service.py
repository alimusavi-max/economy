import asyncio
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from database.database import AsyncSessionLocal
from database.models import Indicator
from services.fred_service import fetch_and_store_fred_series

async def check_and_update_stale_data():
    """
    این تابع دیتابیس را می‌گردد و شاخص‌هایی که از زمان آپدیتشان گذشته است را پیدا کرده و آپدیت می‌کند.
    """
    print(f"[{date.today()}] شروع بررسی دوره‌ای برای آپدیت دیتاهای قدیمی...")
    
    async with AsyncSessionLocal() as session:
        # دریافت تمام شاخص‌های ثبت شده
        result = await session.execute(select(Indicator))
        indicators = result.scalars().all()
        
        today = date.today()
        
        for ind in indicators:
            # اگر تاحالا آپدیت نشده (None) یا از زمان آپدیتش گذشته است:
            if ind.last_updated is None or (today - ind.last_updated).days >= ind.update_interval_days:
                print(f"شناسه {ind.symbol} نیاز به آپدیت دارد. آخرین آپدیت: {ind.last_updated}")
                
                # فراخوانی سرویس برای آپدیت
                if ind.source == "FRED":
                    await fetch_and_store_fred_series(
                        session=session,
                        series_id=ind.symbol,
                        name=ind.name,
                        frequency=ind.frequency or "Monthly"
                    )
                
                # یک وقفه کوتاه (Rate Limiting) برای جلوگیری از مسدود شدن توسط API
                await asyncio.sleep(2) 

def start_scheduler():
    scheduler = AsyncIOScheduler()
    
    # تنظیم اجرای تابع بالا برای هر روز ساعت 2 بامداد
    # برای تست کردن می‌توانید به جای trigger='cron' از trigger='interval', minutes=1 استفاده کنید
    scheduler.add_job(check_and_update_stale_data, trigger='cron', hour=2, minute=0)
    
    scheduler.start()
    print("سیستم زمان‌بندی (Scheduler) با موفقیت راه‌اندازی شد.")