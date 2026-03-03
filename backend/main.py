from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
# سرویس‌ها
from services.market_service import fetch_and_store_market_data
from services.fred_service import fetch_and_store_fred_series
from services.discovery_service import discover_fred_category, seed_market_symbols, auto_discover_all_fred
from services.worldbank_service import auto_discover_worldbank_indicators
from services.alphavantage_service import fetch_and_store_alphavantage
from services.imf_service import auto_discover_imf_indicators
from services.oecd_service import auto_discover_oecd_indicators
# تنظیمات دیتابیس و مدل‌ها
from database.database import engine, get_db
from database.models import Base
from services.ecb_service import fetch_and_store_ecb_data, auto_discover_ecb
# ایمپورت روتر دیتا (مسیرهای مربوط به فرانت‌اند)
from routers import data_router, pipeline_router
from sqlalchemy import select
# ایمپورت سیستم زمان‌بندی
from services.scheduler_service import start_scheduler
from database.models import AssetMarketData
# === تابع اصلی کاوشگر جهانی (Spider) ===
async def run_global_scrapers(db: AsyncSession, source: str = "ALL"):
    print(f"شروع عملیات کاوشگر برای منبع: {source}")
    try:
        if source in ["ALL", "WORLDBANK"]:
            await auto_discover_worldbank_indicators(db)
            
        if source in ["ALL", "FRED"]:
            await auto_discover_all_fred(db)
            
        if source in ["ALL", "YAHOO"]:
            from services.discovery_service import seed_market_symbols
            await seed_market_symbols(db)
            
        if source in ["ALL", "ECB"]:
            await auto_discover_ecb(db)

        if source in ["ALL", "IMF"]:
            await auto_discover_imf_indicators(db)

        if source in ["ALL", "OECD"]:
            await auto_discover_oecd_indicators(db)

        print(f"عملیات کاوشگر برای {source} با موفقیت به پایان رسید!")
    except Exception as e:
        print(f"خطا در حین اجرای کاوشگر {source}: {e}")

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
app.include_router(pipeline_router.router)
codex/fix-undefinedcolumnerror-in-indicators-table-o15y0n
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
 main


@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}

@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(str(STATIC_DIR / "index.html"))

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


@app.post("/api/discover/imf")
async def trigger_imf_discovery(
    db: AsyncSession = Depends(get_db)
):
    result = await auto_discover_imf_indicators(db)
    return {"success": True, "new_indicators": result}

@app.post("/api/discover/oecd")
async def trigger_oecd_discovery(
    db: AsyncSession = Depends(get_db)
):
    result = await auto_discover_oecd_indicators(db)
    return {"success": True, "new_indicators": result}

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

@app.post("/api/fetch/alpha/{symbol}")
async def trigger_alpha_fetch(
    symbol: str, 
    asset_type: str = "STOCK", # می تواند STOCK, CRYPTO, FX باشد
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت دیتای بازارهای مالی از Alpha Vantage
    مثال: symbol=IBM , asset_type=STOCK
    """
    result = await fetch_and_store_alphavantage(session=db, symbol=symbol, asset_type=asset_type)
    return result

@app.post("/api/fetch/ecb/{symbol}")
async def trigger_ecb_fetch(
    symbol: str, 
    db: AsyncSession = Depends(get_db)
):
    """دریافت دستی دیتای بانک مرکزی اروپا"""
    result = await fetch_and_store_ecb_data(session=db, symbol=symbol)
    return result

@app.get("/api/market/eur-usd")
async def get_eur_usd_history(db: AsyncSession = Depends(get_db)):
    """دریافت تاریخچه قیمت یورو به دلار برای رسم نمودار"""
    
    # یک کوئری سریع برای گرفتن ۱۰۰ رکورد آخر (یا بیشتر، بسته به نیاز نمودار)
    query = (
        select(AssetMarketData)
        .where(AssetMarketData.symbol == 'EUR/USD')
        .order_by(AssetMarketData.date.desc())
        .limit(100)
    )
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    return {"symbol": "EUR/USD", "data": records}