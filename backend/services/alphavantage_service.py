import os
import requests
import asyncio
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator, AssetMarketData

load_dotenv()
ALPHAVANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

async def fetch_and_store_alphavantage(session: AsyncSession, symbol: str, asset_type: str = "STOCK"):
    """
    دریافت اطلاعات دقیق بازارهای مالی از دیتابیس Alpha Vantage
    asset_type می تواند STOCK (سهام) یا CRYPTO (ارز دیجیتال) یا FX (جفت ارز) باشد.
    """
    print(f"در حال دریافت دیتای {symbol} از Alpha Vantage...")
    
    # تعیین نوع درخواست بر اساس نوع دارایی
    if asset_type == "STOCK":
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=full&apikey={ALPHAVANTAGE_API_KEY}"
        data_key = "Time Series (Daily)"
    elif asset_type == "CRYPTO":
        url = f"https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_DAILY&symbol={symbol}&market=USD&apikey={ALPHAVANTAGE_API_KEY}"
        data_key = "Time Series (Digital Currency Daily)"
    elif asset_type == "FX":
        # برای فارکس نماد باید به شکل EURUSD باشد، ما آن را جدا می‌کنیم
        from_sym = symbol[:3]
        to_sym = symbol[3:] if len(symbol) > 3 else "USD"
        url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={from_sym}&to_symbol={to_sym}&outputsize=full&apikey={ALPHAVANTAGE_API_KEY}"
        data_key = "Time Series FX (Daily)"
    else:
        return {"success": False, "message": "نوع دارایی نامعتبر است."}

    # تلاش برای دریافت دیتا با مکانیزم ضد قطعی
    success = False
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # آلفا ونتیج در صورت رد شدن کلید یا لیمیت شدن پیام ارور در JSON می فرستد
                if "Error Message" in data or "Note" in data:
                    print(f"خطای Alpha Vantage: {data}")
                    return {"success": False, "message": "محدودیت API یا نماد نامعتبر است."}
                if data_key in data:
                    success = True
                    break
            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در دریافت دیتا از Alpha Vantage"}

    time_series = data[data_key]
    
    # ثبت یا آپدیت شناسنامه نماد در دیتابیس
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        indicator = Indicator(
            symbol=symbol.upper(), 
            name=f"{symbol.upper()} ({asset_type})", 
            source="ALPHAVANTAGE", 
            frequency="Daily", 
            update_interval_days=1,
            last_updated=date.today()
        )
        session.add(indicator)
    else:
        indicator.last_updated = date.today()
        session.add(indicator)
    
    await session.commit()
    
    # پردازش و ذخیره رکوردهای قیمتی
    records_to_insert = []
    for date_str, values in time_series.items():
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # کلیدهای دیکشنری در دارایی‌های مختلف متفاوت است
            close_key = next((k for k in values.keys() if 'close' in k.lower()), None)
            vol_key = next((k for k in values.keys() if 'volume' in k.lower()), None)
            
            close_price = float(values[close_key]) if close_key else 0.0
            volume = float(values[vol_key]) if vol_key else 0.0
            
            records_to_insert.append({
                "symbol": symbol.upper(),
                "date": date_obj,
                "close_price": close_price,
                "volume": volume
            })
        except Exception as e:
            continue
            
    if records_to_insert:
        stmt = insert(AssetMarketData).values(records_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'date'])
        result = await session.execute(stmt)
        await session.commit()
        
    return {
        "success": True, 
        "message": f"دیتای {symbol} از Alpha Vantage ذخیره شد.",
        "new_records": result.rowcount
    }