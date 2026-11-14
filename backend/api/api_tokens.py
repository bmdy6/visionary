"""JWT-only personal token management. Plaintext returned exactly once."""
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.models.database import get_db
from backend.models import models
from backend.core.deps import get_current_user
from backend.core.api_tokens import digest, usage_month
from backend.core.billing_config import setting

router = APIRouter(prefix='/user/api-tokens', tags=['api-tokens'])


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


def info(t):
    return {'id': t.id, 'name': t.name, 'prefix': t.prefix, 'suffix': t.suffix,
            'created_at': t.created_at.isoformat() + 'Z',
            'last_used_at': t.last_used_at.isoformat() + 'Z' if t.last_used_at else None,
            'monthly_calls': t.monthly_calls if t.usage_month == usage_month() else 0}


@router.get('')
def list_tokens(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tokens = db.query(models.ApiToken).filter_by(user_id=user.id, revoked_at=None).order_by(models.ApiToken.id.desc()).all()
    return {'tokens': [info(t) for t in tokens], 'enabled': setting('API_TOKENS_ENABLED'), 'limit': setting('API_TOKENS_PER_USER')}


@router.post('')
def create_token(data: TokenCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not setting('API_TOKENS_ENABLED'):
        raise HTTPException(403, 'API 与 MCP 已关闭')
    if not data.name.strip():
        raise HTTPException(422, '名称不能为空')
    # UPDATE locks the account on SQLite and MySQL before checking the cap.
    db.query(models.User).filter_by(id=user.id).update({'id': models.User.id}, synchronize_session=False)
    count = db.query(models.ApiToken).filter_by(user_id=user.id, revoked_at=None).count()
    if count >= setting('API_TOKENS_PER_USER'):
        db.rollback()
        raise HTTPException(409, '有效 Token 数量已达上限，请先撤销不用的 Token')
    raw = 'vsn_' + secrets.token_urlsafe(32)
    row = models.ApiToken(user_id=user.id, name=data.name.strip(), token_hash=digest(raw), prefix=raw[:8], suffix=raw[-4:])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**info(row), 'token': raw}


@router.delete('/{token_id}')
def revoke_token(token_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    updated = db.query(models.ApiToken).filter_by(id=token_id, user_id=user.id, revoked_at=None).update({'revoked_at': datetime.utcnow()})
    if not updated:
        raise HTTPException(404, 'Token 不存在')
    db.commit()
    return {'message': '已撤销'}
