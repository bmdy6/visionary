"""Provider selection and bundled offline demonstration images."""
import base64
from itertools import count
from pathlib import Path

from backend.core.config import get_config

SHOWCASE_DIR = Path(__file__).resolve().parents[2] / "showcase"
_demo_sequence = count()


def get_image_provider():
    mode = get_config("IMAGE_PROVIDER", "auto").strip().lower()
    if mode not in {"auto", "demo", "openai"}:
        raise ValueError("IMAGE_PROVIDER must be auto, demo or openai")
    has_key = bool((get_config("OPENAI_API_KEY") or "").strip())
    if mode == "openai" and not has_key:
        raise ValueError("IMAGE_PROVIDER=openai requires OPENAI_API_KEY")
    return ("openai" if has_key else "demo") if mode == "auto" else mode


def demo_image():
    """Rotate bundled PNGs; demonstrates the workflow, not prompt rendering."""
    images = sorted(SHOWCASE_DIR.glob("*.png"))
    if not images:
        raise RuntimeError("showcase/ 中缺少演示 PNG 图片")
    image = images[next(_demo_sequence) % len(images)]
    return "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
