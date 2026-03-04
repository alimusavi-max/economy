import os
import requests
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator
from dotenv import load_dotenv
import pandas as pd  # این خط وجود نداره ولی در seed_market_symbols استفاده شده


load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")


if not FRED_API_KEY:
    print("هشدار: کلید FRED_API_KEY در فایل .env پیدا نشد!")
# ==========================================
# ۱. توابع قبلی (برای تزریق دستی و تکی)
# ==========================================
async def discover_fred_category(session: AsyncSession, category_id: int):
    # (کد قبلی شما برای دریافت یک دسته خاص)
    url = f"https://api.stlouisfed.org/fred/category/series?category_id={category_id}&api_key={FRED_API_KEY}&file_type=json"
    response = requests.get(url)
    if response.status_code != 200: return {"success": False}
    series_list = response.json().get('seriess', [])
    records = [{"symbol": s['id'], "name": s['title'], "source": "FRED", "frequency": s.get('frequency_short', 'M'), "update_interval_days": 30} for s in series_list]
    if records:
        stmt = insert(Indicator).values(records).on_conflict_do_nothing(index_elements=['symbol'])
        await session.execute(stmt)
        await session.commit()
    return {"success": True}

async def seed_market_symbols(session: AsyncSession):
    """
    کاوشگر عمیق بازارهای مالی: استخراج زنده ۵۰۰ شرکت برتر آمریکا + فارکس + کریپتو
    """
    print("🚀 در حال استخراج دیتای S&P 500 از ویکی‌پدیا و بازارهای جهانی...")
    records_to_insert = []
    
    # ۱. استخراج اتوماتیک ۵۰۰ شرکت برتر بورس آمریکا (S&P 500)
    try:
        # با یک خط کد، تمام جداول صفحه ویکی‌پدیا را می‌خوانیم!
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        sp500_df = tables[0]
        
        for index, row in sp500_df.iterrows():
            symbol = str(row['Symbol']).replace('.', '-') # تبدیل نمادهایی مثل BRK.B به BRK-B (استاندارد یاهو)
            records_to_insert.append({
                "symbol": symbol,
                "name": f"S&P 500: {row['Security']} ({row['GICS Sector']})",
                "source": "YAHOO",
                "frequency": "Daily",
                "update_interval_days": 1
            })
    except Exception as e:
        print(f"❌ خطا در دریافت لیست S&P 500: {e}")

    # ۲. لیست ارزهای دیجیتال اصلی (Top Crypto)
    cryptos = [
        ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("BNB-USD", "Binance Coin"),
        ("SOL-USD", "Solana"), ("XRP-USD", "Ripple"), ("ADA-USD", "Cardano"),
        ("DOGE-USD", "Dogecoin"), ("TRX-USD", "TRON"), ("LINK-USD", "Chainlink")
    ]
    for c in cryptos:
        records_to_insert.append({"symbol": c[0], "name": f"Crypto: {c[1]}", "source": "YAHOO", "frequency": "Daily", "update_interval_days": 1})

    # ۳. لیست جفت‌ارزهای جهانی (Forex)
    forex = [
        ("EURUSD=X", "EUR/USD"), ("GBPUSD=X", "GBP/USD"), ("JPY=X", "USD/JPY"),
        ("EURGBP=X", "EUR/GBP"), ("CAD=X", "USD/CAD"), ("AUDUSD=X", "AUD/USD"),
        ("CHF=X", "USD/CHF"), ("CNY=X", "USD/CNY"), ("IRR=X", "USD/IRR")
    ]
    for f in forex:
        records_to_insert.append({"symbol": f[0], "name": f"Forex: {f[1]}", "source": "YAHOO", "frequency": "Daily", "update_interval_days": 1})

    # تزریق یک‌جای بیش از ۵۰۰ نماد به دیتابیس
    if records_to_insert:
        stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=['symbol'])
        result = await session.execute(stmt)
        await session.commit()
        print(f"🎉 کاوشگر بازار تمام شد! {result.rowcount} نماد مالی در دیتابیس ثبت شد.")
        return result.rowcount
    
    return 0


# ==========================================
# ۲. خزنده اتوماتیک و ضد قطعی FRED (جدید)
# ==========================================
async def auto_discover_all_fred(session: AsyncSession):
    """
    کاوشگر عنکبوتی FRED با مکانیزم ضد قطعی و تلاش مجدد (Retry)
    """
    print("در حال شروع کاوشگر اتوماتیک FRED...")
    max_retries = 3
    total_added = 0
    
    # مرحله اول: استخراج ۱۰۰ تگ (موضوع) پرکاربرد اقتصاد جهانی
    tags_url = f"https://api.stlouisfed.org/fred/tags?api_key={FRED_API_KEY}&file_type=json&order_by=popularity&sort_order=desc&limit=100"
    
    tags_success = False
    for attempt in range(max_retries):
        try:
            tags_resp = requests.get(tags_url, timeout=15)
            if tags_resp.status_code == 200:
                tags_success = True
                break
            else:
                await asyncio.sleep(5)
        except Exception as e:
            print(f"قطعی در دریافت تگ‌های FRED. تلاش مجدد...")
            await asyncio.sleep(10)
            
    if not tags_success:
        print("خطا در دریافت تگ‌های اصلی FRED. کاوشگر FRED متوقف شد.")
        return 0
        
    tags_data = tags_resp.json().get('tags', [])
    
    # مرحله دوم: دریافت هزاران شاخص برای هر تگ کشف شده
    for tag in tags_data:
        tag_name = tag['name']
        print(f"در حال کاوش شاخص‌های تگ FRED: {tag_name} ...")
        
        series_url = f"https://api.stlouisfed.org/fred/tags/series?tag_names={tag_name}&api_key={FRED_API_KEY}&file_type=json&order_by=popularity&sort_order=desc&limit=1000"
        
        series_success = False
        for attempt in range(max_retries):
            try:
                series_resp = requests.get(series_url, timeout=15)
                if series_resp.status_code == 200:
                    series_success = True
                    break
                else:
                    await asyncio.sleep(5)
            except Exception as e:
                await asyncio.sleep(10)
                
        if not series_success:
            print(f"رد شدن از تگ '{tag_name}' به دلیل خطای مکرر شبکه.")
            continue # رفتن سراغ تگ بعدی
            
        series_list = series_resp.json().get('seriess', [])
        records_to_insert = []
        
        for series in series_list:
            records_to_insert.append({
                "symbol": series['id'].upper(),
                "name": series['title'][:250], # برش نام‌های خیلی طولانی برای جلوگیری از خطای دیتابیس
                "source": "FRED",
                "frequency": series.get('frequency_short', 'M'),
                "update_interval_days": 30 # آپدیت ماهانه برای داده‌های کلان کافیست
            })
            
        if records_to_insert:
            stmt = insert(Indicator).values(records_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=['symbol'])
            result = await session.execute(stmt)
            await session.commit()
            total_added += result.rowcount
            
        # یک مکث کوتاه برای جلوگیری از مسدود شدن IP توسط سیستم امنیتی FRED
        await asyncio.sleep(1.5) 
        
    print(f"کاوشگر FRED با موفقیت به پایان رسید! {total_added} شاخص جدید ثبت شد.")
    return total_added