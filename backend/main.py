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
from services.eurostat_service import auto_discover_eurostat
# ایمپورت سیستم زمان‌بندی
from services.scheduler_service import start_scheduler
from database.models import AssetMarketData
from services.bis_service import auto_discover_bis_indicators

from fastapi import HTTPException
from typing import List

# ایمپورت‌های دیتابیس شما (ممکن است در فایل شما کمی متفاوت باشد، تنظیمش کنید)
from database.database import AsyncSessionLocal
from database.models import Indicator, EconomicData
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
            
        # --- کاوشگر جدید BIS اضافه شد ---
        if source in ["ALL", "BIS"]:
            await auto_discover_bis_indicators(db)
            
        if source in ["ALL", "EUROSTAT"]:
            await auto_discover_eurostat(db)

        print(f"عملیات کاوشگر برای {source} با موفقیت به پایان رسید!")
    except Exception as e:
        print(f"خطا در حین اجرای کاوشگر {source}: {e}")
        
@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine is not None:
        print("در حال اتصال به دیتابیس و بررسی جداول...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        print("هشدار: اتصال دیتابیس برقرار نشد؛ سرور بدون قابلیت‌های دیتابیس اجرا می‌شود.")

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

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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






app = FastAPI(title="Macro Economy Lab API")

# تابع وابستگی برای گرفتن سشن دیتابیس
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        
@app.get("/api/indicators")
async def get_indicators(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).order_by(Indicator.source, Indicator.symbol))
    indicators = result.scalars().all()
    return indicators

# ۲. مسیر دریافت دیتای تاریخی یک شاخص خاص (برای رسم چارت)
@app.get("/api/data/{indicator_id}")
async def get_indicator_data(indicator_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EconomicData)
        .where(EconomicData.indicator_id == indicator_id)
        .order_by(EconomicData.date)
    )
    data = result.scalars().all()
    
    if not data:
        raise HTTPException(status_code=404, detail="دیتایی برای این شاخص یافت نشد.")
        
    # فرمت کردن دیتا برای کتابخانه‌های چارت فرانت‌اند (مثل Recharts یا TradingView)
    chart_data = [{"date": str(row.date), "value": row.value} for row in data]
    return chart_data

# ۳. 🧪 موتور آزمایشگاه: ترکیب دو شاخص با عملیات ریاضی (جمع، تفریق، ضرب، تقسیم)
@app.get("/api/lab/combine")
async def combine_indicators(
    id1: int, 
    id2: int, 
    operation: str, # "add", "sub", "mul", "div"
    db: AsyncSession = Depends(get_db)
):
    # دریافت دیتای هر دو شاخص
    data1 = await get_indicator_data(id1, db)
    data2 = await get_indicator_data(id2, db)
    
    # تبدیل لیست‌ها به دیکشنری بر اساس تاریخ برای تطبیق (Alignment) زمان‌ها
    dict1 = {item["date"]: item["value"] for item in data1}
    dict2 = {item["date"]: item["value"] for item in data2}
    
    # پیدا کردن تاریخ‌های مشترک
    common_dates = sorted(list(set(dict1.keys()) & set(dict2.keys())))
    
    combined_data = []
    for date_str in common_dates:
        v1 = dict1[date_str]
        v2 = dict2[date_str]
        
        try:
            if operation == "add": result = v1 + v2
            elif operation == "sub": result = v1 - v2
            elif operation == "mul": result = v1 * v2
            elif operation == "div": result = v1 / v2 if v2 != 0 else 0
            else: raise HTTPException(status_code=400, detail="عملیات نامعتبر است")
            
            combined_data.append({"date": date_str, "value": round(result, 4)})
        except Exception:
            continue
            
    return combined_data