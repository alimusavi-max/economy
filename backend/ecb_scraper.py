import pandas as pd
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

# آدرس اتصال به دیتابیس داکر (دقیقاً همان پورت ۵۴۳۳)
DATABASE_URL = "postgresql+asyncpg://postgres:admin@localhost:5433/economy-db"

async def fetch_and_insert_ecb_data():
    print("🌍 در حال اتصال به سرورهای بانک مرکزی اروپا (ECB)...")
    
    # آدرس رسمی API بانک مرکزی اروپا برای دریافت دیتای روزانه یورو به دلار (از 1999 تا الان)
    ecb_url = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata"
    
    try:
        # دانلود مستقیم دیتا و تبدیل به دیتافریم پانداز
        df = pd.read_csv(ecb_url)
        print(f"✅ دانلود موفقیت‌آمیز! {len(df)} رکورد تاریخی دریافت شد.")
        
        # مرتب‌سازی و آماده‌کردن دیتا برای دیتابیس ما
        df = df[['TIME_PERIOD', 'OBS_VALUE']].copy()
        df.rename(columns={'TIME_PERIOD': 'date', 'OBS_VALUE': 'close_price'}, inplace=True)
        
        # --- رفع مشکل فرمت تاریخ و دیتای کثیف (روزهای تعطیل) ---
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
        df = df.dropna() # حذف روزهایی که بانک تعطیل بوده و قیمت ندارند
        # -----------------------------------------------------
        
        df['symbol'] = 'EUR/USD'
        df['volume'] = 0.0  # بازار ارز حجم متمرکز ندارد
        
        # تبدیل دیتافریم به لیستی از دیکشنری‌ها برای تزریق فوق‌سریع
        records = df.to_dict(orient='records')
        
        print("🚀 در حال تزریق میلیاردها میلی‌ثانیه دیتا به موتور TimescaleDB...")
        
        # اتصال به دیتابیس و تزریق گروهی (Bulk Insert)
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            # استفاده از دستور خام SQL برای دور زدن محدودیت‌های سرعت
            query = text("""
                INSERT INTO asset_market_data (symbol, date, close_price, volume)
                VALUES (:symbol, :date, :close_price, :volume)
                ON CONFLICT (id, date) DO NOTHING;
            """)
            await conn.execute(query, records)
            
        print("🎉 بوم! تمام دیتاها با موفقیت در دیتابیس تایم‌سری ذخیره شدند!")
        
    except Exception as e:
        print(f"❌ خطایی رخ داد: {e}")

# اجرای توابع غیرهمزمان (Async)
if __name__ == "__main__":
    asyncio.run(fetch_and_insert_ecb_data())