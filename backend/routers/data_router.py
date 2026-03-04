from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.models import EconomicData, Indicator
from services.ecb_service import fetch_and_store_ecb_data
from services.dbnomics_service import fetch_and_store_dbnomics_data
from services.fred_service import fetch_and_store_fred_series
from services.market_service import fetch_and_store_market_data
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
    limit: int = Query(default=300, ge=1, le=2000),
):
    query = (
        select(
            Indicator.id,
            Indicator.symbol,
            Indicator.name,
            Indicator.source,
            Indicator.frequency,
            Indicator.dbnomics_provider,
            Indicator.update_interval_days,
            Indicator.last_updated,
            func.count(EconomicData.id).label("data_points_count"),
        )
        .select_from(Indicator)
        .outerjoin(EconomicData, EconomicData.indicator_id == Indicator.id)
    )

    if source:
        query = query.where(Indicator.source == source.upper())


    if dbnomics_provider:
        query = query.where(Indicator.source == "DBNOMICS")
        query = query.where(Indicator.dbnomics_provider == dbnomics_provider.upper())


    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            Indicator.symbol.ilike(pattern)
            | Indicator.name.ilike(pattern)
            | Indicator.source.ilike(pattern)
        )

    query = query.group_by(
        Indicator.id,
        Indicator.symbol,
        Indicator.name,
        Indicator.source,
        Indicator.frequency,
        Indicator.dbnomics_provider,
        Indicator.update_interval_days,
        Indicator.last_updated,
    )

    if with_data_only:
        query = query.having(func.count(EconomicData.id) > 0)

    query = query.order_by(Indicator.source.asc(), Indicator.name.asc()).limit(limit)

    try:
        result = await db.execute(query)
        rows = result.all()
        has_dbnomics_provider_column = True
    except ProgrammingError as exc:
        # Backward compatibility for old databases where this column has not been migrated yet.
        # In that case we re-run a reduced query and return null for dbnomics_provider.
        if "dbnomics_provider" not in str(exc).lower():
            raise

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
            # If DB lacks provider column we cannot provider-filter accurately.
            # Keep DBNOMICS-only filter to reduce surprises instead of crashing.
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

        fallback_query = fallback_query.order_by(Indicator.source.asc(), Indicator.name.asc()).limit(limit)
        result = await db.execute(fallback_query)
        rows = result.all()
        has_dbnomics_provider_column = False

    return [
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
        }
        for row in rows
    ]


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


@router.post("/symbols/{symbol}/refresh-now")
async def refresh_symbol_now(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indicator).where(Indicator.symbol == symbol.upper()))
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="نماد یافت نشد")

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

    raise HTTPException(
        status_code=400,
        detail=f"برای منبع {indicator.source} هنوز رفرش مستقیم پیاده‌سازی نشده است.",
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
                val = v1 / v2 if v2 != 0 else 0

            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception:
            continue

    return combined_data


@router.post("/lab/formula")
async def compute_custom_formula(request: FormulaRequest, db: AsyncSession = Depends(get_db)):
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

    combined_data = []
    for d in common_dates:
        local_vars = {var_name: series_data[var_name][d] for var_name in request.variables.keys()}
        try:
            val = eval(request.formula, {"__builtins__": {}}, {**safe_math_env, **local_vars})
            combined_data.append({"date": str(d), "value": round(val, 4)})
        except Exception:
            continue

    return combined_data


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

    return {
        "indicator": {
            "name": indicator.name,
            "symbol": indicator.symbol,
            "source": indicator.source,
        },
        "total_records": len(chart_data),
        "data": chart_data,
    }
