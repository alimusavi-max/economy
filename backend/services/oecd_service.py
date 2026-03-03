import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator

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