from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from database.database import get_db
from database.models import Indicator, EconomicData, AssetMarketData

router = APIRouter(prefix="/api/data", tags=["Data API"])

@router.get("/symbols/available")
async def get_available_symbols(db: AsyncSession = Depends(get_db)):
    """دریافت تمام نمادهای موجود در دیتابیس برای نمایش در منوی جستجوی فرانت‌اند"""
    results = []
    
    ind_result = await db.execute(select(Indicator))
    indicators = ind_result.scalars().all()
    for ind in indicators:
        results.append({
            "symbol": ind.symbol,
            "name": ind.name,
            "type": "Macro",
            "source": ind.source
        })
        
    mkt_result = await db.execute(select(distinct(AssetMarketData.symbol)))
    market_symbols = mkt_result.scalars().all()
    for sym in market_symbols:
        results.append({
            "symbol": sym,
            "name": f"بازار مالی ({sym})",
            "type": "Market",
            "source": "Yahoo Finance"
        })
        
    return {"symbols": results}

@router.get("/{symbol}")
async def get_economic_data(symbol: str, db: AsyncSession = Depends(get_db)):
    """دریافت دیتای تاریخی یک نماد (چه اقتصاد کلان و چه بازار مالی)"""
    symbol_upper = symbol.upper()
    
    ind_result = await db.execute(select(Indicator).where(Indicator.symbol == symbol_upper))
    indicator = ind_result.scalar_one_or_none()
    
    if indicator:
        data_result = await db.execute(
            select(EconomicData)
            .where(EconomicData.indicator_id == indicator.id)
            .order_by(EconomicData.date.asc())
        )
        records = data_result.scalars().all()
        chart_data = [{"date": str(r.date), "value": r.value} for r in records]
        
        return {
            "indicator": {"name": indicator.name, "symbol": indicator.symbol, "source": indicator.source},
            "total_records": len(chart_data),
            "data": chart_data
        }

    market_result = await db.execute(
        select(AssetMarketData)
        .where(AssetMarketData.symbol == symbol_upper)
        .order_by(AssetMarketData.date.asc())
    )
    market_records = market_result.scalars().all()
    
    if not market_records:
        raise HTTPException(status_code=404, detail="شاخص یا نماد مورد نظر یافت نشد.")
        
    chart_data = [{"date": str(r.date), "value": r.close_price} for r in market_records]
    
    return {
        "indicator": {"name": f"قیمت {symbol_upper}", "symbol": symbol_upper, "source": "Yahoo Finance"},
        "total_records": len(chart_data),
        "data": chart_data
    }