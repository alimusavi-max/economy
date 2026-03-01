import requests
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from database.models import Indicator

async def auto_discover_worldbank_indicators(session: AsyncSession):
    """
    دریافت اتوماتیک لیست تمام شاخص‌های بانک جهانی با مکانیزم ضد قطعی
    """
    print("در حال شروع کاوشگر اتوماتیک بانک جهانی (WorldBank)...")
    page = 1
    total_added = 0
    max_retries = 3 # حداکثر ۳ بار تلاش در صورت قطعی

    while True:
        url = f"http://api.worldbank.org/v2/indicator?format=json&per_page=5000&page={page}"
        print(f"در حال دریافت صفحه {page} از بانک جهانی...")
        
        # --- مکانیزم تلاش مجدد (Retry Mechanism) ---
        success = False
        for attempt in range(max_retries):
            try:
                # استفاده از timeout تا در صورت قطعی اینترنت، برنامه قفل نکند
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    success = True
                    break # خروج از حلقه تلاش مجدد
                else:
                    print(f"خطای سرور {response.status_code}. تلاش {attempt + 1} از {max_retries}...")
                    await asyncio.sleep(5) # ۵ ثانیه صبر و تلاش دوباره
            except Exception as e:
                print(f"قطعی ارتباط: {e}. تلاش {attempt + 1} از {max_retries}...")
                await asyncio.sleep(10) # ۱۰ ثانیه صبر در صورت قطعی اینترنت
        
        if not success:
            print(f"دریافت صفحه {page} پس از {max_retries} بار تلاش با شکست مواجه شد. عبور از این صفحه...")
            break
        # -------------------------------------------
            
        data = response.json()
        if len(data) < 2:
            break
            
        indicators_list = data[1]
        if not indicators_list:
            break
            
        records_to_insert = []
        for ind in indicators_list:
            records_to_insert.append({
                "symbol": ind['id'].upper(),
                "name": ind['name'],
                "source": "WORLDBANK",
                "frequency": "Yearly",
                "update_interval_days": 180
            })
            
        if records_to_insert:
            stmt = insert(Indicator).values(records_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=['symbol'])
            result = await session.execute(stmt)
            await session.commit()
            total_added += result.rowcount
            
        pagination = data[0]
        if page >= pagination['pages']:
            break
        
        page += 1
        await asyncio.sleep(1) # یک ثانیه مکث بین هر صفحه برای جلوگیری از بلاک شدن توسط سرور
        
    print(f"کاوشگر بانک جهانی تمام شد! {total_added} شاخص جدید ثبت شد.")
    return total_added