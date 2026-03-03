import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Indicator


async def auto_discover_imf_indicators(session: AsyncSession):
    """
    دریافت مجموعه‌های اصلی شاخص از IMF SDMX Dataflow و ذخیره در جدول Indicator.
    """
    print("در حال شروع کاوشگر صندوق بین‌المللی پول (IMF)...")
    url = "https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/dataflow/IMF"

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
        print("خطا: دریافت لیست شاخص‌های IMF ناموفق بود.")
        return 0

    dataflows = response_json.get("data", {}).get("dataflows", [])
    records_to_insert = []
    for flow in dataflows:
        flow_id = (flow.get("id") or "").upper().strip()
        name = flow.get("name") or flow_id
        if not flow_id:
            continue

        records_to_insert.append(
            {
                "symbol": f"IMF_{flow_id}"[:50],
                "name": f"IMF Dataflow: {name}"[:255],
                "source": "IMF",
                "frequency": "Mixed",
                "update_interval_days": 30,
            }
        )

    if not records_to_insert:
        return 0

    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر IMF تمام شد! {result.rowcount} شاخص جدید ثبت شد.")
    return result.rowcount
