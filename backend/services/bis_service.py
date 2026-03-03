import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator

import csv
import io
from datetime import datetime, date
from sqlalchemy import select

from database.models import Indicator, EconomicData


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

async def fetch_and_store_bis_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی یک پایگاه داده از بانک BIS با استفاده از استاندارد SDMX-CSV
    """
    # استخراج شناسه اصلی BIS از نماد ما (مثلا BIS_WS_CBPOL_POL تبدیل می‌شود به WS_CBPOL_POL)
    flow_id = symbol.replace("BIS_", "")
    print(f"🏦 در حال دانلود دیتای تاریخی {symbol} از سرورهای سوییس (BIS)...")
    
    # آدرس API برای دریافت کل دیتای یک Dataflow با فرمت سبک CSV
    url = f"https://stats.bis.org/api/v1/data/{flow_id}/all"
    headers = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}
    
    success = False
    for attempt in range(3):
        try:
            # استفاده از stream=True برای جلوگیری از پر شدن RAM در فایل‌های گیگابایتی
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                success = True
                break
            elif response.status_code == 404:
                return {"success": False, "message": "دیتایی برای این شاخص یافت نشد."}
            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای BIS."}

    # پیدا کردن ID این شاخص در دیتابیس خودمان
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

    # خواندن دیتای CSV در حافظه
    csv_data = response.text
    reader = csv.DictReader(io.StringIO(csv_data))
    
    records_to_insert = []
    
    for row in reader:
        try:
            # در استاندارد SDMX، تاریخ در ستون TIME_PERIOD و مقدار در OBS_VALUE است
            date_str = row.get('TIME_PERIOD')
            value_str = row.get('OBS_VALUE')
            
            if not date_str or not value_str:
                continue
                
            # تبدیل فرمت‌های مختلف تاریخ BIS (سالانه، فصلی، ماهانه، روزانه) به Date استاندارد
            if len(date_str) == 4: # سالانه (مثلا 2023)
                date_obj = date(int(date_str), 1, 1)
            elif 'Q' in date_str: # فصلی (مثلا 2023-Q1)
                year, q = date_str.split('-Q')
                month = (int(q) * 3) - 2
                date_obj = date(int(year), month, 1)
            elif len(date_str) == 7: # ماهانه (مثلا 2023-01)
                date_obj = datetime.strptime(date_str, "%Y-%m").date()
            else: # روزانه (مثلا 2023-01-15)
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": float(value_str)
            })
        except Exception as e:
            continue

    inserted_count = 0
    # تزریق سریع دیتا به دیتابیس تایم‌سری (هر ۱۰۰۰۰ رکورد در یک پکیج برای سرعت بالاتر)
    batch_size = 3000
    for i in range(0, len(records_to_insert), batch_size):
        batch = records_to_insert[i:i + batch_size]
        stmt = insert(EconomicData).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
        res = await session.execute(stmt)
        inserted_count += res.rowcount
        
    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()
        
    print(f"✅ موفق! {inserted_count} رکورد زمانی برای {symbol} ذخیره شد.")
    return {"success": True, "new_records": inserted_count}