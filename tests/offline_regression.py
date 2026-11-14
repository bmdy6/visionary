"""Offline checks against an isolated synthetic database; never calls external APIs."""
import os
import secrets
import tempfile
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.chdir(root)
tmp = tempfile.TemporaryDirectory(prefix='visionary-check-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tmp.name) / 'test.db')
os.environ['SECRET_KEY'] = secrets.token_urlsafe(48)

from api.index import app
from backend.models.database import Base, engine, SessionLocal
from backend.models import models
from backend.core.security import get_password_hash, verify_password
from backend.api import image
from backend.schemas.image import ImageCreate
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, func

Base.metadata.create_all(engine)
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(models.User)) == 0
print('PASS: empty ORM initialization, no seeded users')

# Exercise the documented administrator initialization entrypoint with an interactive-password substitute.
from scripts import init_db
pwd = secrets.token_urlsafe(20)
with patch('sys.argv', ['init_db', '--admin', 'offline-admin']), patch('getpass.getpass', return_value=pwd):
    init_db.main()
with SessionLocal() as db:
    u = db.scalar(select(models.User).where(models.User.username == 'offline-admin'))
    uid = u.id
    assert u.is_admin and verify_password(pwd, u.password_hash)
print('PASS: optional administrator initialization and bcrypt hash')

with TestClient(app) as client:
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/auth/debug').status_code == 404
    assert client.get('/api/auth/me').status_code == 401
    login = client.post('/api/auth/login', json={'username':'offline-admin','password':pwd})
    assert login.status_code == 200, login.text
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    me = client.get('/api/auth/me', headers=headers)
    assert me.status_code == 200 and me.json()['is_admin'], me.text
    assert client.get('/api/admin/dashboard/stats', headers=headers).status_code == 200
    assert client.get('/api/image/history', headers=headers).status_code == 200
    spec = client.get('/openapi.json').json()
    assert '/api/image/generate' in spec['paths']
    print('PASS: health, removed debug, auth rejection, JWT login, profile, admin, history, OpenAPI')

# A fake HTTP transport and fake storage confine background generation to this process.
class FakeResponse:
    status_code = 200
    def json(self): return {'data':[{'url':'https://images.example.invalid/result.png'}]}
class FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, *a, **k): return FakeResponse()

async def exercise(success):
    with SessionLocal() as db:
        u = db.get(models.User, uid)
        before = u.points
        result = await image.generate_image(ImageCreate(prompt='offline check'), BackgroundTasks(), db, u)
        db.expire_all()
        assert db.get(models.User, uid).frozen_points == 5
        assert db.get(models.User, uid).points == before
        log_id = result['id']
    def config(key, default=None): return {'OPENAI_API_KEY':'offline-dummy', 'OPENAI_BASE_URL':'https://images.example.invalid/v1'}.get(key, default)
    def storage(*args):
        if not success: raise RuntimeError('synthetic storage failure')
        return 'https://storage.example.invalid/result.png'
    with patch.object(image, 'get_image_provider', return_value='openai'), patch.object(image, 'get_config', side_effect=config), patch.object(image.httpx, 'AsyncClient', FakeClient), patch.object(image, 'store_url', side_effect=storage):
        await image.process_image_task(log_id, 'offline check', 'standard', 'default', 5, uid, 0)
    with SessionLocal() as db:
        u = db.get(models.User, uid)
        log = db.get(models.ImageLog, log_id)
        assert u.frozen_points == 0
        assert u.points == before - (5 if success else 0)
        assert log.status == ('success' if success else 'failed')
    print('PASS: reserve and ' + ('success debit' if success else 'failure release without debit'))

asyncio.run(exercise(True))
asyncio.run(exercise(False))
async def insufficient():
    with SessionLocal() as db:
        u = db.get(models.User, uid); u.points = 0; db.commit()
        try:
            await image.generate_image(ImageCreate(prompt='offline'), BackgroundTasks(), db, u)
        except HTTPException as e:
            assert e.status_code == 403
        else: raise AssertionError('insufficient balance accepted')
        db.expire_all(); assert db.get(models.User,uid).frozen_points == 0
asyncio.run(insufficient())
print('PASS: insufficient credits rejected without reservation')
engine.dispose()
tmp.cleanup()
print('ALL OFFLINE CHECKS PASSED; provider, COS, SMTP, payments not contacted')
