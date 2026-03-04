from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.models import Indicator, User, UserDashboardItem

router = APIRouter(prefix="/api/users", tags=["Users"])


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=2, max_length=150)


class DashboardConfigRequest(BaseModel):
    symbols: List[str]


@router.get("")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("")
async def create_user(request: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    username = request.username.strip().lower()
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="این نام کاربری قبلا ثبت شده است.")

    user = User(username=username, display_name=request.display_name.strip())
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"id": user.id, "username": user.username, "display_name": user.display_name}


@router.get("/{user_id}/dashboard")
async def get_user_dashboard(user_id: int, db: AsyncSession = Depends(get_db)):
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    rows = await db.execute(
        select(UserDashboardItem)
        .where(UserDashboardItem.user_id == user_id)
        .order_by(UserDashboardItem.position.asc(), UserDashboardItem.created_at.asc())
    )
    items = rows.scalars().all()

    return {
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name},
        "symbols": [item.indicator_symbol for item in items],
    }


@router.put("/{user_id}/dashboard")
async def update_user_dashboard(user_id: int, request: DashboardConfigRequest, db: AsyncSession = Depends(get_db)):
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    clean_symbols = [s.strip().upper() for s in request.symbols if s.strip()]
    if len(clean_symbols) > 12:
        raise HTTPException(status_code=400, detail="حداکثر ۱۲ نمودار در داشبورد پیش‌فرض مجاز است.")

    if clean_symbols:
        valid_rows = await db.execute(select(Indicator.symbol).where(Indicator.symbol.in_(clean_symbols)))
        valid_symbols = set(valid_rows.scalars().all())
        invalid = [s for s in clean_symbols if s not in valid_symbols]
        if invalid:
            raise HTTPException(status_code=400, detail=f"نمادهای نامعتبر: {', '.join(invalid)}")

    await db.execute(delete(UserDashboardItem).where(UserDashboardItem.user_id == user_id))

    for idx, sym in enumerate(clean_symbols):
        db.add(UserDashboardItem(user_id=user_id, indicator_symbol=sym, position=idx))

    await db.commit()
    return {"success": True, "symbols": clean_symbols}
