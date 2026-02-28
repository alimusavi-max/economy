from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from services.market_service import fetch_and_store_market_data
from database.database import engine, get_db
from database.models import Base
from services.fred_service import fetch_and_store_fred_series

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("در حال اتصال به دیتابیس و بررسی جداول...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Global Economy Analyzer API")

@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}

# --- Endpoint جدید برای دریافت دستی دیتا ---
@app.post("/api/fetch/fred/{series_id}")
async def trigger_fred_fetch(
    series_id: str, 
    name: str, 
    frequency: str = "Monthly", 
    db: AsyncSession = Depends(get_db)
):
    """
    این آدرس دیتا را از FRED می‌گیرد و در دیتابیس ذخیره می‌کند.
    مثال: series_id = IRNBCA , name = Current Account Balance
    """
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
    """
    این آدرس دیتای بازارهای مالی را می‌گیرد.
    مثال نمادها: 
    AAPL (اپل) ، ^GSPC (شاخص S&P 500) ، GC=F (طلا) ، BTC-USD (بیت‌کوین)
    """
    result = await fetch_and_store_market_data(session=db, symbol=symbol)
    return result