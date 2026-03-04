import asyncio
import requests
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Indicator, EconomicData

# 🎭 لباس مبدل ثابت برای دور زدن فایروال تمام بانک‌های جهان
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

async def auto_discover_central_bank(session: AsyncSession, bank_code: str):
    """
    کاوشگر جهانی بانک‌های مرکزی با سیستم صفحه‌بندی (Pagination) هوشمند
    """
    print(f"🏦 در حال نفوذ به کاتالوگ بانک مرکزی {bank_code}...")
    
    offset = 0
    limit = 50  # 👈 احترام به قوانین سرور (درخواست بسته‌های ۵۰ تایی)
    total_inserted = 0
    
    while True:
        url = f"https://api.db.nomics.world/v22/datasets/{bank_code}?limit={limit}&offset={offset}"
        
        try:
            # تایم‌اوت را بالاتر می‌بریم برای اینترنت‌های نوسان‌دار
            response = requests.get(url, headers=HEADERS, timeout=40)
            
            if response.status_code == 400:
                print(f"   ❌ سرور درخواست را رد کرد. (احتمالا پارامترهای نامعتبر)")
                break
            elif response.status_code != 200:
                print(f"   ❌ سرور کد {response.status_code} را برگرداند.")
                break
                
            data = response.json()
        except requests.exceptions.ConnectionError:
            print(f"   ❌ خطای قطعی اینترنت یا VPN در دریافت {bank_code}.")
            break
        except Exception as e:
            print(f"   ❌ خطای ناشناخته: {e}")
            break
            
        datasets = data.get("datasets", {}).get("docs", [])
        
        # اگر دیتاسِتی در این صفحه نبود، یعنی به آخر خط رسیدیم
        if not datasets:
            break
            
        records_to_insert = []
        for ds in datasets:
            code = ds.get("code")
            name = ds.get("name")
            if code:
                records_to_insert.append({
                    "symbol": f"DBN_{bank_code}_{code}"[:50],
                    "name": f"{bank_code}: {name}"[:255],
                    "source": "DBNOMICS",
                    "frequency": "Mixed",
                    "update_interval_days": 15
                })
                
        if records_to_insert:
            stmt = insert(Indicator).values(records_to_insert).on_conflict_do_nothing(index_elements=["symbol"])
            result = await session.execute(stmt)
            await session.commit()
            total_inserted += result.rowcount
            
        # اگر تعداد دیتاسِت‌های دریافتی کمتر از ظرفیت صفحه بود، یعنی صفحه آخر است
        if len(datasets) < limit:
            break
            
        # رفتن به صفحه بعد
        offset += limit
        print(f"   📄 دریافت {offset} دیتاسِت... در حال ورق زدن به صفحه بعد.")
        await asyncio.sleep(1) # استراحت ۱ ثانیه‌ای برای جلوگیری از بلاک شدن
        
    if total_inserted > 0:
        print(f"🎉 عملیات موفق! {total_inserted} پایگاه داده از {bank_code} کشف شد.")
    else:
        print(f"⚠️ پایگاه داده جدیدی برای {bank_code} یافت/ثبت نشد.")
        
    return total_inserted

async def fetch_and_store_dbnomics_data(session: AsyncSession, symbol: str):
    """
    دانلود دیتای تاریخی از سرور یکپارچه بانک‌های مرکزی
    """
    parts = symbol.replace("DBN_", "").split("_", 1)
    if len(parts) != 2:
        return {"success": False, "message": "فرمت نماد نامعتبر است."}
        
    bank_code, dataset_code = parts
    print(f"🏦 در حال استخراج دیتای تاریخی {symbol} از بانک {bank_code}...")
    
    url = f"https://api.db.nomics.world/v22/series/{bank_code}/{dataset_code}?limit=1&observations=1"
    
    success = False
    for attempt in range(3):
        try:
            res = requests.get(url, headers=HEADERS, timeout=30)
            if res.status_code == 200:
                data = res.json()
                success = True
                break
            await asyncio.sleep(2)
        except:
            await asyncio.sleep(4)
            
    if not success:
        return {"success": False, "message": "ارتباط با سرور بانک برقرار نشد."}
        
    result = await session.execute(select(Indicator).where(Indicator.symbol == symbol))
    indicator = result.scalar_one_or_none()
    
    if not indicator:
        return {"success": False, "message": "ابتدا شاخص را کشف کنید."}
        
    records_to_insert = []
    try:
        series_list = data.get("series", {}).get("docs", [])
        if not series_list:
            return {"success": False, "message": "دیتایی برای این شاخص وجود ندارد."}
            
        series_data = series_list[0]
        periods = series_data.get("period", [])
        values = series_data.get("value", [])
        
        for p, v in zip(periods, values):
            if v == "NA" or v is None:
                continue
            try:
                if len(p) == 4:
                    d = date(int(p), 1, 1)
                elif '-Q' in p:
                    y, q = p.split('-Q')
                    d = date(int(y), int(q)*3 - 2, 1)
                elif len(p) == 7 and '-' in p:
                    y, m = p.split('-')
                    d = date(int(y), int(m), 1)
                else:
                    d = datetime.strptime(p, "%Y-%m-%d").date()
                    
                records_to_insert.append({
                    "indicator_id": indicator.id,
                    "date": d,
                    "value": float(v)
                })
            except:
                continue
    except Exception as e:
        return {"success": False, "message": "خطا در پردازش دیتای بانک."}
        
    if not records_to_insert:
        return {"success": False, "message": "رکورد معتبری یافت نشد."}
        
    inserted_count = 0
    batch_size = 3000
    for i in range(0, len(records_to_insert), batch_size):
        batch = records_to_insert[i:i + batch_size]
        stmt = insert(EconomicData).values(batch).on_conflict_do_nothing(index_elements=['indicator_id', 'date'])
        res = await session.execute(stmt)
        inserted_count += res.rowcount
        
    indicator.last_updated = date.today()
    session.add(indicator)
    await session.commit()
    
    print(f"✅ موفق! {inserted_count} رکورد زمانی ذخیره شد.")
    return {"success": True, "new_records": inserted_count}

async def auto_discover_all_central_banks(session: AsyncSession):
    """
    عملیات نفوذ سراسری به تمام بانک‌های مرکزی مهم جهان
    """
    print("🌍 در حال آماده‌سازی شاه‌کلید برای تمام بانک‌های مرکزی جهان...")
    
    central_banks = [
        "BOE",      # بانک مرکزی انگلیس (Bank of England) - تایید شده ✅
        "BOJ",      # بانک مرکزی ژاپن (Bank of Japan) - تایید شده ✅
        "BOC",      # بانک مرکزی کانادا (Bank of Canada) - تایید شده ✅
        "RBA",      # بانک مرکزی استرالیا (Reserve Bank of Australia) - تایید شده ✅
        "BUBA",     # بانک مرکزی آلمان (Bundesbank) - تایید شده ✅
        "BDF",      # بانک مرکزی فرانسه (Banque de France) - تایید شده ✅
        "TCMB",     # بانک مرکزی ترکیه (Central Bank of Turkey) - تایید شده ✅
        "BCB",      # بانک مرکزی برزیل (Banco Central do Brasil) - تایید شده ✅
        "SAMA",     # سازمان پولی عربستان سعودی (Saudi Monetary Authority) - تایید شده ✅
        "BI",       # بانک مرکزی اندونزی (Bank Indonesia) - تایید شده ✅
        "SARB"      # بانک مرکزی آفریقای جنوبی (South African Reserve Bank) - تایید شده ✅
    ]

    total_discovered = 0
    for bank in central_banks:
        try:
            count = await auto_discover_central_bank(session, bank)
            total_discovered += count
            # استراحت ۲ ثانیه‌ای بین هر بانک برای جلوگیری از مسدود شدن IP
            await asyncio.sleep(2)
        except Exception as e:
            print(f"   ⚠️ پرش از {bank} به دلیل خطا: {e}")

    print(f"\n🎉 ماموریت جهانی تمام شد! در مجموع {total_discovered} پایگاه داده از {len(central_banks)} کشور قدرتمند به چنگ آمد.")
    return total_discovered