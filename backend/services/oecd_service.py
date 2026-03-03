import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Indicator


async def auto_discover_oecd_indicators(session: AsyncSession):
    """
    دریافت لیست datasetهای OECD SDMX و ذخیره در جدول Indicator.
    """
    print("در حال شروع کاوشگر OECD...")
    url = "https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.STES,DSD_STES@DF_STES,1.0?detail=full"

    max_retries = 3
    response_json = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    if not response_json:
        print("خطا: دریافت شاخص‌های OECD ناموفق بود.")
        return 0

    flows = response_json.get("data", {}).get("dataflows", [])
    records_to_insert = []
    for flow in flows:
        flow_id = (flow.get("id") or "").upper().strip()
        names = flow.get("name") or {}
        name = names.get("en") if isinstance(names, dict) else str(names)
        if not flow_id:
            continue
        records_to_insert.append(
            {
                "symbol": f"OECD_{flow_id}"[:50],
                "name": f"OECD: {name or flow_id}"[:255],
                "source": "OECD",
                "frequency": "Monthly",
                "update_interval_days": 30,
            }
        )

    if not records_to_insert:
        return 0

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر OECD تمام شد! {result.rowcount} شاخص جدید ثبت شد.")
    return result.rowcount
