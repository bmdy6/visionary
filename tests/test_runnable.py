"""Isolated offline regression: python -m unittest discover -s tests -v."""
import asyncio
import base64
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
import unittest
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="visionary-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(TEMP.name) / "test.db")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)

from api.index import app
from backend.api import image
from backend.core import config, storage, image_provider
from backend.models import models
from backend.models.database import Base, engine, SessionLocal
from backend.schemas.image import ImageCreate
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

SAMPLE = Path(__file__).resolve().parents[1] / "showcase/travel_journal.png"
PNG = SAMPLE.read_bytes()
DATA = "data:image/png;base64," + base64.b64encode(PNG).decode()
COS = dict(zip(storage.COS_KEYS, ["dummy-id", "dummy-secret", "dummy-region", "dummy-bucket"]))


class RunnableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)

    def setUp(self):
        self.env = patch.dict(os.environ, {"IMAGE_PROVIDER": "auto", "OPENAI_API_KEY": "", "STORAGE_BACKEND": "auto", **{k: "" for k in storage.COS_KEYS}})
        self.env.start()
        config._config_cache = {}
        config._last_fetch = time.time()
        self.local = tempfile.TemporaryDirectory(dir=TEMP.name)
        self.path_patch = patch.object(storage, "LOCAL_STORAGE_DIR", Path(self.local.name))
        self.path_patch.start()
        with SessionLocal() as db:
            db.query(models.ImageLog).delete()
            db.query(models.User).delete()
            u = models.User(username="offline", uid=12345678, password_hash="unused", points=100)
            db.add(u)
            db.commit()
            self.uid = u.id

    def tearDown(self):
        self.path_patch.stop()
        self.local.cleanup()
        self.env.stop()

    def test_selection_matrix(self):
        self.assertEqual(storage.get_storage_backend(), "local")
        self.assertEqual(image_provider.get_image_provider(), "demo")
        with patch.dict(os.environ, COS):
            self.assertEqual(storage.get_storage_backend(), "cos")
            os.environ["STORAGE_BACKEND"] = "local"
            self.assertEqual(storage.get_storage_backend(), "local")
        with patch.dict(os.environ, {storage.COS_KEYS[0]: "partial"}):
            self.assertEqual(storage.get_storage_backend(), "local")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-dummy"}):
            self.assertEqual(image_provider.get_image_provider(), "openai")
            os.environ["IMAGE_PROVIDER"] = "demo"
            self.assertEqual(image_provider.get_image_provider(), "demo")
        for key, value, fn in [("STORAGE_BACKEND", "cos", storage.get_storage_backend), ("STORAGE_BACKEND", "typo", storage.get_storage_backend), ("IMAGE_PROVIDER", "openai", image_provider.get_image_provider), ("IMAGE_PROVIDER", "typo", image_provider.get_image_provider)]:
            with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    fn()

    def test_database_config_keeps_precedence(self):
        with SessionLocal() as db:
            db.add(models.SystemConfig(config_key="IMAGE_PROVIDER", config_value="demo"))
            db.commit()
        try:
            config._last_fetch = 0
            with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-dummy", "IMAGE_PROVIDER": "openai"}):
                self.assertEqual(image_provider.get_image_provider(), "demo")
        finally:
            with SessionLocal() as db:
                db.query(models.SystemConfig).delete()
                db.commit()
            config._config_cache = {}
            config._last_fetch = 0

    def test_local_reference_preserves_jpeg_media_type(self):
        jpeg = b"\xff\xd8\xff" + b"offline fixture"
        url = storage.store_base64(base64.b64encode(jpeg).decode(), "reference.png")
        self.assertEqual(storage.provider_reference(url), "data:image/jpeg;base64," + base64.b64encode(jpeg).decode())

    def test_cos_delegation_unchanged(self):
        with patch.dict(os.environ, COS), patch.object(storage, "upload_base64_to_cos", return_value="https://cos.invalid/a") as b64, patch.object(storage, "upload_url_to_cos", return_value="https://cos.invalid/b") as url:
            self.assertEqual(storage.store_base64(DATA, "a.png"), "https://cos.invalid/a")
            self.assertEqual(storage.store_url("https://source.invalid/a", "b.png"), "https://cos.invalid/b")
            b64.assert_called_once_with(DATA, "a.png")
            url.assert_called_once_with("https://source.invalid/a", "b.png")

    def test_local_static_proxy_download_and_reference(self):
        url = storage.store_base64(DATA, "中文.png")
        with TestClient(app) as client:
            self.assertEqual(client.get(url).content, PNG)
            self.assertEqual(client.get("/api/image/proxy", params={"url": url}).content, PNG)
            self.assertEqual(client.get("/api/creations/missing.png").status_code, 404)
            self.assertEqual(client.get("/api/image/proxy", params={"url": "/api/creations/../outside"}).status_code, 400)
            info = client.get("/api/image/config").json()
            self.assertTrue(info["demo_mode"])
        self.assertEqual(storage.provider_reference(url), DATA)
        for name in ["../outside.png", "/outside.png"]:
            with self.assertRaises(ValueError):
                storage.store_base64(DATA, name)
        with self.assertRaises(ValueError):
            storage.provider_reference("/api/creations/%2e%2e%2foutside")

    async def generate(self, reference=None):
        with SessionLocal() as db:
            user = db.get(models.User, self.uid)
            before = user.points
            tasks = BackgroundTasks()
            result = await image.generate_image(ImageCreate(prompt="offline", ref_image_url=reference), tasks, db, user)
            db.expire_all()
            self.assertEqual(db.get(models.User, self.uid).points, before)
            self.assertEqual(db.get(models.User, self.uid).frozen_points, 5)
        await tasks()
        return result["id"], before

    def check_success(self, log_id, before):
        with SessionLocal() as db:
            user, log = db.get(models.User, self.uid), db.get(models.ImageLog, log_id)
            self.assertEqual(log.status, "success", log.error_msg)
            self.assertEqual(user.points, before - 5)
            self.assertEqual(user.frozen_points, 0)
            url = log.image_url
        with TestClient(app) as client:
            self.assertEqual(client.get(url).content, PNG)
            self.assertEqual(client.get("/api/image/download", params={"id": log_id}).content, PNG)
        return url

    def test_demo_text_and_reference_without_network(self):
        with patch("socket.socket.connect", side_effect=AssertionError("demo must not connect")):
            for ref in [None, DATA]:
                log_id, before = asyncio.run(self.generate(ref))
                self.check_success(log_id, before)
        self.assertEqual(base64.b64decode(image_provider.demo_image().split(",")[-1]), PNG)

    def test_invalid_explicit_config_fails_without_network_or_debit(self):
        for settings in [{"IMAGE_PROVIDER": "openai"}, {"STORAGE_BACKEND": "cos", "OPENAI_API_KEY": "offline-dummy"}]:
            with self.subTest(settings=settings), patch.dict(os.environ, settings), patch("socket.socket.connect", side_effect=AssertionError("invalid config must not connect")):
                log_id, before = asyncio.run(self.generate())
                with SessionLocal() as db:
                    self.assertEqual(db.get(models.ImageLog, log_id).status, "failed")
                    self.assertEqual(db.get(models.User, self.uid).points, before)
                    self.assertEqual(db.get(models.User, self.uid).frozen_points, 0)

    def test_failure_releases_reservation(self):
        with patch.object(image, "store_base64", side_effect=OSError("synthetic disk failure")):
            log_id, before = asyncio.run(self.generate())
        with SessionLocal() as db:
            self.assertEqual(db.get(models.ImageLog, log_id).status, "failed")
            self.assertEqual(db.get(models.User, self.uid).points, before)
            self.assertEqual(db.get(models.User, self.uid).frozen_points, 0)

    def test_key_without_cos_loopback_provider(self):
        requests = []
        result_format = ["b64"]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["content-length"])))
                requests.append((self.path, payload, self.headers["Authorization"]))
                result = {"b64_json": DATA.split(",")[-1]} if result_format[0] == "b64" else {"url": f"http://127.0.0.1:{self.server.server_port}/result.png"}
                data = json.dumps({"data": [result]}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(PNG)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-dummy", "OPENAI_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1"}):
                for ref in [None, DATA, storage.store_base64(DATA, "reused.png")]:
                    log_id, before = asyncio.run(self.generate(ref))
                    self.check_success(log_id, before)
                    if ref: self.assertEqual(requests[-1][1]["images"][0]["image_url"], DATA)
                    result_format[0] = "url"
            self.assertEqual([r[0] for r in requests], ["/v1/images/generations", "/v1/images/edits", "/v1/images/edits"])
            self.assertTrue(all(r[2] == "Bearer offline-dummy" for r in requests))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
