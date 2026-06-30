"""منطق مرکزی دریافت داده برای هر شاخص بر اساس منبع آن.

این ماژول جلوی تکرار شدن منطق dispatch در scheduler، bulk-refresh و
refresh-now را می‌گیرد و یک نقطه‌ی واحد برای همه‌ی منابع فراهم می‌کند.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Indicator
from services.alphavantage_service import fetch_and_store_alphavantage
from services.bis_service import fetch_and_store_bis_data
from services.dbnomics_service import fetch_and_store_dbnomics_data
from services.ecb_service import fetch_and_store_ecb_data
from services.eurostat_service import fetch_and_store_eurostat_data
from services.fao_service import fetch_and_store_fao_data
from services.fred_service import fetch_and_store_fred_series
from services.ilo_service import fetch_and_store_ilo_data
from services.imf_service import fetch_and_store_imf_data
from services.market_service import fetch_and_store_market_data
from services.oecd_service import fetch_and_store_oecd_data
from services.treasury_service import fetch_and_store_treasury_data
from services.un_service import fetch_and_store_un_data
from services.worldbank_service import fetch_world_bank_data

# منابعی که دریافت مستقیم داده برایشان پشتیبانی می‌شود
SUPPORTED_FETCH_SOURCES = {
    "FRED", "YAHOO", "WORLDBANK", "ECB", "DBNOMICS", "IMF", "OECD",
    "BIS", "EUROSTAT", "ALPHAVANTAGE", "ILO", "TREASURY", "FAO", "UN",
}


async def dispatch_fetch(session: AsyncSession, ind: Indicator):
    """داده‌ی یک شاخص را بر اساس منبعش دریافت و ذخیره می‌کند.

    در صورت پشتیبانی نشدن منبع یا فرمت نامعتبر نماد، ValueError پرتاب می‌شود.
    """
    source = ind.source

    if source == "FRED":
        return await fetch_and_store_fred_series(
            session, ind.symbol, ind.name, ind.frequency or "Monthly"
        )
    if source == "YAHOO":
        return await fetch_and_store_market_data(session, ind.symbol)
    if source == "WORLDBANK":
        parts = ind.symbol.split("_", 2)
        if len(parts) != 3:
            raise ValueError(f"فرمت نماد WorldBank نامعتبر است: {ind.symbol}")
        _, country, wb_id = parts
        return await fetch_world_bank_data(session, country, wb_id, ind.name)
    if source == "ECB":
        return await fetch_and_store_ecb_data(session, ind.symbol)
    if source == "DBNOMICS":
        return await fetch_and_store_dbnomics_data(session, ind.symbol)
    if source == "IMF":
        return await fetch_and_store_imf_data(session, ind.symbol)
    if source == "OECD":
        return await fetch_and_store_oecd_data(session, ind.symbol)
    if source == "BIS":
        return await fetch_and_store_bis_data(session, ind.symbol)
    if source == "EUROSTAT":
        return await fetch_and_store_eurostat_data(session, ind.symbol)
    if source == "ALPHAVANTAGE":
        return await fetch_and_store_alphavantage(session, ind.symbol)
    if source == "ILO":
        return await fetch_and_store_ilo_data(session, ind.symbol)
    if source == "TREASURY":
        return await fetch_and_store_treasury_data(session, ind.symbol)
    if source == "FAO":
        return await fetch_and_store_fao_data(session, ind.symbol)
    if source == "UN":
        return await fetch_and_store_un_data(session, ind.symbol)

    raise ValueError(f"دریافت داده برای منبع {source} پشتیبانی نمی‌شود.")
