import pandas as pd
import asyncio
import httpx
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# خواندن اتوماتیک کلید API و آدرس دیتابیس از فایل .env
load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

async def fetch_and_insert_fred_data(series_id, series_name):
    print(f"🦅 در حال دریافت دیتای {series_name} ({series_id}) از فدرال رزرو آمریکا...")
    
    # آدرس API بانک FRED
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=20.0)
            data = response.json()
            
        df = pd.DataFrame(data['observations'])
        print(f"✅ دانلود موفق! {len(df)} رکورد برای {series_id} دریافت شد.")
        
        # تمیز کردن دیتا (FRED گاهی برای روزهای تعطیل نقطه '.' می‌گذارد)
        df = df[df['value'] != '.']
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['value'] = pd.to_numeric(df['value'])
        df['symbol'] = series_id
        
        # آماده‌سازی برای تزریق به جدول indicators
        records = df[['symbol', 'date', 'value']].to_dict(orient='records')
        
        # اتصال به دیتابیس
        engine = create_async_engine(DATABASE_URL)
        
        # عملیات ۱: ساخت جدول (در یک تراکنش مستقل و امن)
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS indicators (
                    symbol VARCHAR(50) NOT NULL,
                    date DATE NOT NULL,
                    value DOUBLE PRECISION,
                    PRIMARY KEY (symbol, date)
                );
            """))
            
        # عملیات ۲: اجرای جادوی تایم‌سری (در تراکنش مستقل دوم)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT create_hypertable('indicators', 'date', if_not_exists => TRUE);"))
        except Exception as e:
            # اگر از قبل تایم‌سری شده باشد یا خطای جزئی بدهد، از آن عبور می‌کنیم
            pass 
            
        # عملیات ۳: تزریق فوق‌سریع دیتا (در تراکنش مستقل سوم)
        async with engine.begin() as conn:
            query = text("""
                INSERT INTO indicators (symbol, date, value)
                VALUES (:symbol, :date, :value)
                ON CONFLICT (symbol, date) DO NOTHING;
            """)
            await conn.execute(query, records)
            
        print(f"🎉 بوم! دیتای {series_name} با موفقیت در دیتابیس تایم‌سری نشست!\n")
        
    except Exception as e:
        print(f"❌ خطایی در دریافت {series_id} رخ داد: {e}\n")

async def main():
    # دریافت همزمان حجم پول و نرخ بیکاری
    await fetch_and_insert_fred_data("M2SL", "حجم پول آمریکا")
    await fetch_and_insert_fred_data("UNRATE", "نرخ بیکاری آمریکا")

if __name__ == "__main__":
    asyncio.run(main())