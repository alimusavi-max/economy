from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
# سرویس‌ها
from services.market_service import fetch_and_store_market_data
from services.fred_service import fetch_and_store_fred_series
from services.discovery_service import discover_fred_category, seed_market_symbols, auto_discover_all_fred
from services.worldbank_service import auto_discover_worldbank_indicators

# تنظیمات دیتابیس و مدل‌ها
from database.database import engine, get_db
from database.models import Base

# ایمپورت روتر دیتا (مسیرهای مربوط به فرانت‌اند)
from routers import data_router

# ایمپورت سیستم زمان‌بندی
from services.scheduler_service import start_scheduler

# === تابع اصلی کاوشگر جهانی (Spider) ===
async def run_global_scrapers(db: AsyncSession, source: str = "ALL"):
    """
    این تابع حالا می‌فهمد که باید همه خزنده‌ها را روشن کند یا فقط یک خزنده خاص را.
    """
    print(f"شروع عملیات کاوشگر برای منبع: {source}")
    try:
        if source in ["ALL", "WORLDBANK"]:
            await auto_discover_worldbank_indicators(db)
            
        if source in ["ALL", "FRED"]:
            await auto_discover_all_fred(db)
            
        if source in ["ALL", "YAHOO"]:
            await seed_market_symbols(db) # برای یاهو فعلاً همان لیست اولیه را تزریق می‌کنیم
            
        print(f"عملیات کاوشگر برای {source} با موفقیت به پایان رسید!")
    except Exception as e:
        print(f"خطا در حین اجرای کاوشگر {source}: {e}")
# =======================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("در حال اتصال به دیتابیس و بررسی جداول...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # روشن کردن سیستم زمان‌بندی در پس‌زمینه
    start_scheduler()
    
    yield
    print("سرور در حال خاموش شدن است...")

# اتصال چرخه حیات (lifespan) به اپلیکیشن
app = FastAPI(title="Global Economy Analyzer API", lifespan=lifespan)

# === فعال‌سازی CORS برای ارتباط با فرانت‌اند (Next.js) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === متصل کردن روترها به اپلیکیشن اصلی ===
app.include_router(data_router.router)


@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}

# --- Endpoints برای دریافت و کشف دیتا ---

@app.post("/api/fetch/fred/{series_id}")
async def trigger_fred_fetch(
    series_id: str, 
    name: str, 
    frequency: str = "Monthly", 
    db: AsyncSession = Depends(get_db)
):
    result = await fetch_and_store_fred_series(
        session=db, 
        series_id=series_id.upper(), 
        name=name, 
        frequency=frequency
    )
    return result

@app.post("/api/fetch/market/{symbol}")
async def trigger_market_fetch(
    symbol: str, 
    db: AsyncSession = Depends(get_db)
):
    result = await fetch_and_store_market_data(session=db, symbol=symbol)
    return result

@app.post("/api/discover/fred/{category_id}")
async def trigger_fred_discovery(
    category_id: int, 
    db: AsyncSession = Depends(get_db)
):
    result = await discover_fred_category(session=db, category_id=category_id)
    return result

@app.post("/api/discover/market-seed")
async def trigger_market_seed(
    db: AsyncSession = Depends(get_db)
):
    result = await seed_market_symbols(session=db)
    return result

@app.post("/api/discover/auto-spider")
async def trigger_auto_spider(
    background_tasks: BackgroundTasks, 
    source: Optional[str] = "ALL", # دریافت نام منبع از فرانت‌اند
    db: AsyncSession = Depends(get_db)
):
    """
    روشن کردن موتور کاوشگر بر اساس منبع انتخابی
    """
    # پاس دادن متغیر source به تابع پس‌زمینه
    background_tasks.add_task(run_global_scrapers, db, source)
    
    msg_source = "تمام منابع جهانی" if source == "ALL" else source
    return {
        "success": True, 
        "message": f"موتور کاوشگر برای [{msg_source}] در پس‌زمینه روشن شد! لطفاً چند دقیقه دیگر داشبورد را رفرش کنید."
    }