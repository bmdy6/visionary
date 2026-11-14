"""HTTP boundary; generation POST is never retried automatically."""
import asyncio
import base64
import mimetypes
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx


class Visionary:
    def __init__(self, url=None, token=None, transport=None):
        self.url = (url or os.environ.get('VISIONARY_URL', '')).rstrip('/')
        self.token = token or os.environ.get('VISIONARY_TOKEN', '')
        parsed = urlsplit(self.url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('VISIONARY_URL must be an http(s) origin, without credentials, query or fragment')
        if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Use HTTPS except for loopback development')
        if not self.token.startswith('vsn_'):
            raise ValueError('Set VISIONARY_TOKEN to a personal vsn_ token')
        self.transport = transport

    def absolute(self, url):
        return urljoin(self.url + '/', url)

    async def request(self, method, path, **kwargs):
        async with httpx.AsyncClient(transport=self.transport, timeout=30, follow_redirects=False, trust_env=False) as client:
            response = await client.request(method, self.url + '/api' + path,
                                            headers={'Authorization': 'Bearer ' + self.token}, **kwargs)
        try:
            data = response.json()
        except ValueError:
            raise ValueError(f'Visionary returned HTTP {response.status_code}, without JSON') from None
        if response.is_error:
            detail = data.get('detail')
            if isinstance(detail, dict) and detail.get('code') == 'insufficient_credits':
                return {'status': 'insufficient_credits', **detail, 'recharge_url': self.absolute(detail['recharge_url'])}
            raise ValueError(f'Visionary HTTP {response.status_code}: request rejected; check token, permissions and server settings')
        return data

    async def balance(self):
        result = await self.request('GET', '/image/balance')
        result['recharge_url'] = self.absolute(result['recharge_url'])
        return result

    async def styles(self):
        return await self.request('GET', '/image/styles')

    async def task(self, task_id):
        if task_id < 1:
            raise ValueError('task_id must be positive')
        result = await self.request('GET', f'/image/status/{task_id}')
        if result.get('image_url'):
            result['image_url'] = self.absolute(result['image_url'])
        # The server's raw provider error may contain credentials or request data.
        if result.get('error'):
            result['error'] = 'Generation failed; inspect server logs or retry as a new task.'
        return result

    async def save(self, result, save_path):
        if result.get('status') != 'success' or not save_path:
            return result
        path = Path(save_path).expanduser()
        try:
            # Never forward the personal token to storage hosts or redirects.
            async with httpx.AsyncClient(transport=self.transport, timeout=30, follow_redirects=True, trust_env=False) as client:
                response = await client.get(result['image_url'])
                response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(response.content)
            result['saved_path'] = str(path.resolve())
        except (OSError, httpx.HTTPError):
            result['save_error'] = 'Image generated; local save failed (check path, existing file or download access). Use image_url; do not regenerate.'
        return result

    async def generate(self, prompt, aspect_ratio='1:1', style='default', tier='standard', reference_image=None, save_path=None, wait_seconds=180):
        if not prompt.strip() or len(prompt) > 1000 or aspect_ratio not in ('1:1', '9:16', '16:9') or tier not in ('standard', 'hd', 'master'):
            raise ValueError('Check prompt (1–1000 characters), aspect_ratio and tier')
        if not 0 <= wait_seconds <= 300:
            raise ValueError('wait_seconds must be between 0 and 300')
        if save_path and Path(save_path).expanduser().exists():
            raise ValueError('save_path already exists; choose a new path before generating')
        reference = reference_image
        if reference and not reference.startswith(('https://', 'http://', 'data:image/')):
            path = Path(reference).expanduser()
            if path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError('Reference image exceeds 20 MiB')
            media = mimetypes.guess_type(path.name)[0]
            if media not in ('image/png', 'image/jpeg', 'image/webp'):
                raise ValueError('Reference must be PNG, JPEG or WebP')
            reference = f'data:{media};base64,' + base64.b64encode(path.read_bytes()).decode()
        settings = await self.styles()
        if settings['mcp_max_images_per_call'] < 1:
            raise ValueError('MCP generation is disabled by the administrator')
        if style not in settings['styles']:
            raise ValueError('Unknown style; use list_styles')
        result = await self.request('POST', '/image/generate', json={
            'prompt': prompt, 'quality': tier, 'style': style,
            'aspect_ratio': aspect_ratio, 'ref_image_url': reference})
        if result.get('status') == 'insufficient_credits':
            return result
        task_id = result['id']
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            try:
                result = await asyncio.wait_for(self.task(task_id), timeout=max(.001, deadline - time.monotonic()))
            except (asyncio.TimeoutError, httpx.HTTPError, ValueError):
                # Submission already succeeded; always preserve its ID for recovery.
                return {'status': 'pending', 'task_id': task_id, 'message': 'Polling interrupted; call get_task. Do not resubmit.'}
            if result['status'] in ('success', 'failed'):
                return await self.save({'task_id': task_id, **result}, save_path)
            await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))
        return {'status': 'pending', 'task_id': task_id, 'message': 'Wait timed out; call get_task. Do not resubmit.'}
