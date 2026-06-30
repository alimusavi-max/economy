import math
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.models import AssetMarketData, EconomicData, Indicator
from services.alphavantage_service import fetch_and_store_alphavantage
from services.bis_service import fetch_and_store_bis_data
from services.ecb_service import fetch_and_store_ecb_data
from services.dbnomics_service import fetch_and_store_dbnomics_data
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

router = APIRouter(prefix="/api/data", tags=["Data API"])


class UpdateIntervalRequest(BaseModel):
    update_interval_days: int = Field(ge=1, le=3650)


class FormulaRequest(BaseModel):
    formula: str
    variables: Dict[str, str]


@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    total_indicators_q = await db.execute(select(func.count(Indicator.id)))
    total_indicators = total_indicators_q.scalar() or 0

    indicators_with_data_q = await db.execute(
        select(func.count(func.distinct(EconomicData.indicator_id)))
    )
    indicators_with_data = indicators_with_data_q.scalar() or 0

    total_points_q = await db.execute(select(func.count(EconomicData.id)))
    total_points = total_points_q.scalar() or 0

    by_source_q = await db.execute(
        select(
            Indicator.source,
            func.count(Indicator.id).label("indicator_count"),
            func.count(func.distinct(EconomicData.indicator_id)).label("with_data_count"),
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
        .group_by(Indicator.source)
        .order_by(Indicator.source.asc())
    )

    by_source = [
        {
            "source": row.source,
            "indicators": int(row.indicator_count or 0),
            "indicators_with_data": int(row.with_data_count or 0),
            "data_points": int(row.data_points_count or 0),
        }
        for row in by_source_q.all()
    ]

    return {
        "totals": {
            "indicators": int(total_indicators),
            "indicators_with_data": int(indicators_with_data),
            "economic_data_points": int(total_points),
        },
        "sources": by_source,
        "generated_at": date.today(),
    }


@router.get("/top-series")
async def get_top_series(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
    source: Optional[str] = Query(default=None),
):
    """بیشترین رکوردها در هر شاخص."""
    q = (
        select(
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .join(EconomicData, EconomicData.indicator_id == Indicator.id)
        .group_by(Indicator.id, Indicator.symbol, Indicator.name, Indicator.source)
        .order_by(func.count(EconomicData.id).desc())
        .limit(limit)
    )
    if source:
        q = q.where(Indicator.source == source.upper())
    rows = (await db.execute(q)).all()
    return [
        {"symbol": r.symbol, "name": r.name, "source": r.source, "data_points_count": int(r.data_points_count)}
        for r in rows
    ]


@router.get("/recent-activity")
async def get_recent_activity(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """شاخص‌هایی که اخیراً آپدیت شده‌اند."""
    from sqlalchemy import desc
    result = await db.execute(
        select(
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            Indicator.last_updated,
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
        .where(Indicator.last_updated.isnot(None))
        .group_by(Indicator.id, Indicator.symbol, Indicator.name, Indicator.source, Indicator.last_updated)
        .order_by(desc(Indicator.last_updated))
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "symbol": r.symbol,
            "name": r.name,
            "source": r.source,
            "last_updated": r.last_updated,
            "data_points_count": int(r.data_points_count or 0),
        }
        for r in rows
    ]


@router.get("/freshness")
async def get_freshness_overview(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Indicator.id,
            Indicator.symbol,
            Indicator.source,
            Indicator.update_interval_days,
            Indicator.last_updated,
        )
    )
    rows = result.all()
    today = date.today()

    stale = 0
    never_updated = 0
    healthy = 0
    due_soon = 0

    details = []
    for row in rows:
        if row.last_updated is None:
            status = "never_updated"
            never_updated += 1
            days_since_update = None
            days_until_due = 0
        else:
            days_since_update = (today - row.last_updated).days
            days_until_due = row.update_interval_days - days_since_update
            if days_until_due <= 0:
                status = "stale"
                stale += 1
            elif days_until_due <= 3:
                status = "due_soon"
                due_soon += 1
            else:
                status = "healthy"
                healthy += 1

        details.append(
            {
                "id": row.id,
                "symbol": row.symbol,
                "source": row.source,
                "status": status,
                "last_updated": row.last_updated,
                "update_interval_days": row.update_interval_days,
                "days_since_update": days_since_update,
                "days_until_due": days_until_due,
            }
        )

    return {
        "totals": {
            "all": len(rows),
            "healthy": healthy,
            "due_soon": due_soon,
            "stale": stale,
            "never_updated": never_updated,
        },
        "generated_at": today,
        "items": details,
    }


@router.get("/symbols/available")
async def get_available_symbols(
    db: AsyncSession = Depends(get_db),
    source: Optional[str] = Query(default=None, description="فیلتر منبع مثل FRED/IMF/OECD"),
    dbnomics_provider: Optional[str] = Query(default=None, description="فیلتر زیرمنبع DBNOMICS مثل CBI/SAMA/BOE"),
    with_data_only: bool = Query(default=False, description="فقط شاخص‌هایی که دیتای زمانی دارند"),
    search: Optional[str] = Query(default=None, description="جستجو روی name/symbol/source"),
    limit: int = Query(default=300, ge=1, le=10000),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    paginated: bool = Query(default=False, description="در صورت true خروجی شامل items+pagination می‌شود"),
    sort_by: str = Query(default="source", description="مرتب‌سازی: source|name|symbol|updated|interval|points"),
    sort_dir: str = Query(default="asc", description="جهت مرتب‌سازی: asc|desc"),
):
    base_query = (
        select(
            Indicator.id,
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            Indicator.frequency,
            Indicator.dbnomics_provider,
            Indicator.update_interval_days,
            Indicator.last_updated,
            Indicator.tags,
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
    )

    if source:
        base_query = base_query.where(Indicator.source == source.upper())

    if dbnomics_provider:
        base_query = base_query.where(Indicator.source == "DBNOMICS")
        base_query = base_query.where(func.upper(Indicator.dbnomics_provider) == dbnomics_provider.upper())

    if search:
        pattern = f"%{search.strip()}%"
        base_query = base_query.where(
            Indicator.symbol.ilike(pattern)
            | Indicator.name.ilike(pattern)
            | Indicator.source.ilike(pattern)
        )

    base_query = base_query.group_by(
        Indicator.id,
        Indicator.symbol,
        Indicator.name,
        Indicator.source,
        Indicator.frequency,
        Indicator.dbnomics_provider,
        Indicator.update_interval_days,
        Indicator.last_updated,
        Indicator.tags,
    )

    if with_data_only:
        base_query = base_query.having(func.count(EconomicData.id) > 0)

    sort_key = (sort_by or "source").lower()
    sort_direction = (sort_dir or "asc").lower()

    sort_columns = {
        "source": Indicator.source,
        "name": Indicator.name,
        "symbol": Indicator.symbol,
        "updated": Indicator.last_updated,
        "interval": Indicator.update_interval_days,
        "points": func.count(EconomicData.id),
    }

    sort_column = sort_columns.get(sort_key, Indicator.source)
    sort_expr = sort_column.desc().nullslast() if sort_direction == "desc" else sort_column.asc().nullslast()

    ordered_query = base_query.order_by(sort_expr, Indicator.source.asc(), Indicator.name.asc())

    try:
        has_dbnomics_provider_column = True
        if paginated:
            count_query = select(func.count()).select_from(base_query.subquery())
            total = int((await db.execute(count_query)).scalar() or 0)
            rows_query = ordered_query.offset((page - 1) * page_size).limit(page_size)
        else:
            total = None
            rows_query = ordered_query.limit(limit)

        rows = (await db.execute(rows_query)).all()
    except ProgrammingError as exc:
        if "dbnomics_provider" not in str(exc).lower():
            raise

        has_dbnomics_provider_column = False
        fallback_query = (
            select(
                Indicator.id,
                Indicator.symbol,
                Indicator.name,
                Indicator.source,
                Indicator.frequency,
                Indicator.update_interval_days,
                Indicator.last_updated,
                func.count(EconomicData.id).label("data_points_count"),
            )
            .select_from(Indicator)
            .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
        )

        if source:
            fallback_query = fallback_query.where(Indicator.source == source.upper())

        if dbnomics_provider:
            fallback_query = fallback_query.where(Indicator.source == "DBNOMICS")

        if search:
            pattern = f"%{search.strip()}%"
            fallback_query = fallback_query.where(
                Indicator.symbol.ilike(pattern)
                | Indicator.name.ilike(pattern)
                | Indicator.source.ilike(pattern)
            )

        fallback_query = fallback_query.group_by(
            Indicator.id,
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            Indicator.frequency,
            Indicator.update_interval_days,
            Indicator.last_updated,
        )

        if with_data_only:
            fallback_query = fallback_query.having(func.count(EconomicData.id) > 0)

        fallback_sort_columns = {
            "source": Indicator.source,
            "name": Indicator.name,
            "symbol": Indicator.symbol,
            "updated": Indicator.last_updated,
            "interval": Indicator.update_interval_days,
            "points": func.count(EconomicData.id),
        }
        fallback_sort_column = fallback_sort_columns.get(sort_key, Indicator.source)
        fallback_sort_expr = fallback_sort_column.desc().nullslast() if sort_direction == "desc" else fallback_sort_column.asc().nullslast()

        ordered_fallback_query = fallback_query.order_by(fallback_sort_expr, Indicator.source.asc(), Indicator.name.asc())
        if paginated:
            count_query = select(func.count()).select_from(fallback_query.subquery())
            total = int((await db.execute(count_query)).scalar() or 0)
            rows_query = ordered_fallback_query.offset((page - 1) * page_size).limit(page_size)
        else:
            total = None
            rows_query = ordered_fallback_query.limit(limit)

        rows = (await db.execute(rows_query)).all()

    rows_payload = [
        {
            "id": row.id,
            "symbol": row.symbol,
            "name": row.name,
            "source": row.source,
            "frequency": row.frequency,
            "dbnomics_provider": row.dbnomics_provider if has_dbnomics_provider_column else None,
            "update_interval_days": row.update_interval_days,
            "last_updated": row.last_updated,
            "data_points_count": int(row.data_points_count or 0),
            "has_data": int(row.data_points_count or 0) > 0,
            "tags": getattr(row, "tags", None),
        }
        for row in rows
    ]

    if not paginated:
        return rows_payload

    total_pages = max((total + page_size - 1) // page_size, 1)
    return {
        "items": rows_payload,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@router.get("/dbnomics/providers")
async def get_dbnomics_providers(
    db: AsyncSession = Depends(get_db),
    with_data_only: bool = Query(default=False, description="فقط زیرمنبع‌هایی که دیتای زمانی دارند"),
    search: Optional[str] = Query(default=None, description="جستجو در نام زیرمنبع"),
    limit: int = Query(default=5000, ge=1, le=20000),
):
    try:
        query = (
            select(Indicator.dbnomics_provider, func.count(Indicator.id).label("indicators_count"))
            .where(Indicator.source == "DBNOMICS")
            .where(Indicator.dbnomics_provider.is_not(None))
            .where(Indicator.dbnomics_provider != "")
            .group_by(Indicator.dbnomics_provider)
            .order_by(Indicator.dbnomics_provider.asc())
            .limit(limit)
        )

        if search:
            query = query.where(Indicator.dbnomics_provider.ilike(f"%{search.strip()}%"))

        if with_data_only:
            query = (
                select(Indicator.dbnomics_provider, func.count(func.distinct(Indicator.id)).label("indicators_count"))
                .select_from(Indicator)
                .join(EconomicData, EconomicData.indicator_id == Indicator.id)
                .where(Indicator.source == "DBNOMICS")
                .where(Indicator.dbnomics_provider.is_not(None))
                .where(Indicator.dbnomics_provider != "")
                .group_by(Indicator.dbnomics_provider)
                .order_by(Indicator.dbnomics_provider.asc())
                .limit(limit)
            )

            if search:
                query = query.where(Indicator.dbnomics_provider.ilike(f"%{search.strip()}%"))

        rows = (await db.execute(query)).all()
        return [
            {
                "provider": r.dbnomics_provider,
                "indicators": int(r.indicators_count or 0),
            }
            for r in rows
        ]
    except ProgrammingError as exc:
        if "dbnomics_provider" not in str(exc).lower():
            raise

        fallback_query = select(Indicator.symbol).where(Indicator.source == "DBNOMICS")
        if with_data_only:
            fallback_query = (
                select(Indicator.symbol)
                .select_from(Indicator)
                .join(EconomicData, EconomicData.indicator_id == Indicator.id)
                .where(Indicator.source == "DBNOMICS")
            )

        symbols = (await db.execute(fallback_query.limit(limit))).scalars().all()
        counts: Dict[str, int] = {}

        for symbol in symbols:
            if not symbol or not symbol.startswith("DBN_"):
                continue
            parts = symbol.split("_", 2)
            if len(parts) < 2 or not parts[1]:
                continue
            provider = parts[1].upper()
            if search and search.strip().upper() not in provider:
                continue
            counts[provider] = counts.get(provider, 0) + 1

        return [
            {"provider": provider, "indicators": counts[provider]}
            for provider in sorted(counts.keys())
        ]


class BulkSymbolsRequest(BaseModel):
    symbols: List[str] = Field(max_length=50)


@router.post("/symbols/bulk-refresh")
async def bulk_refresh_symbols(request: BulkSymbolsRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """دریافت چندین شاخص به صورت پس‌زمینه."""
    from database.database import AsyncSessionLocal

    clean = [s.strip().upper() for s in request.symbols if s.strip()][:50]
    if not clean:
        raise HTTPException(status_code=400, detail="حداقل یک نماد باید مشخص شود.")

    async def _run_bulk():
        async with AsyncSessionLocal() as session:
            for sym in clean:
                try:
                    ind_r = await session.execute(select(Indicator).where(Indicator.symbol == sym))
                    ind = ind_r.scalar_one_or_none()
                    if not ind:
                        continue
                    # use same dispatch logic as refresh-now
                    if ind.source == "FRED":
                        await fetch_and_store_fred_series(session, ind.symbol, ind.name, ind.frequency or "Monthly")
                    elif ind.source == "YAHOO":
                        await fetch_and_store_market_data(session, ind.symbol)
                    elif ind.source == "WORLDBANK":
                        parts = ind.symbol.split("_", 2)
                        if len(parts) == 3:
                            _, country, wb_id = parts
                            await fetch_world_bank_data(session, country, wb_id, ind.name)
                    elif ind.source == "ECB":
                        await fetch_and_store_ecb_data(session, ind.symbol)
                    elif ind.source == "DBNOMICS":
                        await fetch_and_store_dbnomics_data(session, ind.symbol)
                    elif ind.source == "IMF":
                        await fetch_and_store_imf_data(session, ind.symbol)
                    elif ind.source == "OECD":
                        await fetch_and_store_oecd_data(session, ind.symbol)
                    elif ind.source == "BIS":
                        await fetch_and_store_bis_data(session, ind.symbol)
                    elif ind.source == "EUROSTAT":
                        await fetch_and_store_eurostat_data(session, ind.symbol)
                    elif ind.source == "ALPHAVANTAGE":
                        await fetch_and_store_alphavantage(session, ind.symbol)
                    elif ind.source == "ILO":
                        await fetch_and_store_ilo_data(session, ind.symbol)
                    elif ind.source == "TREASURY":
                        await fetch_and_store_treasury_data(session, ind.symbol)
                    elif ind.source == "FAO":
                        await fetch_and_store_fao_data(session, ind.symbol)
                    elif ind.source == "UN":
                        await fetch_and_store_un_data(session, ind.symbol)
                except Exception as e:
                    print(f"[bulk-refresh] خطا در {sym}: {e}")
                import asyncio
                await asyncio.sleep(1)

    background_tasks.add_task(_run_bulk)
    return {"success": True, "queued": len(clean), "message": f"رفرش {len(clean)} شاخص در پس‌زمینه آغاز شد."}


@router.post("/sources/{source}/fetch-data")
async def fetch_source_data(
    source: str,
    background_tasks: BackgroundTasks,
    only_empty: bool = True,
    limit: int = Query(300, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """دریافت داده برای همه‌ی شاخص‌های یک منبع (به‌صورت پس‌زمینه با ردیابی پیشرفت).

    only_empty=True یعنی فقط شاخص‌هایی که هنوز هیچ داده‌ای ندارند پر می‌شوند.
    """
    from database.database import AsyncSessionLocal
    from services.fetch_dispatch import dispatch_fetch, SUPPORTED_FETCH_SOURCES
    from services import job_progress
    import asyncio

    src = source.upper()
    if src not in SUPPORTED_FETCH_SOURCES:
        raise HTTPException(status_code=400, detail=f"دریافت داده برای منبع {src} پشتیبانی نمی‌شود.")

    job_key = f"fetch:{src}"
    if job_progress._jobs.get(job_key, {}).get("status") == "running":
        raise HTTPException(status_code=409, detail=f"دریافت داده‌ی {src} هم‌اکنون در حال اجراست.")

    # انتخاب شاخص‌های هدف
    q = select(Indicator).where(Indicator.source == src)
    if only_empty:
        sub = select(EconomicData.indicator_id).distinct()
        q = q.where(Indicator.id.notin_(sub))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    targets = [(r.symbol, r.id) for r in rows]

    if not targets:
        return {
            "success": True,
            "queued": 0,
            "message": f"شاخص خالی‌ای برای {src} پیدا نشد. ابتدا «شخم بزن» را اجرا کنید." if only_empty
                       else f"شاخصی برای {src} پیدا نشد.",
        }

    job_progress.start_job(job_key, "fetch", f"دریافت داده‌ی {src}", total=len(targets))

    async def _run():
        async with AsyncSessionLocal() as session:
            for sym, _id in targets:
                try:
                    ind = (await session.execute(
                        select(Indicator).where(Indicator.symbol == sym)
                    )).scalar_one_or_none()
                    if not ind:
                        job_progress.update_job(job_key, current=sym, ok=False)
                        continue
                    await dispatch_fetch(session, ind)
                    job_progress.update_job(job_key, current=sym, ok=True)
                except Exception as e:
                    print(f"[fetch-data:{src}] خطا در {sym}: {e}")
                    job_progress.update_job(job_key, current=sym, ok=False)
                await asyncio.sleep(0.5)
        job = job_progress._jobs.get(job_key, {})
        job_progress.finish_job(
            job_key,
            message=f"دریافت داده‌ی {src} تمام شد: {job.get('ok', 0)} موفق، {job.get('failed', 0)} ناموفق.",
        )

    background_tasks.add_task(_run)
    return {
        "success": True,
        "queued": len(targets),
        "job_key": job_key,
        "message": f"دریافت داده برای {len(targets)} شاخص {src} در پس‌زمینه آغاز شد.",
    }


@router.get("/jobs/progress")
async def get_jobs_progress():
    """وضعیت زنده‌ی عملیات‌های پس‌زمینه (دریافت داده) را برمی‌گرداند."""
    from services import job_progress
    return {"jobs": job_progress.get_all_jobs()}


@router.post("/jobs/clear")
async def clear_jobs_progress():
    from services import job_progress
    job_progress.clear_finished()
    return {"success": True}


@router.put("/symbols/{symbol}/interval")
async def update_symbol_interval(symbol: str, request: UpdateIntervalRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()

    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")

    indicator.update_interval_days = request.update_interval_days
    db.add(indicator)
    await db.commit()

    return {"success": True, "message": f"بازه آپدیت نماد {symbol} به {request.update_interval_days} روز تغییر یافت."}


@router.delete("/symbols/{symbol}")
async def delete_indicator(symbol: str, data_only: bool = False, db: AsyncSession = Depends(get_db)):
    """حذف یک شاخص (و در صورت لزوم داده‌های آن) از دیتابیس."""
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")

    await db.execute(delete(EconomicData).where(EconomicData.indicator_id == indicator.id))
    if not data_only:
        await db.delete(indicator)
    else:
        indicator.last_updated = None
        db.add(indicator)

    await db.commit()
    if data_only:
        return {"success": True, "message": f"داده‌های {symbol} پاک شد؛ تعریف شاخص حفظ شد."}
    return {"success": True, "message": f"شاخص {symbol} و تمام داده‌هایش حذف شد."}


@router.post("/symbols/{symbol}/refresh-now")
async def refresh_symbol_now(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")

    async def _refresh_once():
        if indicator.source == "FRED":
            return await fetch_and_store_fred_series(
                session=db,
                series_id=indicator.symbol,
                name=indicator.name,
                frequency=indicator.frequency or "Monthly",
            )

        if indicator.source == "YAHOO":
            return await fetch_and_store_market_data(session=db, symbol=indicator.symbol)

        if indicator.source == "WORLDBANK":
            parts = indicator.symbol.split("_", 2)
            if len(parts) == 3:
                _, country, wb_indicator = parts
                return await fetch_world_bank_data(db, country, wb_indicator, indicator.name)

        if indicator.source == "ECB":
            return await fetch_and_store_ecb_data(db, indicator.symbol)

        if indicator.source == "DBNOMICS":
            return await fetch_and_store_dbnomics_data(db, indicator.symbol)

        if indicator.source == "IMF":
            return await fetch_and_store_imf_data(db, indicator.symbol)

        if indicator.source == "OECD":
            return await fetch_and_store_oecd_data(db, indicator.symbol)

        if indicator.source == "BIS":
            return await fetch_and_store_bis_data(db, indicator.symbol)

        if indicator.source == "EUROSTAT":
            return await fetch_and_store_eurostat_data(db, indicator.symbol)

        if indicator.source == "ALPHAVANTAGE":
            return await fetch_and_store_alphavantage(db, indicator.symbol)

        if indicator.source == "ILO":
            return await fetch_and_store_ilo_data(db, indicator.symbol)

        if indicator.source == "TREASURY":
            return await fetch_and_store_treasury_data(db, indicator.symbol)

        if indicator.source == "FAO":
            return await fetch_and_store_fao_data(db, indicator.symbol)

        if indicator.source == "UN":
            return await fetch_and_store_un_data(db, indicator.symbol)

        raise HTTPException(
            status_code=400,
            detail=f"برای منبع {indicator.source} هنوز رفرش مستقیم پیاده‌سازی نشده است.",
        )

    last_error = None
    for _ in range(2):
        try:
            result = await _refresh_once()
            return {"success": True, "symbol": indicator.symbol, "source": indicator.source, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            last_error = exc

    raise HTTPException(
        status_code=502,
        detail=f"رفرش مستقیم برای {indicator.symbol} ناموفق بود: {str(last_error) if last_error else 'unknown error'}",
    )


@router.get("/lab/combine")
async def combine_indicators_data(
    sym1: str,
    sym2: str,
    operation: str,
    db: AsyncSession = Depends(get_db)
):
    if operation not in {"add", "sub", "mul", "div"}:
        raise HTTPException(status_code=400, detail="عملیات نامعتبر است. از add/sub/mul/div استفاده کنید.")

    ind1_res = await db.execute(select(Indicator).where(Indicator.symbol == sym1.upper()))
    ind1 = ind1_res.scalar_one_or_none()

    ind2_res = await db.execute(select(Indicator).where(Indicator.symbol == sym2.upper()))
    ind2 = ind2_res.scalar_one_or_none()

    if not ind1 or not ind2:
        raise HTTPException(status_code=404, detail="یکی از شاخص‌ها یافت نشد.")

    data1_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind1.id))
    data2_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind2.id))

    dict1 = {r.date: r.value for r in data1_res.scalars().all()}
    dict2 = {r.date: r.value for r in data2_res.scalars().all()}

    common_dates = sorted(list(set(dict1.keys()) & set(dict2.keys())))

    combined_data = []
    for d in common_dates:
        v1, v2 = dict1[d], dict2[d]
        try:
            if operation == "add":
                val = v1 + v2
            elif operation == "sub":
                val = v1 - v2
            elif operation == "mul":
                val = v1 * v2
            else:
                val = v1 / v2 if v2 != 0 else float("nan")

            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception:
            continue

    return combined_data


@router.post("/lab/formula")
async def compute_custom_formula(request: FormulaRequest, db: AsyncSession = Depends(get_db)):
    import ast
    import math

    series_data: Dict[str, Dict[Any, float]] = {}

    for var_name, symbol in request.variables.items():
        ind_res = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
        ind = ind_res.scalar_one_or_none()
        if not ind:
            raise HTTPException(status_code=404, detail=f"نماد {symbol} یافت نشد.")

        data_res = await db.execute(select(EconomicData).where(EconomicData.indicator_id == ind.id))
        records = data_res.scalars().all()
        series_data[var_name] = {r.date: r.value for r in records}

    if not series_data:
        return []

    common_dates = set.intersection(*[set(d.keys()) for d in series_data.values()])
    common_dates = sorted(list(common_dates))

    safe_math_env = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}
    all_var_names = set(request.variables.keys()) | set(safe_math_env.keys())

    try:
        tree = ast.parse(request.formula, mode="eval")
        ALLOWED_NODES = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name,
            ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
            ast.USub, ast.UAdd, ast.Mod, ast.Load, ast.keyword,
        )
        for node in ast.walk(tree):
            if not isinstance(node, ALLOWED_NODES):
                raise HTTPException(status_code=400, detail=f"عملگر غیرمجاز در فرمول: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id not in all_var_names:
                raise HTTPException(status_code=400, detail=f"متغیر یا تابع ناشناخته: '{node.id}'")
        compiled = compile(tree, "<formula>", "eval")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"خطای نحوی در فرمول: {exc}") from exc

    combined_data = []
    for d in common_dates:
        local_vars = {var_name: series_data[var_name][d] for var_name in request.variables.keys()}
        try:
            val = eval(compiled, {"__builtins__": {}}, {**safe_math_env, **local_vars})
            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception:
            continue

    return combined_data


class ComputeRequest(BaseModel):
    formula: str
    variables: Dict[str, str]


async def _load_series(db: AsyncSession, symbol: str) -> Dict[date, float]:
    sym = symbol.upper()
    ind_res = await db.execute(select(Indicator).where(Indicator.symbol == sym))
    ind = ind_res.scalar_one_or_none()
    if not ind:
        raise HTTPException(status_code=404, detail=f"نماد {sym} یافت نشد.")

    data_res = await db.execute(
        select(EconomicData).where(EconomicData.indicator_id == ind.id).order_by(EconomicData.date.asc())
    )
    records = data_res.scalars().all()

    if not records:
        market_res = await db.execute(
            select(AssetMarketData).where(AssetMarketData.symbol == sym).order_by(AssetMarketData.date.asc())
        )
        market_records = market_res.scalars().all()
        return {r.date: r.close_price for r in market_records}

    return {r.date: r.value for r in records}


@router.post("/lab/compute")
async def compute_advanced_formula(request: ComputeRequest, db: AsyncSession = Depends(get_db)):
    """
    محاسبه فرمول پیشرفته روی سری‌های زمانی با پشتیبانی از توابع:
    lag(A, n), pct_change(A, n), rolling_mean(A, n), rolling_std(A, n),
    normalize(A), zscore(A), diff(A, n), log(A), exp(A), abs(A), cumsum(A)
    """
    raw: Dict[str, Dict[date, float]] = {}
    for var_name, symbol in request.variables.items():
        raw[var_name] = await _load_series(db, symbol)

    if not raw:
        return {"result": [], "series": {}}

    df = pd.DataFrame(raw)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().dropna(how="all")

    _math = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}

    def _lag(s: pd.Series, n: int = 1) -> pd.Series:
        return s.shift(n)

    def _pct_change(s: pd.Series, n: int = 1) -> pd.Series:
        return s.pct_change(periods=n) * 100

    def _rolling_mean(s: pd.Series, n: int = 12) -> pd.Series:
        return s.rolling(window=n, min_periods=1).mean()

    def _rolling_std(s: pd.Series, n: int = 12) -> pd.Series:
        return s.rolling(window=n, min_periods=2).std()

    def _normalize(s: pd.Series) -> pd.Series:
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn) * 100 if mx != mn else s * 0

    def _zscore(s: pd.Series) -> pd.Series:
        std = s.std()
        return (s - s.mean()) / std if std != 0 else s * 0

    def _diff(s: pd.Series, n: int = 1) -> pd.Series:
        return s.diff(n)

    def _cumsum(s: pd.Series) -> pd.Series:
        return s.cumsum()

    def _rolling_median(s: pd.Series, n: int = 12) -> pd.Series:
        return s.rolling(window=n, min_periods=1).median()

    def _ewm(s: pd.Series, span: int = 12) -> pd.Series:
        return s.ewm(span=span, adjust=False).mean()

    def _clip(s: pd.Series, lo: float = None, hi: float = None) -> pd.Series:
        return s.clip(lower=lo, upper=hi)

    env = {
        **_math,
        "lag": _lag,
        "pct_change": _pct_change,
        "rolling_mean": _rolling_mean,
        "rolling_std": _rolling_std,
        "rolling_median": _rolling_median,
        "ewm": _ewm,
        "clip": _clip,
        "normalize": _normalize,
        "zscore": _zscore,
        "diff": _diff,
        "cumsum": _cumsum,
        "log": lambda s: s.apply(lambda x: math.log(x) if x > 0 else float("nan")),
        "exp": lambda s: s.apply(math.exp),
        "abs": lambda s: s.abs(),
        "sqrt": lambda s: s.apply(lambda x: math.sqrt(x) if x >= 0 else float("nan")),
    }

    col_vars = {col: df[col] for col in df.columns if col in request.variables}
    env.update(col_vars)

    try:
        import ast
        tree = ast.parse(request.formula, mode="eval")
        # whitelist: فقط عملگرهای ریاضی و نام‌های موجود در env مجاز هستند
        ALLOWED_NODES = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name,
            ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
            ast.USub, ast.UAdd, ast.Mod, ast.Load, ast.keyword,
        )
        for node in ast.walk(tree):
            if not isinstance(node, ALLOWED_NODES):
                raise ValueError(f"عملگر غیرمجاز در فرمول: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id not in env:
                raise ValueError(f"متغیر یا تابع ناشناخته: '{node.id}'")
        result = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, env)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"خطا در فرمول: {exc}") from exc

    if isinstance(result, pd.Series):
        result = result.dropna()
        result_list = [
            {"date": str(idx.date()), "value": round(float(v), 6)}
            for idx, v in result.items()
            if pd.notna(v) and not (isinstance(v, float) and math.isinf(v))
        ]
    elif isinstance(result, (int, float)):
        result_list = [{"date": str(df.index[-1].date()), "value": round(float(result), 6)}]
    else:
        result_list = []

    series_out: Dict[str, List[Dict]] = {}
    for var_name in request.variables:
        if var_name in df.columns:
            col = df[var_name].dropna()
            series_out[var_name] = [
                {"date": str(idx.date()), "value": round(float(v), 6)}
                for idx, v in col.items()
            ]

    return {"result": result_list, "series": series_out}


@router.post("/lab/correlate")
async def compute_correlation(request: ComputeRequest, db: AsyncSession = Depends(get_db)):
    """
    محاسبه ماتریس همبستگی پیرسون بین تمام سری‌های انتخاب‌شده
    برمی‌گرداند: ماتریس همبستگی + scatter data برای هر جفت
    """
    raw: Dict[str, Dict[date, float]] = {}
    for var_name, symbol in request.variables.items():
        raw[var_name] = await _load_series(db, symbol)

    if len(raw) < 2:
        raise HTTPException(status_code=400, detail="حداقل ۲ متغیر برای همبستگی لازم است.")

    df = pd.DataFrame(raw)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().dropna(how="all")

    corr_matrix = df.corr(method="pearson").round(4)

    matrix_out = []
    for a in corr_matrix.index:
        for b in corr_matrix.columns:
            matrix_out.append({
                "a": a,
                "b": b,
                "symbol_a": request.variables.get(a, a),
                "symbol_b": request.variables.get(b, b),
                "corr": round(float(corr_matrix.loc[a, b]), 4) if pd.notna(corr_matrix.loc[a, b]) else None,
            })

    scatter_pairs = {}
    vars_list = list(request.variables.keys())
    for i in range(len(vars_list)):
        for j in range(i + 1, len(vars_list)):
            a, b = vars_list[i], vars_list[j]
            pair_df = df[[a, b]].dropna()
            scatter_pairs[f"{a}_{b}"] = [
                {"x": round(float(row[a]), 6), "y": round(float(row[b]), 6), "date": str(idx.date())}
                for idx, row in pair_df.iterrows()
            ]

    return {
        "matrix": matrix_out,
        "variables": request.variables,
        "n_observations": len(df.dropna()),
        "scatter": scatter_pairs,
    }


class TagsRequest(BaseModel):
    tags: Optional[str] = Field(default=None, max_length=200)


@router.patch("/symbols/{symbol}/tags")
async def update_symbol_tags(symbol: str, request: TagsRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")
    indicator.tags = request.tags.strip() if request.tags else None
    await db.commit()
    return {"success": True, "symbol": indicator.symbol, "tags": indicator.tags}


@router.get("/export/multi.csv")
async def export_multi_csv(
    symbols: str = Query(description="کاما-جدا نمادها مثل FEDFUNDS,UNRATE"),
    db: AsyncSession = Depends(get_db),
):
    """خروجی CSV گسترده برای چندین شاخص با ستون‌های جداگانه."""
    from fastapi.responses import StreamingResponse
    import io

    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    if not sym_list:
        raise HTTPException(status_code=400, detail="حداقل یک نماد مشخص کنید.")

    series_data: Dict[str, Dict[date, float]] = {}
    for sym in sym_list:
        result = await db.execute(select(Indicator).where(Indicator.symbol == sym))
        indicator = result.scalar_one_or_none()
        if not indicator:
            continue
        data_res = await db.execute(
            select(EconomicData).where(EconomicData.indicator_id == indicator.id).order_by(EconomicData.date.asc())
        )
        series_data[sym] = {r.date: r.value for r in data_res.scalars().all()}

    all_dates = sorted(set(d for s in series_data.values() for d in s))
    header = ["date"] + list(series_data.keys())
    lines = [",".join(header)]
    for d in all_dates:
        row_vals = [str(d)] + [str(series_data[sym].get(d, "")) for sym in series_data]
        lines.append(",".join(row_vals))

    content = "\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )


@router.get("/{symbol}/export.csv")
async def export_symbol_csv(symbol: str, db: AsyncSession = Depends(get_db)):
    """خروجی CSV برای یک شاخص."""
    from fastapi.responses import StreamingResponse
    import io

    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="شاخص یافت نشد.")

    data_result = await db.execute(
        select(EconomicData)
        .where(EconomicData.indicator_id == indicator.id)
        .order_by(EconomicData.date.asc())
    )
    records = data_result.scalars().all()

    lines = ["date,value"]
    for r in records:
        lines.append(f"{r.date},{r.value}")

    content = "\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{symbol.upper()}.csv"'},
    )


@router.get("/{symbol}")
async def get_economic_data(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()

    if not indicator:
        raise HTTPException(status_code=404, detail="شاخص مورد نظر در دیتابیس یافت نشد. ابتدا آن را Fetch کنید.")

    data_result = await db.execute(
        select(EconomicData)
        .where(EconomicData.indicator_id == indicator.id)
        .order_by(EconomicData.date.asc())
    )
    records = data_result.scalars().all()

    chart_data = [{"date": str(r.date), "value": r.value} for r in records]

    # اگر در EconomicData چیزی نبود و منبع YAHOO یا ALPHAVANTAGE بود، از AssetMarketData بخوان
    if not chart_data and indicator.source in ("YAHOO", "ALPHAVANTAGE"):
        asset_result = await db.execute(
            select(AssetMarketData)
            .where(AssetMarketData.symbol == indicator.symbol)
            .order_by(AssetMarketData.date.asc())
        )
        asset_records = asset_result.scalars().all()
        chart_data = [{"date": str(r.date), "value": r.close_price} for r in asset_records]

    return {
        "indicator": {
            "name": indicator.name,
            "symbol": indicator.symbol,
            "source": indicator.source,
            "frequency": indicator.frequency,
            "last_updated": indicator.last_updated,
            "update_interval_days": indicator.update_interval_days,
            "tags": indicator.tags,
        },
        "total_records": len(chart_data),
        "data": chart_data,
    }
