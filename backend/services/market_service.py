import yfinance as yf
import asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database.models import AssetMarketData, Indicator

async def fetch_and_store_market_data(session: AsyncSession, symbol: str):
    """
    دریافت دیتای تاریخی یک نماد مالی واقعی از یاهو فایننس
    و ثبت خودکار آن در داشبورد
    """
    print(f"در حال دریافت دیتای بازار برای نماد {symbol}...")
    
    ticker = yf.Ticker(symbol)
    hist = await asyncio.to_thread(ticker.history, period="max")
    
    if hist.empty:
        return {"success": False, "message": f"دیتایی برای نماد {symbol} یافت نشد. آیا مطمئنید این نماد در سایت وجود دارد؟"}
        
    # --- بخش جدید: ثبت نماد واقعی در داشبورد (جدول Indicator) ---
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        # تلاش برای پیدا کردن نام واقعی شرکت از سایت
        try:
            info = await asyncio.to_thread(lambda: ticker.info)
            company_name = info.get("shortName", symbol.upper()) if isinstance(info, dict) else symbol.upper()
        except:
            company_name = symbol.upper()
            
        indicator = Indicator(
            symbol=symbol.upper(), 
            name=company_name, 
            source="YAHOO", 
            frequency="Daily", 
            update_interval_days=1,
            last_updated=date.today()
        )
        session.add(indicator)
        await session.commit()
    else:
        indicator.last_updated = date.today()
        session.add(indicator)
        await session.commit()
    # -------------------------------------------------------------
        
    records_to_insert = []
    for index, row in hist.iterrows():
        date_obj = index.date() if hasattr(index, 'date') else index
        
        records_to_insert.append({
            "symbol": symbol.upper(),
            "date": date_obj,
            "close_price": float(row["Close"]),
            "volume": float(row["Volume"])
        })
        
    stmt = insert(AssetMarketData).values(records_to_insert)
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'date'])
    
    result = await session.execute(stmt)
    await session.commit()
    
    return {
        "success": True, 
        "message": f"دیتا با موفقیت دریافت و ذخیره شد.",
        "symbol": symbol.upper(),
        "total_records_fetched": len(records_to_insert),
        "new_records_saved": result.rowcount
    }