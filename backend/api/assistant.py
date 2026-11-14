"""User-owned conversation history and immutable, versioned generation proposals."""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.models.database import get_db
from backend.models import models
from backend.core.deps import get_current_user
from backend.core.billing_config import setting
from backend.core.assistant import PlanData, discuss
from backend.core.storage import store_base64
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix='/assistant', tags=['assistant'])


def require_enabled():
    if not setting('ASSISTANT_MODE_ENABLED'):
        raise HTTPException(403, 'AI 助手模式已关闭')


def owned(db, conversation_id, user_id):
    row = db.query(models.AssistantConversation).filter_by(id=conversation_id, user_id=user_id).first()
    if not row:
        raise HTTPException(404, '对话不存在')
    return row


def latest_plan(db, conversation_id):
    return db.query(models.AssistantPlan).filter_by(plan_id=conversation_id).order_by(models.AssistantPlan.version.desc()).first()


def serialize(db, row):
    p = latest_plan(db, row.id)
    return {'id':row.id, 'revision':row.revision, 'messages':json.loads(row.messages),
            'reference_url':row.reference_url, 'reference_name':row.reference_name,
            'plan': {'plan_id':p.plan_id, 'version':p.version, 'data':json.loads(p.data), 'task_id':p.task_id} if p else None}


def claim_revision(db, row, expected):
    changed = db.query(models.AssistantConversation).filter_by(id=row.id, revision=expected).update(
        {'revision':models.AssistantConversation.revision + 1}, synchronize_session=False)
    if not changed:
        db.rollback()
        raise HTTPException(409, '对话已更新，请刷新后重试')


@router.post('/conversations')
def new_conversation(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_enabled()
    row = models.AssistantConversation(id=str(uuid.uuid4()), user_id=user.id)
    db.add(row)
    db.commit()
    return serialize(db, row)


@router.get('/conversations/latest')
def current_conversation(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.query(models.AssistantConversation).filter_by(user_id=user.id).order_by(models.AssistantConversation.created_at.desc()).first()
    return serialize(db, row) if row else None


@router.get('/conversations/{conversation_id}')
def get_conversation(conversation_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return serialize(db, owned(db, conversation_id, user.id))


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    revision: int = Field(ge=0)
    reference_data: str | None = Field(default=None, max_length=8 * 1024 * 1024)
    reference_name: str | None = Field(default=None, max_length=120)


@router.post('/conversations/{conversation_id}/messages')
async def chat(conversation_id: str, payload: ChatInput, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_enabled()
    row = owned(db, conversation_id, user.id)
    if row.revision != payload.revision:
        raise HTTPException(409, '对话已更新，请刷新后重试')
    if not payload.message.strip():
        raise HTTPException(422, '消息不能为空')
    messages = json.loads(row.messages)
    if len(messages) >= 100:
        raise HTTPException(422, '当前对话已达上限，请新建对话')
    reference_url, reference_name = row.reference_url, row.reference_name
    if payload.reference_data:
        if not payload.reference_data.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')):
            raise HTTPException(422, '参考图仅支持 PNG、JPEG、WebP')
        try:
            reference_url = await run_in_threadpool(store_base64, payload.reference_data, 'assistant_ref_' + uuid.uuid4().hex + '.png')
        except Exception:
            raise HTTPException(422, '参考图保存失败，请检查图片后重试') from None
        reference_name = payload.reference_name or '参考图'
    previous = latest_plan(db, row.id)
    messages.append({'role':'user', 'content':payload.message.strip(), 'reference_name':reference_name if payload.reference_data else None})
    try:
        reply, demo = await discuss(messages, json.loads(previous.data) if previous else None, bool(reference_url))
    except Exception:
        # Never silently fall back on a failed paid model or persist a partial turn.
        raise HTTPException(502, '对话模型返回失败或方案格式无效，请重试；未生成、未扣积分') from None
    claim_revision(db, row, payload.revision)
    messages.append({'role':'assistant', 'content':reply.reply, 'demo':demo})
    row.messages = json.dumps(messages, ensure_ascii=False)
    row.reference_url, row.reference_name = reference_url, reference_name
    if reply.plan:
        data = reply.plan.model_dump()
        data['ref_image_url'] = reference_url
        db.add(models.AssistantPlan(plan_id=row.id, version=(previous.version + 1) if previous else 1, data=json.dumps(data, ensure_ascii=False)))
    db.commit()
    db.refresh(row)
    return serialize(db, row)


class EditInput(BaseModel):
    revision: int = Field(ge=0)
    plan: PlanData
    remove_reference: bool = False


@router.put('/conversations/{conversation_id}/plan')
def edit_plan(conversation_id: str, payload: EditInput, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_enabled()
    row = owned(db, conversation_id, user.id)
    p = latest_plan(db, row.id)
    if not p:
        raise HTTPException(404, '请先聊出一个方案')
    if not payload.plan.prompt.strip():
        raise HTTPException(422, '画面描述不能为空')
    claim_revision(db, row, payload.revision)
    if payload.remove_reference:
        row.reference_url, row.reference_name = None, None
    data = payload.plan.model_dump()
    data['ref_image_url'] = row.reference_url
    db.add(models.AssistantPlan(plan_id=row.id, version=p.version + 1, data=json.dumps(data, ensure_ascii=False)))
    db.commit()
    db.refresh(row)
    return serialize(db, row)
