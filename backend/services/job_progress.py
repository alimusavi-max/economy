"""ردیاب ساده‌ی پیشرفت عملیات‌های پس‌زمینه (شخم‌زدن و دریافت داده).

در حافظه نگه‌داری می‌شود؛ برای یک نمونه‌ی تک‌پروسسی FastAPI کافی است و به
فرانت‌اند اجازه می‌دهد نوار پیشرفت زنده نمایش دهد.
"""

from datetime import datetime
from typing import Dict, Optional

# هر job با یک کلید یکتا (مثلاً "fetch:FRED" یا "discover:ALL") نگه‌داری می‌شود
_jobs: Dict[str, dict] = {}


def start_job(key: str, kind: str, label: str, total: int = 0) -> None:
    _jobs[key] = {
        "key": key,
        "kind": kind,            # "fetch" یا "discover"
        "label": label,
        "status": "running",     # running | done | error
        "total": total,
        "done": 0,
        "ok": 0,
        "failed": 0,
        "current": None,
        "message": None,
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }


def update_job(key: str, *, current: Optional[str] = None, ok: bool = None) -> None:
    job = _jobs.get(key)
    if not job:
        return
    job["done"] += 1
    if current is not None:
        job["current"] = current
    if ok is True:
        job["ok"] += 1
    elif ok is False:
        job["failed"] += 1


def finish_job(key: str, message: Optional[str] = None, error: bool = False) -> None:
    job = _jobs.get(key)
    if not job:
        return
    job["status"] = "error" if error else "done"
    job["current"] = None
    job["message"] = message
    job["finished_at"] = datetime.utcnow().isoformat()


def get_all_jobs() -> list:
    """لیست job‌ها را برمی‌گرداند؛ ابتدا در حال اجرا، سپس بقیه."""
    jobs = list(_jobs.values())
    jobs.sort(key=lambda j: (j["status"] != "running", j["started_at"]), reverse=False)
    return jobs


def clear_finished() -> None:
    for key in [k for k, v in _jobs.items() if v["status"] != "running"]:
        _jobs.pop(key, None)
