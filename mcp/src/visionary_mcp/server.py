"""stdio entry point; all diagnostics stay on stderr through FastMCP."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from visionary_mcp.client import Visionary

mcp = FastMCP('visionary-mcp', instructions='Generate directly when trials or credits suffice; no confirmation required. Insufficient balance never generates. A pending task_id must be polled, not resubmitted.', log_level='WARNING')


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
async def generate_image(prompt: str, aspect_ratio: str = '1:1', style: str = 'default', tier: str = 'standard', reference_image: str | None = None, save_path: str | None = None, wait_seconds: float = 180) -> dict:
    """Generate one image immediately using the account's trial/credits. Optional reference_image: URL, data URL or local image path. Optional save_path never overwrites. Wait at most 300 seconds; pending returns task_id. Do not retry automatically after submission errors."""
    return await Visionary().generate(prompt, aspect_ratio, style, tier, reference_image, save_path, wait_seconds)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_task(task_id: int) -> dict:
    """Read your own generation task; image_url is absolute when ready."""
    return await Visionary().task(task_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_balance() -> dict:
    """Read available credits, remaining trials, unlimited flag and recharge link."""
    return await Visionary().balance()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def list_styles() -> dict:
    """List styles, tier prices, trial tiers and MCP cap from live server settings."""
    return await Visionary().styles()


def main():
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
