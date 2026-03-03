import os
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
AsyncSessionLocal = None

if DATABASE_URL:
    # سازگاری با URLهای قدیمی Heroku/Postgres
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    # ساخت موتور ناهمگام دیتابیس (Async Engine)
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # اگر True باشد، تمام کوئری‌های SQL در ترمینال چاپ می‌شود
        future=True,
    )

    # ساخت Session ساز ناهمگام
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
else:
    print("هشدار: DATABASE_URL در .env تنظیم نشده است؛ قابلیت‌های دیتابیس غیرفعال هستند.")


# تابع وابستگی (Dependency) برای استفاده در روترهای FastAPI
async def get_db():
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set DATABASE_URL in backend/.env",
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
