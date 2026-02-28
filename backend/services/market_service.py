import yfinance as yf
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from database.models import AssetMarketData

async def fetch_and_store_market_data(session: AsyncSession, symbol: str):
    """
    دریافت دیتای تاریخی یک نماد مالی (سهام، جفت ارز، کریپتو) از یاهو فایننس
    و ذخیره هوشمند در دیتابیس
    """
    print(f"در حال دریافت دیتای بازار برای نماد {symbol}...")
    
    # از آنجایی که yfinance ناهمگام (Async) نیست، آن را در یک Thread جداگانه اجرا می‌کنیم 
    # تا در زمان دانلود دیتای سنگین، کل سرور ما قفل نشود
    ticker = yf.Ticker(symbol)
    hist = await asyncio.to_thread(ticker.history, period="max") # دریافت کل تاریخچه ممکن
    
    if hist.empty:
        return {"success": False, "message": f"دیتایی برای نماد {symbol} یافت نشد. آیا نماد درست است؟"}
        
    records_to_insert = []
    # تبدیل داده‌های دریافت شده به فرمت دیتابیس خودمان
    for index, row in hist.iterrows():
        # گاهی دیتای یاهو شامل ساعت هم هست، ما فقط تاریخ (Date) را می‌خواهیم
        date_obj = index.date() if hasattr(index, 'date') else index
        
        records_to_insert.append({
            "symbol": symbol.upper(),
            "date": date_obj,
            "close_price": float(row["Close"]),
            "volume": float(row["Volume"])
        })
        
    # ذخیره در دیتابیس با قابلیت رد کردن داده‌های تکراری (ON CONFLICT DO NOTHING)
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