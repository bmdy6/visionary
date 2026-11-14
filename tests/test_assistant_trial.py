"""Assistant and billing contracts; synthetic SQLite and loopback only."""
import asyncio
import json
import os
import time
import unittest
from unittest.mock import patch
from test_runnable import TEMP, PNG, DATA, app, models, Base, engine, SessionLocal, config
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from backend.api import image
from backend.schemas.image import ImageCreate
from backend.core.security import create_access_token


class AssistantTrialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)

    def setUp(self):
        config._last_fetch = 0
        config._config_cache = {}
        self.env = patch.dict(os.environ, {'IMAGE_PROVIDER': 'demo', 'STORAGE_BACKEND': 'local', 'OPENAI_API_KEY': '', 'DASHSCOPE_API_KEY': ''})
        self.env.start()
        with SessionLocal() as db:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.add_all([models.User(username='creator', uid='100001', points=10), models.User(username='admin', uid='100002', points=100, is_admin=True)])
            db.commit()
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'creator'})}
        self.admin = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin'})}

    def tearDown(self):
        self.env.stop()
        self.client.close()
        config._last_fetch = 0

    def test_phone_registration_grants_separate_trials(self):
        r = self.client.post('/api/auth/register-phone', json={'username':'new-creator', 'phone':'10000000001', 'password':'synthetic-password', 'captcha_code':'1234'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['user']['trial_remaining'], 5)
        self.assertEqual(r.json()['user']['points'], 10)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.User).filter_by(username='new-creator').count(), 1)

    def test_admin_config_is_validated_audited_and_immediate(self):
        path = '/api/admin/settings/credits'
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 403)
        self.assertEqual(self.client.put(path, headers=self.admin, json={'TIER_COSTS':'standard:-1,hd:10,master:15'}).status_code, 422)
        r = self.client.put(path, headers=self.admin, json={'NEW_USER_FREE_GENERATIONS':'0', 'NEW_USER_POINTS':'23', 'TIER_COSTS':'standard:7,hd:11,master:19', 'ASSISTANT_MODE_ENABLED':'false'})
        self.assertEqual(r.status_code, 200, r.text)
        info = self.client.get('/api/image/config').json()
        self.assertEqual(info['pricing']['standard'], 7)
        self.assertFalse(info['assistant_mode_enabled'])
        with SessionLocal() as db:
            audit = db.query(models.RechargeLog).filter(models.RechargeLog.trade_no.like('CONFIG_%')).one()
            self.assertEqual(audit.amount, 0)
            self.assertEqual(audit.operator_id, 2)
            self.assertIn('23', audit.admin_note)

    def test_trial_reserve_success_failure_and_tier_restriction(self):
        async def exercise(tier, fail=False):
            with SessionLocal() as db:
                u = db.get(models.User, 1)
                u.trial_remaining = 2
                db.commit()
                tasks = BackgroundTasks()
                res = await image.generate_image(ImageCreate(prompt='trial', quality=tier), tasks, db, u)
                db.expire_all()
                u = db.get(models.User, 1)
                self.assertEqual(u.frozen_trials, int(tier == 'standard'))
                self.assertEqual(u.frozen_points, 0 if tier == 'standard' else 10)
            with patch.object(image, 'store_base64', side_effect=OSError('synthetic failure')) if fail else patch.object(image, 'store_base64', return_value='/api/creations/test.png'):
                await tasks()
            with SessionLocal() as db:
                u = db.get(models.User, 1)
                self.assertEqual(u.trial_remaining, 1 if tier == 'standard' and not fail else 2)
                self.assertEqual(u.frozen_trials, 0)
                self.assertEqual(u.frozen_points, 0)
                self.assertEqual(u.points, 0 if tier == 'hd' and not fail else 10)
        asyncio.run(exercise('standard'))
        asyncio.run(exercise('standard', True))
        asyncio.run(exercise('hd'))

    def test_demo_chat_edit_ownership_and_confirmation_idempotency(self):
        c = self.client.post('/api/assistant/conversations', headers=self.headers).json()
        path = '/api/assistant/conversations/' + c['id']
        self.assertEqual(self.client.get(path, headers=self.admin).status_code, 404)
        r = self.client.post(path + '/messages', headers=self.headers, json={'message':'给妈妈的向日葵生日贺卡', 'revision':0})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()['plan'])
        c = self.client.post(path + '/messages', headers=self.headers, json={'message':'竖版，写妈妈生日快乐', 'revision':r.json()['revision']}).json()
        p = c['plan']
        self.assertEqual(p['version'], 1)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.ImageLog).count(), 0)
            self.assertEqual(db.get(models.User, 1).frozen_points, 0)
        edited = self.client.put(path + '/plan', headers=self.headers, json={'revision': c['revision'], 'plan':{**p['data'], 'prompt':'浅色背景的向日葵贺卡'}})
        self.assertEqual(edited.status_code, 200, edited.text)
        p = edited.json()['plan']
        self.assertEqual(p['version'], 2)
        self.assertEqual(self.client.put(path + '/plan', headers=self.headers, json={'revision':c['revision'], 'plan':p['data']}).status_code, 409)
        payload = {'prompt':'tampered', 'quality':'master', 'plan_id':p['plan_id'], 'plan_version':p['version']}
        with patch.object(image, 'store_base64', return_value='/api/creations/test.png'):
            a = self.client.post('/api/image/generate', headers=self.headers, json=payload)
            b = self.client.post('/api/image/generate', headers=self.headers, json=payload)
        self.assertEqual(a.status_code, 200, a.text)
        self.assertEqual(a.json()['id'], b.json()['id'])
        with SessionLocal() as db:
            log = db.query(models.ImageLog).one()
            self.assertEqual(log.source, 'assistant')
            self.assertEqual(log.prompt, '浅色背景的向日葵贺卡')
            self.assertEqual(log.quality, 'standard')
            self.assertEqual(log.aspect_ratio, '9:16')
            self.assertEqual(db.get(models.User, 1).points, 5)
        self.assertEqual(self.client.get(path, headers=self.headers).json()['plan']['task_id'], a.json()['id'])

    def test_config_precedence_and_cache_invalidation(self):
        from backend.core.billing_config import setting
        with patch.dict(os.environ, {'NEW_USER_POINTS':'31'}):
            self.assertEqual(setting('NEW_USER_POINTS'), 31)
            with SessionLocal() as db:
                db.add(models.SystemConfig(config_key='NEW_USER_POINTS', config_value='41'))
                db.commit()
            config.invalidate_config_cache()
            self.assertEqual(setting('NEW_USER_POINTS'), 41)
            with SessionLocal() as db:
                db.query(models.SystemConfig).filter_by(config_key='NEW_USER_POINTS').one().config_value = ''
                db.commit()
            self.assertEqual(setting('NEW_USER_POINTS'), 41)  # cache, until invalidated
            config.invalidate_config_cache()
            self.assertEqual(setting('NEW_USER_POINTS'), 31)
        with patch.dict(os.environ, {'NEW_USER_POINTS':''}):
            self.assertEqual(setting('NEW_USER_POINTS'), 10)

    def test_additive_migration_keeps_existing_users_at_zero_trials(self):
        from sqlalchemy import create_engine, text
        from backend.models.migrations import migrate
        old = create_engine('sqlite:///' + str(__import__('pathlib').Path(TEMP.name) / 'migration.db'))
        try:
            with old.begin() as conn:
                conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, points INTEGER)'))
                conn.execute(text('INSERT INTO users VALUES (1,73)'))
                conn.execute(text('CREATE TABLE image_logs (id INTEGER PRIMARY KEY)'))
            migrate(old)
            migrate(old)
            with old.connect() as conn:
                self.assertEqual(tuple(conn.execute(text('SELECT points, trial_remaining, frozen_trials FROM users')).one()), (73,0,0))
        finally:
            old.dispose()

    def test_zero_grant_and_configured_invitation_rewards(self):
        self.client.put('/api/admin/settings/credits', headers=self.admin, json={'NEW_USER_FREE_GENERATIONS':'0', 'NEW_USER_POINTS':'21', 'INVITE_REWARD_POINTS':'3', 'INVITE_DAILY_LIMIT':'1'})
        r = self.client.post('/api/auth/register-phone', json={'username':'invitee', 'phone':'10000000002', 'password':'synthetic-password', 'captcha_code':'1234','invite_code':'100001'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual((r.json()['user']['points'],r.json()['user']['trial_remaining']),(24,0))
        with patch.object(image,'store_base64',return_value='/api/creations/test.png'):
            h = {'Authorization':'Bearer '+r.json()['access_token']}
            self.assertEqual(self.client.post('/api/image/generate',headers=h,json={'prompt':'first'}).status_code,200)
        from backend.crud.recharge import can_receive_invitation_reward
        with SessionLocal() as db:
            self.assertEqual(db.get(models.User,1).points,13)
            self.assertFalse(can_receive_invitation_reward(db,1))
        self.assertEqual(self.client.get('/api/auth/invitation-stats',headers=self.headers).json()['daily_limit'],1)

    def test_atomic_plan_claim_with_parallel_requests(self):
        from concurrent.futures import ThreadPoolExecutor
        c = self.client.post('/api/assistant/conversations',headers=self.headers).json()
        path = '/api/assistant/conversations/'+c['id']
        for message in ['贺卡','竖版']:
            c=self.client.post(path+'/messages',headers=self.headers,json={'message':message,'revision':c['revision']}).json()
        p=c['plan']
        payload={'prompt':'ignored','plan_id':p['plan_id'],'plan_version':p['version']}
        # Hold background work so every duplicate overlaps the pending reservation.
        async def no_background(*args,**kwargs): pass
        with patch.object(image,'process_image_task',no_background), ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:self.client.post('/api/image/generate',headers=self.headers,json=payload),range(4)))
        self.assertTrue(all(r.status_code==200 for r in responses),[r.text for r in responses])
        self.assertEqual(len({r.json()['id'] for r in responses}),1)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.ImageLog).count(),1)
            self.assertEqual(db.get(models.User,1).frozen_points,5)

    def test_trial_reservations_and_reset_do_not_resurrect(self):
        async def exercise():
            with SessionLocal() as db:
                u=db.get(models.User,1);u.trial_remaining=1;db.commit()
                tasks=BackgroundTasks()
                for n in range(2):
                    await image.generate_image(ImageCreate(prompt='parallel '+str(n)),tasks,db,u)
                db.expire_all();u=db.get(models.User,1)
                self.assertEqual((u.frozen_trials,u.frozen_points),(1,5))
                from backend.crud.image import reset_active_tasks
                reset_active_tasks(db,1)
                db.refresh(u)
                self.assertEqual((u.frozen_trials,u.frozen_points),(0,0))
            with patch.object(image,'store_base64',return_value='/api/creations/test.png'):
                await tasks()
            with SessionLocal() as db:
                u=db.get(models.User,1)
                self.assertEqual((u.trial_remaining,u.points,u.frozen_trials,u.frozen_points),(1,10,0,0))
                self.assertTrue(all(l.status=='failed' for l in db.query(models.ImageLog)))
        asyncio.run(exercise())

    def test_model_uses_loopback_and_rejects_malformed_proposals(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        responses=[{'reply':'请确认方案','plan':{'prompt':'回环贺卡','aspect_ratio':'9:16','quality':'standard','style':'watercolor'}}, {'reply':'bad','plan':{'prompt':'x','quality':'not-a-tier'}}]
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['content-length']))))
                content=json.dumps(responses.pop(0),ensure_ascii=False)
                body=json.dumps({'choices':[{'message':{'content':content}}]}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'loopback-only','OPENAI_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1'}):
                c=self.client.post('/api/assistant/conversations',headers=self.headers).json()
                path='/api/assistant/conversations/'+c['id']
                r=self.client.post(path+'/messages',headers=self.headers,json={'message':'贺卡','revision':0})
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()['plan']['data']['style'],'watercolor')
                r=self.client.post(path+'/messages',headers=self.headers,json={'message':'改一下','revision':1})
                self.assertEqual(r.status_code,502,r.text)
                saved=self.client.get(path,headers=self.headers).json()
                self.assertEqual((saved['revision'],len(saved['messages'])),(1,2))
                self.assertEqual(captured[0]['model'],'gpt-4o-mini')
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__ == '__main__':
    unittest.main()
