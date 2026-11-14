"""COS when configured, otherwise same-origin local creation files."""
import base64
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

from backend.core.config import get_config
from backend.core.cos import upload_base64_to_cos, upload_url_to_cos

COS_KEYS = ("TENCENT_CLOUD_SECRET_ID", "TENCENT_CLOUD_SECRET_KEY",
            "TENCENT_CLOUD_COS_REGION", "TENCENT_CLOUD_COS_BUCKET")
LOCAL_STORAGE_DIR = Path(__file__).resolve().parents[1] / "data" / "creations"
LOCAL_URL_PREFIX = "/api/creations/"


def get_storage_backend():
    mode = get_config("STORAGE_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "local", "cos"}:
        raise ValueError("STORAGE_BACKEND must be auto, local or cos")
    configured = all((get_config(key) or "").strip() for key in COS_KEYS)
    if mode == "cos" and not configured:
        raise ValueError("COS 配置不完整")
    return ("cos" if configured else "local") if mode == "auto" else mode


def local_path(filename):
    # One filename only: never allow URLs to escape the creations directory.
    name = unquote(filename)
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("Invalid local image filename")
    root = LOCAL_STORAGE_DIR.resolve()
    target = (root / name).resolve()
    if target.parent != root:
        raise ValueError("Invalid local image path")
    return target


def store_base64(data, filename):
    if get_storage_backend() == "cos":
        return upload_base64_to_cos(data, filename)
    target = local_path(filename)
    body = base64.b64decode(data.split(",", 1)[-1], validate=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return LOCAL_URL_PREFIX + quote(filename)


def store_url(url, filename):
    if get_storage_backend() == "cos":
        return upload_url_to_cos(url, filename)
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
    return store_base64(base64.b64encode(response.content).decode(), filename)


def image_data_url(body):
    # Uploaded reference files can be JPEG/WebP even when the legacy name ends in .png.
    media_type = "image/png"
    if body.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif body[:6] in (b"GIF87a", b"GIF89a"):
        media_type = "image/gif"
    elif body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        media_type = "image/webp"
    return f"data:{media_type};base64," + base64.b64encode(body).decode()


def provider_reference(url):
    """A remote provider cannot fetch a relative URL on this computer."""
    if url and url.startswith(LOCAL_URL_PREFIX):
        body = local_path(url[len(LOCAL_URL_PREFIX):]).read_bytes()
        return image_data_url(body)
    return url
