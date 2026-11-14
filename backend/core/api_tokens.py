"""Personal tokens: no plaintext persistence and no authentication cache."""
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import case
from backend.models import models


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def usage_month():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m')


def authenticate(db, raw):
    row = db.query(models.ApiToken).filter_by(token_hash=digest(raw), revoked_at=None).first()
    if not row:
        raise HTTPException(401, 'API Token 无效或已撤销', headers={'WWW-Authenticate': 'Bearer'})
    user = db.get(models.User, row.user_id)
    if not user:
        raise HTTPException(401, 'API Token 账户不存在')
    month = usage_month()
    updated = db.query(models.ApiToken).filter_by(id=row.id, revoked_at=None).update({
        'last_used_at': datetime.utcnow(), 'usage_month': month,
        'monthly_calls': case((models.ApiToken.usage_month == month, models.ApiToken.monthly_calls + 1), else_=1)
    }, synchronize_session=False)
    if not updated:
        db.rollback()
        raise HTTPException(401, 'API Token 已撤销')
    db.commit()
    user._api_token_id = row.id
    return user
