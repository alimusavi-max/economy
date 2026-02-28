import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

# ساخت موتور ناهمگام دیتابیس (Async Engine)
engine = create_async_engine(
    DATABASE_URL,
    echo=False, # اگر True باشد، تمام کوئری‌های SQL در ترمینال چاپ می‌شود
    future=True
)

# ساخت Session ساز ناهمگام
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# تابع وابستگی (Dependency) برای استفاده در روترهای FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()