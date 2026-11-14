from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, StrictBool
from ..models.database import get_db
from ..models import models
from ..crud import user as user_crud, recharge as recharge_crud
from ..schemas import user as user_schema
from ..core.deps import get_current_user
from ..core.cos import delete_from_cos

router = APIRouter(prefix="/admin", tags=["admin"])

# 管理员鉴权中间件
def admin_required(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅管理员可操作"
        )
    return current_user

@router.post("/recharge")
def recharge_points(
    target_username: str,
    amount: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(admin_required)
):
    if amount < 1 or amount > 1000000:
        raise HTTPException(422, "积分必须为 1–1000000 的整数")
    # 1. 查找目标用户
    user = user_crud.get_user_by_username(db, username=target_username)
    if not user:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    # 2. 增加积分 (Task 6.1)
    user.points += amount

    # 3. 记录充值日志
    recharge_crud.create_recharge_log(
        db, user_id=user.id, amount=amount, operator_id=admin.id, admin_note="管理员手动充值"
    )

    db.commit()
    return {"message": f"成功为 {target_username} 充值 {amount} 积分", "new_balance": user.points}

@router.get("/recharge/pending")
def list_pending_recharges(
    db: Session = Depends(get_db),
    admin: models.User = Depends(admin_required)
):
    return recharge_crud.get_pending_recharges(db)

@router.post("/recharge/audit/{log_id}")
def audit_recharge_request(
    log_id: int,
    data: user_schema.RechargeAudit,
    db: Session = Depends(get_db),
    admin: models.User = Depends(admin_required)
):
    return recharge_crud.audit_recharge(
        db,
        log_id=log_id,
        admin_id=admin.id,
        approved=data.approved,
        admin_note=data.admin_note
    )

@router.get('/settings/credits')
def credit_settings(admin: models.User = Depends(admin_required)):
    from ..core.billing_config import DEFAULTS, setting
    return {key: {'value': setting(key), 'default': default} for key, default in DEFAULTS.items()}


@router.put('/settings/credits')
def update_credit_settings(values: dict[str, str], db: Session = Depends(get_db), admin: models.User = Depends(admin_required)):
    import json
    import uuid
    from ..core.billing_config import parse_setting, setting
    from ..core.config import invalidate_config_cache
    try:
        for key, value in values.items():
            parse_setting(key, value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    changes = {}
    for key, value in values.items():
        before = setting(key)
        row = db.query(models.SystemConfig).filter_by(config_key=key).first()
        if row:
            row.config_value = value.strip()
        else:
            db.add(models.SystemConfig(config_key=key, config_value=value.strip()))
        changes[key] = {'before': before, 'after': parse_setting(key, value)}
    if changes:
        recharge_crud.create_recharge_log(db, user_id=admin.id, amount=0, operator_id=admin.id,
            admin_note=json.dumps(changes, ensure_ascii=False), trade_no='CONFIG_' + uuid.uuid4().hex)
    db.commit()
    invalidate_config_cache()
    return credit_settings(admin)


def month_start():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get('/dashboard/stats')
def dashboard_stats(db: Session = Depends(get_db), admin: models.User = Depends(admin_required)):
    month = month_start()
    monthly = db.query(models.ImageLog).filter(models.ImageLog.created_at >= month)
    successful = monthly.filter(models.ImageLog.status == 'success')
    recent = db.query(models.ImageLog, models.User.username).join(models.User).order_by(models.ImageLog.created_at.desc(), models.ImageLog.id.desc()).limit(50).all()
    return {
        'summary': {
            'total_users': db.query(models.User).count(),
            'new_users': db.query(models.User).filter(models.User.created_at >= month).count(),
            'monthly_images': successful.count(),
            'sources': {s: successful.filter(models.ImageLog.source == s).count() for s in ('normal', 'assistant', 'mcp')},
            'monthly_revenue': db.query(func.sum(models.RechargeLog.money_amount)).filter(models.RechargeLog.status == 'success', models.RechargeLog.created_at >= month).scalar() or 0,
            'pending_recharges': len(recharge_crud.get_pending_recharges(db)),
            'upstream_cost': monthly.with_entities(func.sum(models.ImageLog.upstream_cost_rmb)).scalar() or 0,
            'unknown_cost_count': monthly.filter(models.ImageLog.upstream_cost_rmb == None).count(),
        },
        'recent_logs': [{'id': l.id, 'username': username, 'prompt': l.prompt, 'source': l.source,
                         'quality': l.quality, 'status': l.status, 'cost_points': l.cost_points,
                         'trial_used': l.trial_used, 'created_at': l.created_at} for l, username in recent]
    }


def user_summary(db, user):
    monthly = db.query(models.ImageLog).filter(models.ImageLog.user_id == user.id, models.ImageLog.created_at >= month_start())
    return {'id': user.id, 'uid': user.uid, 'username': user.username, 'created_at': user.created_at,
            'unlimited_credits': user.unlimited_credits, 'points': user.points, 'frozen_points': user.frozen_points, 'trial_remaining': user.trial_remaining,
            'frozen_trials': user.frozen_trials, 'monthly_images': monthly.filter(models.ImageLog.status == 'success').count(),
            'upstream_cost': monthly.with_entities(func.sum(models.ImageLog.upstream_cost_rmb)).scalar() or 0,
            'unknown_cost_count': monthly.filter(models.ImageLog.upstream_cost_rmb == None).count()}


@router.get('/users')
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), admin: models.User = Depends(admin_required)):
    from fastapi import HTTPException
    if skip < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, '分页参数无效')
    users = db.query(models.User).order_by(models.User.id.desc()).offset(skip).limit(limit).all()
    return [user_summary(db, u) for u in users]


@router.get('/users/{user_id}')
def user_detail(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(admin_required)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, '用户不存在')
    return user_summary(db, user)


class UnlimitedChange(BaseModel):
    enabled: StrictBool


@router.put('/users/{user_id}/unlimited')
def set_unlimited(user_id: int, data: UnlimitedChange, db: Session = Depends(get_db), admin: models.User = Depends(admin_required)):
    import json
    import uuid
    # Serialize concurrent switches and audit only actual changes in the same transaction.
    db.query(models.User).filter_by(id=user_id).update({'id': models.User.id}, synchronize_session=False)
    user = db.query(models.User).filter_by(id=user_id).populate_existing().first()
    if not user:
        raise HTTPException(404, '用户不存在')
    before = user.unlimited_credits
    if before != data.enabled:
        user.unlimited_credits = data.enabled
        recharge_crud.create_recharge_log(db, user_id=user.id, amount=0, operator_id=admin.id,
            admin_note=json.dumps({'unlimited_credits': {'before': before, 'after': data.enabled}}),
            trade_no='UNLIMITED_' + uuid.uuid4().hex)
        db.commit()
    return user_summary(db, user)
