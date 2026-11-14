"""Personal token scope and shared settlement contracts, synthetic data only."""
import asyncio
from unittest.mock import patch
import unittest
import test_assistant_trial as fixtures
from test_runnable import models, SessionLocal
from backend.api import image
from backend.schemas.image import ImageCreate
from fastapi import BackgroundTasks


class ApiMcpTest(unittest.TestCase):
    setUpClass = classmethod(fixtures.AssistantTrialTest.setUpClass.__func__)
    setUp = fixtures.AssistantTrialTest.setUp
    tearDown = fixtures.AssistantTrialTest.tearDown
    def token(self, headers=None):
        r = self.client.post('/api/user/api-tokens', headers=headers or self.headers, json={'name': 'Agent'})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_token_hash_scope_usage_revocation(self):
        token = self.token()
        raw = token['token']
        self.assertTrue(raw.startswith('vsn_'))
        auth = {'Authorization': 'Bearer ' + raw}
        with SessionLocal() as db:
            row = db.query(models.ApiToken).one()
            self.assertNotEqual(row.token_hash, raw)
            self.assertNotIn(raw, str(row.__dict__))
        for path in ['/api/image/balance', '/api/image/styles']:
            self.assertEqual(self.client.get(path, headers=auth).status_code, 200)
        for path, payload in [('/api/user/recharge/apply', {'money_amount':1}), ('/api/auth/change-password', {'old_password':'old','new_password':'new'}), ('/api/user/api-tokens', {'name':'nested'}), ('/api/admin/recharge?target_username=creator&amount=10', {})]:
            self.assertEqual(self.client.post(path, headers=auth, json=payload).status_code, 401, path)
        self.assertEqual(self.client.get('/api/auth/me', headers=auth).status_code, 401)
        listed = self.client.get('/api/user/api-tokens', headers=self.headers).json()
        self.assertNotIn(raw, str(listed))
        self.assertEqual(listed['tokens'][0]['suffix'], raw[-4:])
        self.assertEqual(listed['tokens'][0]['monthly_calls'], 2)
        self.assertEqual(self.client.delete(f"/api/user/api-tokens/{token['id']}", headers=self.admin).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/user/api-tokens/{token['id']}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/image/balance', headers=auth).status_code, 401)

    def test_direct_generation_and_insufficient_no_task(self):
        auth = {'Authorization':'Bearer ' + self.token()['token']}
        r = self.client.post('/api/image/generate', headers=auth, json={'prompt':'demo', 'quality':'hd'})
        self.assertEqual(r.status_code, 200, r.text)
        task_id = r.json()['id']
        status = self.client.get(f'/api/image/status/{task_id}', headers=auth)
        self.assertEqual(status.json()['status'], 'success')
        self.assertEqual(status.json()['source'], 'mcp')
        self.assertEqual(self.client.get(f'/api/image/status/{task_id}', headers=self.admin).status_code, 404)
        r = self.client.post('/api/image/generate', headers=auth, json={'prompt':'cannot afford'})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()['detail']['balance'], 0)
        self.assertEqual(r.json()['detail']['required'], 5)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.ImageLog).count(), 1)
            self.assertEqual(db.get(models.User, 1).frozen_points, 0)

    def test_unlimited_toggle_audit_and_snapshot(self):
        path = '/api/admin/users/1/unlimited'
        self.assertEqual(self.client.put(path, headers=self.headers, json={'enabled':True}).status_code, 403)
        self.assertEqual(self.client.put(path, headers=self.admin, json={'enabled':True}).status_code, 200)
        with SessionLocal() as db:
            user = db.get(models.User, 1)
            user.points, user.trial_remaining = 0, 2
            db.commit()
            tasks = BackgroundTasks()
            result = asyncio.run(image.generate_image(ImageCreate(prompt='unlimited'), tasks, db, user))
            db.expire_all()
            self.assertEqual((user.frozen_points, user.frozen_trials), (0, 0))
        self.client.put(path, headers=self.admin, json={'enabled':False})
        asyncio.run(tasks())
        with SessionLocal() as db:
            user = db.get(models.User, 1)
            log = db.get(models.ImageLog, result['id'])
            self.assertEqual((user.points, user.trial_remaining), (0, 2))
            self.assertEqual((log.cost_points, log.trial_used, log.status), (0, False, 'success'))
            self.assertEqual(log.upstream_cost_rmb, 0)
            self.assertEqual(db.query(models.RechargeLog).filter(models.RechargeLog.trade_no.like('UNLIMITED_%')).count(), 2)

    def test_limits_disable_and_validation(self):
        path = '/api/admin/settings/credits'
        self.assertEqual(self.client.put(path, headers=self.admin, json={'API_TOKENS_PER_USER':'1'}).status_code, 200)
        t = self.token()
        self.assertEqual(self.client.post('/api/user/api-tokens', headers=self.headers, json={'name':'overflow'}).status_code, 409)
        auth = {'Authorization':'Bearer ' + t['token']}
        self.client.put(path, headers=self.admin, json={'API_TOKENS_ENABLED':'false'})
        self.assertEqual(self.client.get('/api/image/balance', headers=auth).status_code, 403)
        self.assertEqual(self.client.post('/api/user/api-tokens', headers=self.headers, json={'name':'off'}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/user/api-tokens/{t['id']}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.put(path, headers=self.admin, json={'MCP_MAX_IMAGES_PER_CALL':'-1'}).status_code, 422)

    def test_month_rollover_cap_serialization_and_no_scope_escalation(self):
        from concurrent.futures import ThreadPoolExecutor
        self.client.put('/api/admin/settings/credits', headers=self.admin, json={'API_TOKENS_PER_USER':'1'})
        def create(_):
            return self.client.post('/api/user/api-tokens', headers=self.headers, json={'name':'parallel'}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(create, range(4)))
        self.assertEqual(sorted(statuses), [200,409,409,409])
        with SessionLocal() as db:
            token = db.query(models.ApiToken).one()
            token.usage_month, token.monthly_calls = '2000-01', 99
            db.commit()
        # Management response resets an older month's display without changing the digest.
        listed = self.client.get('/api/user/api-tokens', headers=self.headers).json()
        self.assertEqual(listed['tokens'][0]['monthly_calls'], 0)
        raw = 'vsn_synthetic_monthly'
        from backend.core.api_tokens import digest
        with SessionLocal() as db:
            db.query(models.ApiToken).update({'token_hash':digest(raw)})
            db.commit()
        auth = {'Authorization':'Bearer '+raw}
        def use(_):
            return self.client.get('/api/image/balance', headers=auth).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(use, range(4))), [200]*4)
        self.assertEqual(self.client.get('/api/user/api-tokens', headers=self.headers).json()['tokens'][0]['monthly_calls'], 4)
        for path in ['/api/image/history', '/api/user/consumption', '/api/admin/users', '/api/user/api-tokens']:
            self.assertEqual(self.client.get(path, headers=auth).status_code, 401)
        self.assertEqual(self.client.post('/api/image/generate', headers=auth, json={'prompt':'bad', 'plan_id':'bad', 'plan_version':1}).status_code,403)
        self.client.put('/api/admin/settings/credits', headers=self.admin, json={'MCP_MAX_IMAGES_PER_CALL':'0'})
        self.assertEqual(self.client.post('/api/image/generate', headers=auth, json={'prompt':'disabled'}).status_code,403)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.ImageLog).count(),0)
            self.assertFalse(db.get(models.User,2).unlimited_credits)

    def test_unlimited_loopback_cost_and_failure(self):
        import json
        import os
        import threading
        from decimal import Decimal
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from test_runnable import DATA
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['content-length']))
                data = json.dumps({'data':[{'b64_json':DATA.split(',')[-1]}]}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.client.put('/api/admin/users/1/unlimited',headers=self.admin,json={'enabled':True})
        with SessionLocal() as db:
            u=db.get(models.User,1);u.points=0;u.trial_remaining=2;db.commit()
        auth = {'Authorization':'Bearer '+self.token()['token']}
        try:
            with patch.dict(os.environ,{'IMAGE_PROVIDER':'openai','OPENAI_API_KEY':'synthetic-loopback','OPENAI_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1'}):
                for fail in (False,True):
                    with patch.object(image,'store_base64',side_effect=OSError('synthetic disk failure')) if fail else patch.object(image,'store_base64',return_value='/api/creations/test.png'):
                        r=self.client.post('/api/image/generate',headers=auth,json={'prompt':'cost snapshot'})
                        self.assertEqual(r.status_code,200,r.text)
                    with SessionLocal() as db:
                        log=db.get(models.ImageLog,r.json()['id']);u=db.get(models.User,1)
                        self.assertEqual(log.status,'failed' if fail else 'success')
                        self.assertEqual(log.upstream_cost_rmb,Decimal('.45'))
                        self.assertEqual((log.cost_points,log.trial_used),(0,False))
                        self.assertEqual((u.points,u.frozen_points,u.trial_remaining,u.frozen_trials),(0,0,2,0))
                summary=self.client.get('/api/admin/users/1',headers=self.admin).json()
                self.assertEqual(float(summary['upstream_cost']),.9)
                self.assertEqual(summary['monthly_images'],1)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_unlimited_migration_is_additive_and_idempotent(self):
        import sqlalchemy as sa
        from backend.models.migrations import migrate
        old = sa.create_engine('sqlite://')
        with old.begin() as conn:
            conn.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY, points INTEGER, is_admin BOOLEAN)'))
            conn.execute(sa.text('INSERT INTO users VALUES (1, 29, 1)'))
        migrate(old);migrate(old)
        with old.connect() as conn:
            row=conn.execute(sa.text('SELECT points, is_admin, unlimited_credits FROM users')).one()
            self.assertEqual(tuple(row),(29,1,0))
            self.assertIn('api_tokens',sa.inspect(conn).get_table_names())
        old.dispose()


    def test_init_unlimited_option_and_preserve_existing(self):
        from scripts import init_db
        with patch('sys.argv', ['init_db', '--admin', 'local-owner', '--unlimited']), patch('getpass.getpass', return_value='synthetic-initial-password'):
            init_db.main()
        with SessionLocal() as db:
            u=db.query(models.User).filter_by(username='local-owner').one()
            self.assertTrue(u.unlimited_credits)
            self.assertEqual((u.points,u.trial_remaining),(10,0))
        with patch('sys.argv', ['init_db', '--admin', 'local-owner', '--if-missing']):
            init_db.main()
        with SessionLocal() as db:
            self.assertTrue(db.query(models.User).filter_by(username='local-owner').one().unlimited_credits)
        with patch('sys.argv', ['init_db', '--unlimited']), self.assertRaises(SystemExit):
            init_db.main()
