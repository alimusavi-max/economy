import asyncio
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Indicator
from datetime import date
from sqlalchemy import select

from database.models import Indicator, EconomicData

async def auto_discover_imf_indicators(session: AsyncSession):
    """
    کاوشگر عمیق برای دریافت تمام شاخص‌های اقتصادی صندوق بین‌المللی پول (IMF)
    """
    print("🌐 در حال شروع کاوشگر صندوق بین‌المللی پول (IMF)...")
    
    # آدرس API رسمی و سریع IMF
    url = "https://www.imf.org/external/datamapper/api/v1/indicators"
    
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

    if not response_json or "indicators" not in response_json:
        print("❌ خطا در دریافت کاتالوگ IMF.")
        return 0

    records_to_insert = []
    indicators_data = response_json["indicators"]
    
    for symbol, info in indicators_data.items():
        try:
            name = info.get("label", symbol)
            # تمیز کردن نام شاخص‌ها
            clean_name = name.replace("\n", " ").replace("\r", " ").strip()
            
            records_to_insert.append({
                "symbol": f"IMF_{symbol.upper()}"[:50],
                "name": f"IMF: {clean_name}"[:255],
                "source": "IMF",
                "frequency": "Annual", # بیشتر دیتای عمومی IMF سالانه است
                "update_interval_days": 90
            })
        except Exception as e:
            continue

    if not records_to_insert:
        return 0

    # تزریق به دیتابیس بدون تکرار
    stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    print(f"🎉 کاوشگر IMF تمام شد! {result.rowcount} شاخص کلان از صندوق بین‌المللی پول ثبت شد.")
    return result.rowcount

async def fetch_and_store_imf_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی یک شاخص از صندوق بین‌المللی پول (IMF)
    تمرکز بر دیتای اقتصاد جهانی (WLD)
    """
    # استخراج نماد خالص (مثلا IMF_NGDP_RPCH تبدیل می‌شود به NGDP_RPCH)
    imf_id = symbol.replace("IMF_", "")
    print(f"🌐 در حال دانلود دیتای تاریخی {symbol} از صندوق بین‌المللی پول...")
    
    url = f"https://www.imf.org/external/datamapper/api/v1/{imf_id}"
    
    success = False
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                response_json = response.json()
                success = True
                break
            elif response.status_code == 404:
                return {"success": False, "message": "دیتایی در سرور IMF یافت نشد."}
            await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(4)

    if not success or not response_json:
        return {"success": False, "message": "خطا در ارتباط با سرورهای IMF."}

    # پیدا کردن ID این شاخص در دیتابیس خودمان
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        return {"success": False, "message": "ابتدا باید این شاخص را توسط کاوشگر کشف کنید."}

    records_to_insert = []
    
    try:
        # ساختار دیتای IMF: values -> indicator -> country -> year -> value
        indicator_data = response_json.get("values", {}).get(imf_id, {})
        
        if not indicator_data:
            return {"success": False, "message": "دیتای مقداری برای این شاخص وجود ندارد."}

        # ما تمرکزمان روی اقتصاد جهانی است، پس دیتای کل دنیا (WLD) را استخراج می‌کنیم
        # اگر WLD نبود، دیتای اولین منطقه/کشور موجود را برمی‌داریم تا دست خالی برنگردیم
        target_region = "WLD"
        if target_region not in indicator_data:
            target_region = list(indicator_data.keys())[0]

        yearly_data = indicator_data[target_region]
        
        for year_str, value in yearly_data.items():
            try:
                # دیتای IMF معمولاً سالانه است (مثلاً "2023")
                year_int = int(year_str)
                date_obj = date(year_int, 1, 1)
                
                records_to_insert.append({
                    "indicator_id": indicator.id,
                    "date": date_obj,
                    "value": float(value)
                })
            except ValueError:
                continue
                
    except Exception as e:
        return {"success": False, "message": f"خطا در پردازش JSON سرور: {e}"}

    if not records_to_insert:
        return {"success": False, "message": "هیچ رکورد زمانی معتبری یافت نشد."}

    # تزریق به دیتابیس با سرعت بالا
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
        
    print(f"✅ موفق! {inserted_count} رکورد زمانی (دیتای جهانی) برای {symbol} ذخیره شد.")
    return {"success": True, "new_records": inserted_count}