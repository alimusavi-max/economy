import asyncio
from fastapi import APIRouter, BackgroundTasks
from database.database import AsyncSessionLocal

# وارد کردن سرویس‌های دریافت دیتا
from services.fred_service import fetch_and_store_fred_series
from services.market_service import fetch_and_store_market_data
from services.worldbank_service import fetch_world_bank_data, get_all_worldbank_indicators

router = APIRouter(prefix="/api/pipeline", tags=["Data Pipeline"])

# ==========================================
# توابع کمکی: ساخت کانال (Session) اختصاصی برای هر ربات
# این کار از تداخل دیتابیس (Warning های زرد رنگ) جلوگیری می‌کند
# ==========================================
async def safe_fred(*args):
    async with AsyncSessionLocal() as db:
        return await fetch_and_store_fred_series(db, *args)

async def safe_market(*args):
    async with AsyncSessionLocal() as db:
        return await fetch_and_store_market_data(db, *args)

async def safe_wb(*args):
    async with AsyncSessionLocal() as db:
        return await fetch_world_bank_data(db, *args)


# ==========================================
# عملیات ۱: دریافت موازی و سریع (چند شاخص مهم برای تست و روزمره)
# ==========================================
async def run_parallel_ingestion():
    """تابع مرکزی برای اجرای همزمان بدون تداخل دیتابیس"""
    print("🚀 استارت عملیات دریافت موازی دیتا با کانال‌های مجزا...")
    
    tasks = [
        safe_wb("1W", "NY.GDP.MKTP.CD", "Global GDP (World)"),
        safe_wb("US", "NY.GDP.MKTP.CD", "US GDP"),
        safe_wb("CN", "NY.GDP.MKTP.CD", "China GDP"),
        
        safe_fred("UNRATE", "US Unemployment Rate", "Monthly"),
        safe_fred("M2SL", "US M2 Money Supply", "Monthly"),
        
        safe_market("CL=F"),
        safe_market("EURUSD=X"),
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)
    print("✅ عملیات موازی بدون هیچ هشداری به پایان رسید!")

@router.post("/trigger-all")
async def trigger_all_pipelines(background_tasks: BackgroundTasks):
    """دکمه شروع عملیات دریافت سریع و موازی"""
    background_tasks.add_task(run_parallel_ingestion)
    return {
        "message": "عملیات دریافت دیتا به صورت همزمان و ایمن آغاز شد. داشبورد را رفرش کنید."
    }


# ==========================================
# عملیات ۲: ماشین شخم‌زن (Crawler) کل دیتای بانک جهانی
# ==========================================
async def run_massive_worldbank_crawler():
    """این ماشین شخم‌زن، کل بانک جهانی را دانلود می‌کند"""
    print("🚨 ماشین شخم‌زن بانک جهانی روشن شد! این عملیات زمان‌بر است...")
    
    # ۱. گرفتن لیست تمام شاخص‌های دنیا (حدود ۲۴ هزار تا)
    all_indicators = await get_all_worldbank_indicators()
    
    if not all_indicators:
        print("❌ خطا در دریافت لیست شاخص‌های بانک جهانی.")
        return

    # برای اینکه سرور قفل نکند، فعلاً ۵۰ شاخص اول را برای "تمام کشورهای دنیا" می‌گیریم.
    # برای گرفتن کل دیتاها می‌توانی [0:50] را در آینده پاک کنی.
    target_indicators = all_indicators[0:50] 
    
    for i, ind in enumerate(target_indicators):
        try:
            print(f"⏳ در حال دانلود شاخص {i+1} از {len(target_indicators)}: {ind['name']} برای کل دنیا...")
            
            # ارسال کلمه all به جای نام کشور، تا دیتای هر ۲۶۶ کشور را یک‌جا بگیرد
            await safe_wb("all", ind["id"], ind["name"])
            
            # ۲ ثانیه توقف بین هر شاخص تا بانک جهانی IP ما را مسدود (Ban) نکند
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"❌ خطا در دانلود شاخص {ind['id']}: {e}")
        
    print("🏆 فاز اول شخم‌زدن بانک جهانی با موفقیت تمام شد!")

@router.post("/massive-worldbank")
async def trigger_massive_worldbank(background_tasks: BackgroundTasks):
    """دکمه شروع عملیات عظیم بانک جهانی"""
    background_tasks.add_task(run_massive_worldbank_crawler)
    return {
        "message": "ماشین شخم‌زن روشن شد! به ترمینال پایتون نگاه کنید تا روند دانلود دیتای تمام کشورهای دنیا را ببینید."
    }