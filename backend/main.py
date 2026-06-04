from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import AsyncSessionLocal, engine, get_db
from database.models import AssetMarketData, Base

from routers import data_router, pipeline_router, user_router
from services.alphavantage_service import fetch_and_store_alphavantage
from services.bis_service import auto_discover_bis_indicators
from services.dbnomics_service import auto_discover_all_central_banks, auto_discover_central_bank, fetch_and_store_dbnomics_data
from services.discovery_service import auto_discover_all_fred, discover_fred_category, seed_market_symbols
from services.ecb_service import auto_discover_ecb, fetch_and_store_ecb_data
from services.eurostat_service import auto_discover_eurostat
from services.fao_service import auto_discover_fao, fetch_and_store_fao_data
from services.fred_service import fetch_and_store_fred_series
from services.ilo_service import auto_discover_ilo, fetch_and_store_ilo_data
from services.imf_service import auto_discover_imf_indicators
from services.market_service import fetch_and_store_market_data
from services.oecd_service import auto_discover_oecd_indicators
from services.scheduler_service import start_scheduler
from services.treasury_service import auto_discover_treasury, fetch_and_store_treasury_data
from services.un_service import auto_discover_un, fetch_and_store_un_data
from services.worldbank_service import auto_discover_worldbank_indicators
from sqlalchemy import text


async def ensure_backward_compatible_schema():
    """Adds missing columns for old databases that were created before newer model fields."""
    if engine is None:
        return

    async with engine.begin() as conn:
        dialect = conn.dialect.name

        if dialect == "postgresql":
            await conn.execute(
                text(
                    "ALTER TABLE indicators "
                    "ADD COLUMN IF NOT EXISTS dbnomics_provider VARCHAR(20)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_indicators_dbnomics_provider "
                    "ON indicators (dbnomics_provider)"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE indicators "
                    "ADD COLUMN IF NOT EXISTS tags VARCHAR(200)"
                )
            )


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
        if source in ["ALL", "ILO"]:
            await auto_discover_ilo(db)
        if source in ["ALL", "TREASURY"]:
            await auto_discover_treasury(db)
        if source in ["ALL", "FAO"]:
            await auto_discover_fao(db)
        if source in ["ALL", "UN"]:
            await auto_discover_un(db)
        print(f"عملیات کاوشگر برای {source} با موفقیت به پایان رسید!")
    except Exception as e:
        print(f"خطا در حین اجرای کاوشگر {source}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine is not None:
        print("در حال اتصال به دیتابیس و بررسی جداول...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await ensure_backward_compatible_schema()
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
app.include_router(user_router.router)


@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}


@app.get("/api/health")
async def health_check():
    from datetime import datetime
    return {
        "status": "healthy",
        "database": engine is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }


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
):
    async def _run():
        async with AsyncSessionLocal() as db:
            await run_global_scrapers(db, source)

    background_tasks.add_task(_run)
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



@app.post("/api/discover/dbnomics")
async def trigger_dbnomics_discovery(bank_code: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if bank_code:
        count = await auto_discover_central_bank(db, bank_code.upper())
        return {"success": True, "provider": bank_code.upper(), "new_indicators": count}

    count = await auto_discover_all_central_banks(db)
    return {"success": True, "provider": "ALL", "new_indicators": count}


@app.post("/api/fetch/dbnomics/{symbol}")
async def trigger_dbnomics_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_dbnomics_data(session=db, symbol=symbol.upper())


@app.post("/api/discover/ilo")
async def trigger_ilo_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_ilo(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/fetch/ilo/{symbol}")
async def trigger_ilo_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_ilo_data(session=db, symbol=symbol.upper())


@app.post("/api/discover/treasury")
async def trigger_treasury_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_treasury(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/fetch/treasury/{symbol}")
async def trigger_treasury_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_treasury_data(session=db, symbol=symbol.upper())


@app.post("/api/discover/fao")
async def trigger_fao_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_fao(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/fetch/fao/{symbol}")
async def trigger_fao_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_fao_data(session=db, symbol=symbol.upper())


@app.post("/api/discover/un")
async def trigger_un_discovery(db: AsyncSession = Depends(get_db)):
    result = await auto_discover_un(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/fetch/un/{symbol}")
async def trigger_un_fetch(symbol: str, db: AsyncSession = Depends(get_db)):
    return await fetch_and_store_un_data(session=db, symbol=symbol.upper())


@app.post("/api/discover/bis")
async def trigger_bis_discovery(db: AsyncSession = Depends(get_db)):
    from services.bis_service import auto_discover_bis_indicators
    result = await auto_discover_bis_indicators(db)
    return {"success": True, "new_indicators": result}


@app.post("/api/discover/eurostat")
async def trigger_eurostat_discovery(db: AsyncSession = Depends(get_db)):
    from services.eurostat_service import auto_discover_eurostat
    result = await auto_discover_eurostat(db)
    return {"success": True, "new_indicators": result}
