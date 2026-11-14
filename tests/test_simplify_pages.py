"""Simplified page contracts: ownership, removals, filters, accounting and audit."""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import patch
from fastapi import BackgroundTasks
import test_assistant_trial as trial
from test_runnable import models, SessionLocal, image
from backend.schemas.image import ImageCreate


class SimplifyPagesTest(unittest.TestCase):
    setUpClass = classmethod(trial.AssistantTrialTest.setUpClass.__func__)
    setUp = trial.AssistantTrialTest.setUp
    tearDown = trial.AssistantTrialTest.tearDown


    def test_status_ownership(self):
        with SessionLocal() as db:
            job = models.ImageLog(user_id=1, prompt='private prompt', ref_image_url='private reference', status='pending')
            db.add(job); db.commit(); job_id = job.id
        path = f'/api/image/status/{job_id}'
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.admin).status_code, 404)
        self.assertEqual(self.client.get('/api/image/status/99999', headers=self.admin).status_code, 404)


    def test_removed_routes_and_settings(self):
        routes = set(self.client.app.openapi()['paths'])
        for path in ['/api/auth/claim-install-reward', '/api/auth/invitation-stats', '/api/admin/invitation/logs', '/api/feedback', '/api/admin/image/{log_id}/wipe']:
            self.assertNotIn(path, routes)
        self.assertEqual(self.client.put('/api/admin/settings/credits', headers=self.admin, json={'INVITE_REWARD_POINTS':'5'}).status_code, 422)
        self.assertNotIn('invite_reward_points', self.client.get('/api/image/config').json())
        # Successful generation no longer awards a third-party bonus.
        with patch.object(image, 'store_base64', return_value='/api/creations/test.png'):
            self.assertEqual(self.client.post('/api/image/generate', headers=self.headers, json={'prompt':'no reward'}).status_code, 200)
        with SessionLocal() as db:
            self.assertEqual(db.get(models.User, 2).points, 100)


    def test_source_filters(self):
        with SessionLocal() as db:
            for user_id in (1,2):
                for source in ('normal','assistant','mcp'):
                    db.add(models.ImageLog(user_id=user_id, prompt='source '+source, status='success', source=source))
            db.commit()
        for source in ('normal','assistant','mcp'):
            rows = self.client.get('/api/image/history', headers=self.headers, params={'source':source}).json()
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['source'],source)
        self.assertEqual(len(self.client.get('/api/image/history', headers=self.headers).json()),3)
        self.assertEqual(self.client.get('/api/image/history', headers=self.headers, params={'source':'bad'}).status_code,422)
        self.assertEqual(len(self.client.get('/api/image/history', headers=self.headers, params={'keyword':'mcp'}).json()),1)
        with SessionLocal() as db:
            db.add_all([models.ImageLog(user_id=1,prompt='new normal',status='success',source='normal') for _ in range(25)])
            db.commit()
        # Filtering must search the whole history, including beyond page 1.
        rows=self.client.get('/api/image/history',headers=self.headers,params={'source':'assistant'}).json()
        self.assertEqual(len(rows),1)


    def test_costs_users_and_recharge(self):
        with SessionLocal() as db:
            db.add_all([models.ImageLog(user_id=1, prompt='known', status='success', quality='standard', source='normal', cost_points=5, upstream_cost_rmb=Decimal('.45')),
                        models.ImageLog(user_id=1, prompt='old unknown', status='success', quality='standard', source='assistant', cost_points=0, trial_used=True)])
            db.commit()
        self.assertEqual(self.client.get('/api/admin/users', headers=self.headers).status_code,403)
        stats = self.client.get('/api/admin/dashboard/stats', headers=self.admin).json()['summary']
        self.assertEqual(float(stats['upstream_cost']),.45)
        self.assertEqual(stats['unknown_cost_count'],1)
        self.assertEqual(stats['monthly_images'],2)
        detail = self.client.get('/api/admin/users/1', headers=self.admin).json()
        self.assertEqual(detail['monthly_images'],2)
        self.assertEqual(float(detail['upstream_cost']),.45)
        apply = self.client.post('/api/user/recharge/apply', headers=self.headers, json={'money_amount':10})
        self.assertEqual(apply.status_code,200,apply.text)
        log_id = apply.json()['id']
        self.assertEqual(self.client.post(f'/api/admin/recharge/audit/{log_id}', headers=self.headers, json={'approved':True}).status_code,403)
        audit = self.client.post(f'/api/admin/recharge/audit/{log_id}', headers=self.admin, json={'approved':True})
        self.assertEqual(audit.status_code,200,audit.text)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).json()['points'],160)
        self.assertEqual(self.client.post(f'/api/admin/recharge/audit/{log_id}', headers=self.admin, json={'approved':True}).status_code,404)


    def test_three_pending_and_demo_cost(self):
        async def exercise():
            with SessionLocal() as db:
                user=db.get(models.User,1);user.points=100;db.commit()
                tasks=BackgroundTasks()
                for n in range(3):
                    await image.generate_image(ImageCreate(prompt=f'parallel {n}'), tasks, db, user)
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as raised:
                    await image.generate_image(ImageCreate(prompt='fourth'), tasks, db, user)
                self.assertEqual(raised.exception.status_code,429)
            with patch.object(image,'store_base64',return_value='/api/creations/test.png'):
                await tasks()
            with SessionLocal() as db:
                self.assertEqual(db.get(models.User,1).points,85)
                self.assertTrue(all(l.upstream_cost_rmb==0 for l in db.query(models.ImageLog)))
        asyncio.run(exercise())


    def test_payment_readiness(self):
        with patch.object(__import__('backend.api.payment',fromlist=['get_config']), 'get_config',return_value=''):
            self.assertEqual(self.client.get('/api/payment/config').json(),{'online_enabled':False})
            self.assertEqual(self.client.post('/api/payment/create',headers=self.headers,json={'money_amount':10}).status_code,503)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.RechargeLog).count(),0)


    def test_deletion_preserves_accounting(self):
        with SessionLocal() as db:
            row=models.ImageLog(user_id=1,prompt='delete work',status='success',quality='standard',source='normal',cost_points=5,image_url='/api/creations/test.png',upstream_cost_rmb=Decimal('.45'))
            db.add(row);db.commit();job_id=row.id
        self.assertEqual(self.client.delete(f'/api/image/{job_id}',headers=self.admin).status_code,404)
        self.assertEqual(self.client.delete(f'/api/image/{job_id}',headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/image/history',headers=self.headers).json(),[])
        self.assertEqual(self.client.get(f'/api/image/status/{job_id}',headers=self.headers).status_code,404)
        self.assertEqual(len(self.client.get('/api/user/consumption',headers=self.headers).json()),1)
        stats=self.client.get('/api/admin/dashboard/stats',headers=self.admin).json()['summary']
        self.assertEqual(float(stats['upstream_cost']),.45)


    def test_retry_cost_snapshot_uses_decimal_and_survives_failure(self):
        import httpx
        from unittest.mock import AsyncMock
        import os
        async def exercise():
            with SessionLocal() as db:
                user=db.get(models.User,1)
                tasks=BackgroundTasks()
                await image.generate_image(ImageCreate(prompt='retry costs'),tasks,db,user)
            with patch.dict(os.environ,{'IMAGE_PROVIDER':'openai','OPENAI_API_KEY':'loopback-only','OPENAI_BASE_URL':'http://127.0.0.1:9/v1'}), patch.object(httpx.AsyncClient,'post',new=AsyncMock(side_effect=httpx.ConnectTimeout('synthetic timeout'))), patch.object(image.asyncio,'sleep',new=AsyncMock()):
                await tasks()
            with SessionLocal() as db:
                log=db.query(models.ImageLog).one()
                self.assertEqual(log.status,'failed')
                self.assertEqual(log.upstream_cost_rmb,Decimal('1.35'))
                self.assertEqual(db.get(models.User,1).points,10)
                self.assertEqual(db.get(models.User,1).frozen_points,0)
        asyncio.run(exercise())
