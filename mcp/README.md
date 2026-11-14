# visionary-mcp

A standalone Python MCP server that calls Visionary over HTTP. No direct image-provider calls.

Requires Python 3.10+ and uv. Create a personal Token in Visionary's profile, then set `VISIONARY_URL` and `VISIONARY_TOKEN` in your MCP client's private environment configuration.

```bash
uvx --from 'git+https://github.com/bmdy6/visionary@main#subdirectory=mcp' visionary-mcp
```

Use after this feature reaches main. To test a local checkout from the repository root:

```bash
uvx --from ./mcp visionary-mcp
uv pip install -e ./mcp
python -m unittest discover -s mcp/tests -v
```

Tools: `generate_image`, `get_task`, `get_balance`, `list_styles`. Sufficient credits/trials generate immediately; insufficient balance returns the balance, required price and recharge link. Optional `save_path` saves without overwriting. Waiting timeout returns `task_id`; poll it rather than resubmitting. Read the [root guide](../README.md#在-agent-里使用) for configuration, permissions, unlimited accounts and failure handling. Keep credentials out of public configuration files.
