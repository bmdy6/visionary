"""HTTP boundaries, timeout recovery and local-save side effects."""
import asyncio
import tempfile
import unittest
from pathlib import Path
import httpx
from visionary_mcp.client import Visionary


class ClientTest(unittest.TestCase):
    def client(self, handler):
        return Visionary('http://127.0.0.1:9999', 'vsn_synthetic', httpx.MockTransport(handler))

    def test_insufficient_never_retries(self):
        posts = []
        def handler(r):
            if r.method == 'GET':
                return httpx.Response(200, json={'styles':['default'], 'mcp_max_images_per_call':1})
            posts.append(r)
            return httpx.Response(403, json={'detail':{'code':'insufficient_credits', 'balance':0, 'trial_remaining':0, 'required':7, 'recharge_url':'/profile'}})
        result = asyncio.run(self.client(handler).generate('test'))
        self.assertEqual(result['required'], 7)
        self.assertEqual(result['recharge_url'], 'http://127.0.0.1:9999/profile')
        self.assertEqual(len(posts), 1)

    def test_timeout_and_poll_error_keep_task_id(self):
        for wait, failure in [(0, False), (.01, False), (1, True)]:
            def handler(r):
                if r.url.path.endswith('/styles'):
                    return httpx.Response(200, json={'styles':['default'], 'mcp_max_images_per_call':1})
                if r.method == 'POST':
                    return httpx.Response(200, json={'id':42})
                return httpx.Response(503 if failure else 200, json={'status':'generating'})
            result = asyncio.run(self.client(handler).generate('test', wait_seconds=wait))
            self.assertEqual(result['task_id'], 42)
            self.assertEqual(result['status'], 'pending')

    def test_download_no_credentials_no_overwrite(self):
        downloads = []
        def handler(r):
            if r.url.host == 'storage.example':
                downloads.append(r)
                self.assertNotIn('authorization', r.headers)
                return httpx.Response(200, content=b'image-data')
            if r.url.path.endswith('/styles'):
                return httpx.Response(200, json={'styles':['default'], 'mcp_max_images_per_call':1})
            if r.method == 'POST':
                return httpx.Response(200, json={'id':42})
            return httpx.Response(200, json={'status':'success', 'image_url':'https://storage.example/img.png'})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'image.png'
            client = self.client(handler)
            result = asyncio.run(client.generate('test', save_path=str(path.resolve())))
            self.assertEqual(result['saved_path'], str(path.resolve()))
            self.assertEqual(path.read_bytes(), b'image-data')
            with self.assertRaises(ValueError):
                asyncio.run(client.generate('test', save_path=str(path.resolve())))
            self.assertEqual(len(downloads), 1)

    def test_save_failure_does_not_lose_success(self):
        def handler(r):
            return httpx.Response(503)
        with tempfile.TemporaryDirectory() as d:
            result = asyncio.run(self.client(handler).save({'status':'success', 'task_id':4, 'image_url':'https://storage.example/x'}, str(Path(d)/'x.png')))
            self.assertEqual(result['status'], 'success')
            self.assertIn('save_error', result)

    def test_disabled_cap_invalid_style_and_remote_http(self):
        def handler(r):
            self.assertEqual(r.method, 'GET')
            return httpx.Response(200, json={'styles':['default'], 'mcp_max_images_per_call':0})
        with self.assertRaises(ValueError):
            asyncio.run(self.client(handler).generate('test'))
        with self.assertRaises(ValueError):
            Visionary('http://example.com', 'vsn_synthetic')
