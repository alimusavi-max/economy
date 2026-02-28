from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from scheduler import start_scheduler

from services.market_service import fetch_and_store_market_data
from database.database import engine, get_db
from database.models import Base
from services.fred_service import fetch_and_store_fred_series
from routers.data_router import router as data_router # <--- اضافه شد
from routers.pipeline_router import router as pipeline_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("در حال اتصال به دیتابیس و بررسی جداول...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_scheduler()  # <--- اضافه شد
    yield

app = FastAPI(title="Global Economy Analyzer API")

# <--- اضافه شدن مجوز CORS برای فرانت‌اند --->
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# <--- وصل کردن روتر دیتا به بک‌اند --->
app.include_router(data_router)
app.include_router(pipeline_router)
@app.get("/")
async def root():
    return {"message": "موتور تحلیل اقتصاد جهانی روشن است 🚀"}

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