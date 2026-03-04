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


async def auto_discover_oecd_indicators(session: AsyncSession):
    """
    کاوشگر ناب و واقعی سازمان همکاری و توسعه اقتصادی (OECD)
    (بدون دیتای آماده - استخراج مستقیم و سبک از سرور)
    """
    print("🏢 در حال شروع کاوشگر سازمان همکاری و توسعه اقتصادی (OECD)...")
    
    # 🌟 راز موفقیت: پارامتر detail=allstubs حجم دانلود را به شدت کاهش می‌دهد
    url = "https://sdmx.oecd.org/public/rest/dataflow/all/all/all?detail=allstubs"
    
    headers = {
        "Accept": "application/vnd.sdmx.structure+json;version=1.0",
        "Accept-Encoding": "gzip, deflate, br", # درخواست دیتای فشرده‌شده برای سرعت بالاتر
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    max_retries = 3
    response_json = None
    
    for attempt in range(max_retries):
        try:
            print(f"   ⏳ تلاش {attempt+1}: در حال دریافت لیست کامل از سرورهای پاریس...")
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                response_json = response.json()
                break
            else:
                print(f"   ⚠️ کد خطای سرور: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ تایم‌اوت در ارتباط. تلاش مجدد...")
            
        await asyncio.sleep(4)

    if not response_json or "data" not in response_json:
        print("❌ متاسفانه سرور OECD پاسخ نداد. عملیات متوقف شد.")
        return 0

    records_to_insert = []
    
    try:
        dataflows = response_json["data"].get("dataflows", [])
        for flow in dataflows:
            flow_id = (flow.get("id") or "").upper().strip()
            name = flow.get("name") or flow_id
            if flow_id:
                records_to_insert.append({
                    "symbol": f"OECD_{flow_id}"[:50],
                    "name": f"OECD: {name}"[:255],
                    "source": "OECD",
                    "frequency": "Mixed",
                    "update_interval_days": 30
                })
    except Exception as e:
        print(f"❌ خطا در پردازش اطلاعات دریافتی: {e}")

    if not records_to_insert:
        print("دیتایی برای ثبت یافت نشد.")
        return 0

    print(f"   ✅ دریافت موفقیت‌آمیز! در حال آماده‌سازی {len(records_to_insert)} شاخص...")
    
    # تزریق یک‌جای رکوردها به دیتابیس بدون تکرار
    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"🎉 کاوشگر OECD تمام شد! {result.rowcount} شاخص واقعی و تازه از سرور ثبت شد.")
    return result.rowcount

async def fetch_and_store_oecd_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی یک پایگاه داده از سازمان OECD با فرمت SDMX-CSV
    """
    # استخراج ID اصلی (مثلاً OECD_MEI_CLI تبدیل می‌شود به MEI_CLI)
    flow_id = symbol.replace("OECD_", "")
    print(f"🏢 در حال دانلود دیتای تاریخی {symbol} از سرورهای پاریس (OECD)...")
    
    # آدرس API برای دریافت کل دیتای یک Dataflow با فرمت سبک CSV
    url = f"https://sdmx.oecd.org/public/rest/data/{flow_id}/all"
    headers = {
        "Accept": "application/vnd.sdmx.data+csv;version=1.0.0",
        "Accept-Encoding": "gzip, deflate, br",
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
                return {"success": False, "message": "دیتایی برای این شاخص یافت نشد (احتمالاً بایگانی شده)."}
            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(5)

    if not success:
        return {"success": False, "message": "خطا در ارتباط با سرورهای OECD."}

    # پیدا کردن ID این شاخص در دیتابیس خودمان
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را کشف کنید."}

    # خواندن دیتای CSV در حافظه
    csv_data = response.text
    reader = csv.DictReader(io.StringIO(csv_data))
    
    records_to_insert = []
    
    for row in reader:
        try:
            # ساختار استاندارد SDMX-CSV: ستون‌های TIME_PERIOD و OBS_VALUE
            date_str = row.get('TIME_PERIOD')
            value_str = row.get('OBS_VALUE')
            
            if not date_str or not value_str:
                continue
                
            # مدیریت فرمت‌های زمانی مختلف OECD
            if len(date_str) == 4: # سالانه (2023)
                date_obj = date(int(date_str), 1, 1)
            elif '-Q' in date_str: # فصلی (2023-Q1)
                year, q = date_str.split('-Q')
                month = (int(q) * 3) - 2
                date_obj = date(int(year), month, 1)
            elif len(date_str) == 7 and '-' in date_str: # ماهانه (2023-01)
                date_obj = datetime.strptime(date_str, "%Y-%m").date()
            elif len(date_str) == 10: # روزانه (2023-01-15)
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                continue # فرمت‌های عجیب را رد می‌کنیم
                
            records_to_insert.append({
                "indicator_id": indicator.id,
                "date": date_obj,
                "value": float(value_str)
            })
        except Exception as e:
            continue

    if not records_to_insert:
        return {"success": False, "message": "هیچ رکورد زمانی معتبری یافت نشد."}

    # تزریق سریع دیتا به دیتابیس (لقمه‌های ۳۰۰۰ تایی برای جلوگیری از ارور پستگرس)
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