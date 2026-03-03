import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator

async def auto_discover_bis_indicators(session: AsyncSession):
    """
    دریافت اتوماتیک لیست پایگاه‌های داده (Dataflows) از API بانک تسویه حساب‌های بین‌المللی (BIS).
    """
    print("در حال شروع کاوشگر بانک تسویه حساب‌های بین‌المللی (BIS)...")
    
    # آدرس API رسمی SDMX برای بانک BIS
    url = "https://stats.bis.org/api/v1/dataflow/BIS/all/latest"
    headers = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}

    max_retries = 3
    response_json = None
    
    # تلاش برای دریافت دیتا با مکانیزم ضد قطعی
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                response_json = response.json()
                break
        except Exception:
            pass
        await asyncio.sleep(3 * (attempt + 1))

    records_to_insert = []
    
    # --- دیتابیس‌های حیاتی BIS به عنوان بک‌آپ ---
    # اگر اینترنت قطع شد یا API ساختارش را عوض کرد، این هسته‌های اصلی حتماً ثبت می‌شوند
    core_bis_datasets = [
        {"id": "WS_CBPOL_POL", "name": "نرخ‌های بهره سیاست‌گذاری بانک‌های مرکزی (Policy Rates)"},
        {"id": "WS_XRU", "name": "نرخ‌های ارز رسمی (Exchange Rates)"},
        {"id": "WS_CREDIT_GAP", "name": "شکاف اعتباری به تولید ناخالص داخلی (Credit-to-GDP Gaps)"},
        {"id": "WS_SPP", "name": "شاخص قیمت املاک و مستغلات (Property Prices)"},
        {"id": "WS_LBS", "name": "آمار بانکداری محلی و جریان سرمایه (Locational Banking Stats)"},
        {"id": "WS_GLI", "name": "نقدینگی جهانی (Global Liquidity Indicators)"},
    ]

    # پردازش دیتای دریافتی از API
    if response_json and "data" in response_json:
        try:
            dataflows = response_json["data"].get("dataflows", [])
            for flow in dataflows:
                flow_id = (flow.get("id") or "").upper().strip()
                name = flow.get("name") or flow_id
                if flow_id:
                    records_to_insert.append({
                        "symbol": f"BIS_{flow_id}"[:50],
                        "name": f"BIS: {name}"[:255],
                        "source": "BIS",
                        "frequency": "Mixed",
                        "update_interval_days": 30,
                    })
        except Exception as e:
            print(f"خطا در پارس کردن دیتای BIS: {e}")

    # اگر ارتباط با API قطع بود، دیتای بک‌آپ را تزریق می‌کنیم
    if not records_to_insert:
        print("استفاده از لیست بک‌آپ برای حیاتی‌ترین شاخص‌های BIS...")
        for ds in core_bis_datasets:
            records_to_insert.append({
                "symbol": f"BIS_{ds['id']}",
                "name": f"BIS: {ds['name']}",
                "source": "BIS",
                "frequency": "Mixed",
                "update_interval_days": 30,
            })

    if not records_to_insert:
        return 0

    # تزریق امن به دیتابیس (بدون تکرار)
    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"کاوشگر BIS تمام شد! {result.rowcount} مجموعه داده کلان از بانک مرکزیِ بانک‌ها ثبت شد.")
    return result.rowcount