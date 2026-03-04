from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import engine, get_db
from database.models import AssetMarketData, Base
from routers import data_router, pipeline_router
from services.alphavantage_service import fetch_and_store_alphavantage
from services.bis_service import auto_discover_bis_indicators
from services.discovery_service import auto_discover_all_fred, discover_fred_category, seed_market_symbols
from services.ecb_service import auto_discover_ecb, fetch_and_store_ecb_data
from services.eurostat_service import auto_discover_eurostat
from services.fred_service import fetch_and_store_fred_series
from services.imf_service import auto_discover_imf_indicators
from services.market_service import fetch_and_store_market_data
from services.oecd_service import auto_discover_oecd_indicators
from services.scheduler_service import start_scheduler
from services.worldbank_service import auto_discover_worldbank_indicators


async def run_global_scrapers(db: AsyncSession, source: str = "ALL"):
    print(f"شروع عملیات کاوشگر برای منبع: {source}")
    try:
        if source in ["ALL", "WORLDBANK"]:
            await auto_discover_worldbank_indicators(db)
        if source in ["ALL", "FRED"]:
            await auto_discover_all_fred(db)
        if source in ["ALL", "YAHOO"]:
            await seed_market_symbols(db)
        if source in ["ALL", "ECB"]:
            await auto_discover_ecb(db)
        if source in ["ALL", "IMF"]:
            await auto_discover_imf_indicators(db)
        if source in ["ALL", "OECD"]:
            await auto_discover_oecd_indicators(db)
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

    start_scheduler()
    yield
    print("سرور در حال خاموش شدن است...")


app = FastAPI(title="Global Economy Analyzer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_router.router)
app.include_router(pipeline_router.router)


@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}


@app.post("/api/fetch/fred/{series_id}")
async def trigger_fred_fetch(
    series_id: str,
    name: str,
    frequency: str = "Monthly",
    db: AsyncSession = Depends(get_db),
):
    return await fetch_and_store_fred_series(
        session=db,
        series_id=series_id.upper(),
        name=name,
        frequency=frequency,
    )


@app.post("/api/fetch/market/{symbol}")
async def trigger_market_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_market_data(session=db, symbol=symbol)


@app.post("/api/discover/fred/{category_id}")
async def trigger_fred_discovery(category_id: int, db: AsyncSession = Depends(get_db)):
    return await discover_fred_category(session=db, category_id=category_id)


@app.post("/api/discover/market-seed")
async def trigger_market_seed(db: AsyncSession = Depends(get_db)):
    return await seed_market_symbols(session=db)


@app.post("/api/discover/imf")
async def trigger_imf_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_imf_indicators(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/discover/oecd")
async def trigger_oecd_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_oecd_indicators(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/discover/auto-spider")
async def trigger_auto_spider(
    background_tasks: BackgroundTasks,
    source: Optional[str] = "ALL",
    db: AsyncSession = Depends(get_db),
):
    background_tasks.add_task(run_global_scrapers, db, source)
    msg_source = "تمام منابع جهانی" if source == "ALL" else source
    return {
        "success": True,
        "message": f"موتور کاوشگر برای [{msg_source}] در پس‌زمینه روشن شد! لطفاً چند دقیقه دیگر داشبورد را رفرش کنید.",
    }


@app.post("/api/fetch/alpha/{symbol}")
async def trigger_alpha_fetch(
    symbol: str,
    asset_type: str = "STOCK",
    db: AsyncSession = Depends(get_db),
):
    return await fetch_and_store_alphavantage(session=db, symbol=symbol, asset_type=asset_type)


@app.post("/api/fetch/ecb/{symbol}")
async def trigger_ecb_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_ecb_data(session=db, symbol=symbol)


@app.get("/api/market/eur-usd")
async def get_eur_usd_history(db: AsyncSession = Depends(get_db)):
    query = (
        select(AssetMarketData)
        .where(AssetMarketData.symbol == "EUR/USD")
        .order_by(AssetMarketData.date.desc())
        .limit(100)
    )
    result = await db.execute(query)
    records = result.scalars().all()
    return {"symbol": "EUR/USD", "data": records}
