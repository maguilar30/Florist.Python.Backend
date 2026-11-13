from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import AdminUser, CurrentCompany, CurrentUser, DbSession
from app.errors import problem
from app.loyalty import get_reward, member_order_stats, redemption_count, star_count, validate_reward_payload
from app.models.loyalty import LoyaltyReward
from app.models.user import User
from app.schemas.loyalty import (
    LoyaltyMeOut,
    LoyaltyMemberOut,
    LoyaltyRewardOut,
    LoyaltyRewardProgress,
    LoyaltyRewardUpsert,
)

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


def _out(row: LoyaltyReward) -> LoyaltyRewardOut:
    return LoyaltyRewardOut(
        id=row.id,
        name=row.name,
        description=row.description,
        orders_required=row.orders_required,
        kind=row.kind,
        percent=float(row.percent),
        max_discount=float(row.max_discount),
        active=row.active,
    )


def _progress(db: DbSession, company_id: str, row: LoyaltyReward, user_id: str, stars: int) -> LoyaltyRewardProgress:
    used = redemption_count(db, company_id, row.id, user_id)
    toward = stars % row.orders_required if stars >= 0 else 0
    if stars >= row.orders_required * (used + 1):
        toward = row.orders_required
    remaining = max(0, row.orders_required * (used + 1) - stars)
    available = remaining == 0 and row.active
    return LoyaltyRewardProgress(
        **_out(row).model_dump(),
        stars_toward=toward,
        remaining=remaining,
        redeemed_count=used,
        available=available,
    )


def _me_out(db: DbSession, company_id: str, user: User) -> LoyaltyMeOut:
    stars = star_count(db, company_id, user.id)
    rewards = db.scalars(
        select(LoyaltyReward)
        .where(LoyaltyReward.company_id == company_id, LoyaltyReward.active.is_(True))
        .order_by(LoyaltyReward.orders_required.asc(), LoyaltyReward.id.asc())
    )
    return LoyaltyMeOut(
        stars=stars,
        qualifying_orders=stars,
        rewards=[_progress(db, company_id, row, user.id, stars) for row in rewards],
    )


@router.get("/me", response_model=LoyaltyMeOut)
def my_loyalty(user: CurrentUser, db: DbSession, company: CurrentCompany) -> LoyaltyMeOut:
    return _me_out(db, company.id, user)


@router.get("/accounts/{user_id}", response_model=LoyaltyMeOut)
def loyalty_for_account(
    user_id: str, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> LoyaltyMeOut:
    user = db.scalar(select(User).where(User.id == user_id, User.company_id == company.id))
    if user is None:
        raise problem(404, "No encontramos esa cuenta de cliente.")
    return _me_out(db, company.id, user)


@router.get("/members", response_model=list[LoyaltyMemberOut])
def list_loyalty_members(_admin: AdminUser, db: DbSession, company: CurrentCompany) -> list[LoyaltyMemberOut]:
    stats = member_order_stats(db, company.id)
    user_ids = [user_id for user_id, (_orders, stars, _spent) in stats.items() if stars > 0]
    if not user_ids:
        return []
    users = {
        user.id: user
        for user in db.scalars(select(User).where(User.company_id == company.id, User.id.in_(user_ids)))
    }
    members: list[LoyaltyMemberOut] = []
    for user_id in user_ids:
        user = users.get(user_id)
        if user is None:
            continue
        order_count, stars, total_spent = stats[user_id]
        members.append(
            LoyaltyMemberOut(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                stars=stars,
                order_count=order_count,
                total_spent=float(total_spent),
            )
        )
    members.sort(key=lambda row: (-row.stars, -row.total_spent, row.full_name.lower()))
    return members


@router.get("/rewards", response_model=list[LoyaltyRewardOut])
def list_loyalty_rewards(_admin: AdminUser, db: DbSession, company: CurrentCompany) -> list[LoyaltyRewardOut]:
    rows = db.scalars(
        select(LoyaltyReward)
        .where(LoyaltyReward.company_id == company.id)
        .order_by(LoyaltyReward.orders_required.asc(), LoyaltyReward.id.asc())
    )
    return [_out(row) for row in rows]


@router.post("/rewards", response_model=LoyaltyRewardOut, status_code=status.HTTP_201_CREATED)
def create_loyalty_reward(
    payload: LoyaltyRewardUpsert, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> LoyaltyRewardOut:
    kind = validate_reward_payload(kind=payload.kind, percent=payload.percent, max_discount=payload.max_discount)
    row = LoyaltyReward(
        company_id=company.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        orders_required=payload.orders_required,
        kind=kind,
        percent=payload.percent if kind == "percent" else 0,
        max_discount=payload.max_discount if kind == "percent" else 0,
        active=payload.active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.put("/rewards/{reward_id}", response_model=LoyaltyRewardOut)
def update_loyalty_reward(
    reward_id: int,
    payload: LoyaltyRewardUpsert,
    _admin: AdminUser,
    db: DbSession,
    company: CurrentCompany,
) -> LoyaltyRewardOut:
    row = get_reward(db, company.id, reward_id)
    kind = validate_reward_payload(kind=payload.kind, percent=payload.percent, max_discount=payload.max_discount)
    row.name = payload.name.strip()
    row.description = payload.description.strip()
    row.orders_required = payload.orders_required
    row.kind = kind
    row.percent = payload.percent if kind == "percent" else 0
    row.max_discount = payload.max_discount if kind == "percent" else 0
    row.active = payload.active
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loyalty_reward(
    reward_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> None:
    row = get_reward(db, company.id, reward_id)
    db.delete(row)
    db.commit()
