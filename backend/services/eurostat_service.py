import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator

import csv
import io
from datetime import datetime, date
from sqlalchemy import select
from database.models import EconomicData

async def auto_discover_eurostat(session: AsyncSession):
    """
    کاوشگر مرکز آمار اروپا (Eurostat) مجهز به لباس مبدل و سیستم بک‌آپ
    """
    print("🇪🇺 در حال شروع کاوشگر مرکز آمار اروپا (Eurostat)...")
    
    url = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all"
    
    # 🎭 لباس مبدل برای دور زدن فایروال اتحادیه اروپا
    headers = {
        "Accept": "application/vnd.sdmx.structure+json;version=1.0",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    # لیست بک‌آپ از حیاتی‌ترین شاخص‌های اروپا (در صورتی که کل کاتالوگ مسدود باشد)
    core_eurostat_datasets = [
        {"id": "PRC_HICP_MIDX", "name": "شاخص هماهنگ قیمت مصرف‌کننده (تورم - HICP)"},
        {"id": "NAMQ_10_GDP", "name": "تولید ناخالص داخلی و اجزای اصلی (GDP)"},
        {"id": "UNE_RT_M", "name": "نرخ بیکاری (Unemployment Rate)"},
        {"id": "STS_INPR_M", "name": "تولیدات صنعتی (Industrial Production)"},
        {"id": "PRC_HPI_Q", "name": "شاخص قیمت مسکن (House Price Index)"},
        {"id": "EI_BSSI_M_R2", "name": "شاخص احساسات اقتصادی (Economic Sentiment Indicator)"}
    ]

    max_retries = 3
    response_json = None
    
    for attempt in range(max_retries):
        try:
            print(f"   ⏳ تلاش {attempt+1}: در حال مذاکره با سرورهای Eurostat...")
            response = requests.get(url, headers=headers, timeout=45)
            if response.status_code == 200:
                response_json = response.json()
                break
            else:
                print(f"   ⚠️ سرور کد {response.status_code} را برگرداند.")
        except Exception:
            print(f"   ⚠️ تاخیر در پاسخ سرور (Timeout).")
        await asyncio.sleep(4)

    records_to_insert = []
    
    # اگر کاتالوگ با موفقیت دریافت شد
    if response_json and "data" in response_json:
        try:
            dataflows = response_json["data"].get("dataflows", [])
            for flow in dataflows:
                flow_id = (flow.get("id") or "").upper().strip()
                name = flow.get("name") or flow_id
                if flow_id:
                    records_to_insert.append({
                        "symbol": f"EUROSTAT_{flow_id}"[:50],
                        "name": f"Eurostat: {name}"[:255],
                        "source": "EUROSTAT",
                        "frequency": "Mixed",
                        "update_interval_days": 30
                    })
        except Exception as e:
            print(f"❌ خطا در پارس کردن دیتای Eurostat: {e}")

    # اجرای پلان B: اگر اینترنت یا فایروال اجازه نداد، بک‌آپ را تزریق کن
    if not records_to_insert:
        print("   ⚠️ استفاده از لیست بک‌آپِ حیاتی برای اروپا...")
        for ds in core_eurostat_datasets:
            records_to_insert.append({
                "symbol": f"EUROSTAT_{ds['id']}",
                "name": f"Eurostat: {ds['name']}",
                "source": "EUROSTAT",
                "frequency": "Mixed",
                "update_interval_days": 30
            })

    # تزریق به دیتابیس
    if records_to_insert:
        stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
        result = await session.execute(stmt)
        await session.commit()
        print(f"🎉 کاوشگر Eurostat تمام شد! {result.rowcount} شاخص از اروپا ثبت شد.")
        return result.rowcount

    return 0


async def fetch_and_store_eurostat_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی از مرکز آمار اروپا (Eurostat) با فرمت SDMX-CSV
    """
    flow_id = symbol.replace("EUROSTAT_", "")
    print(f"🇪🇺 در حال دانلود دیتای تاریخی {symbol} از سرورهای اتحادیه اروپا...")
    
    # آدرس رسمی API مرکز آمار اروپا برای دریافت دیتای سبک CSV
    url = f"https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{flow_id}/?format=SDMX-CSV"
    
    headers = {
        "Accept": "text/csv",
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }
    
    success = False
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=40)
            if response.status_code == 200:
                success = True
                break
            elif response.status_code in [404, 400]:
                return {"success": False, "message": "دیتایی در سرور اروپا یافت نشد (احتمالاً بایگانی شده)."}
            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای Eurostat."}

    # پیدا کردن ID این شاخص در دیتابیس خودمان
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را کشف کنید."}

    # خواندن دیتای CSV
    csv_data = response.text
    reader = csv.DictReader(io.StringIO(csv_data))
    
    records_to_insert = []
    
    for row in reader:
        try:
            date_str = row.get('TIME_PERIOD')
            value_str = row.get('OBS_VALUE')
            
            if not date_str or not value_str:
                continue
                
            # تمیز کردن تاریخ‌های عجیب یوروستات (مثلاً گاهی می‌نویسد 2023M01 یا 2023-M01)
            date_str = date_str.replace("-M", "-").replace("M", "-")
            date_str = date_str.replace("Q", "-Q").replace("--", "-")
            
            # تبدیل به تاریخ استاندارد
            if len(date_str) == 4: # سالانه (2023)
                date_obj = date(int(date_str), 1, 1)
            elif '-Q' in date_str: # فصلی (2023-Q1)
                year, q = date_str.split('-Q')
                month = (int(q) * 3) - 2
                date_obj = date(int(year), month, 1)
            elif len(date_str) == 7 and '-' in date_str: # ماهانه (2023-01)
                year, month = date_str.split('-')
                date_obj = date(int(year), int(month), 1)
            elif len(date_str) == 10: # روزانه (2023-01-15)
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                continue # فرمت‌های دیگر (مثل نیم‌ساله S1) را رد می‌کنیم
                
            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": float(value_str)
            })
        except Exception as e:
            continue

    if not records_to_insert:
        return {"success": False, "message": "هیچ رکورد زمانی معتبری یافت نشد."}

    # تزریق به دیتابیس با لقمه‌های ۳۰۰۰ تایی
    inserted_count = 0
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