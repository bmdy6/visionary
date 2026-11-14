import { useEffect, useState } from "react";
import request from "../api/request";
import { errorText } from "../utils/creation";

const date = (value) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "从未";
export default function ApiMcp() {
  const [data, setData] = useState(null);
  const [name, setName] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [copied, setCopied] = useState(false);
  const load = () => request.get("/user/api-tokens").then(setData);
  useEffect(() => {
    let active = true;
    request
      .get("/user/api-tokens")
      .then((value) => {
        if (active) setData(value);
      })
      .catch(() => {
        if (active) setStatus("Token 读取失败，请重试");
      });
    return () => {
      active = false;
    };
  }, []);
  async function create(e) {
    e.preventDefault();
    setBusy(true);
    setStatus("");
    setCopied(false);
    try {
      const result = await request.post("/user/api-tokens", { name });
      setSecret(result.token);
      setName("");
      await load();
    } catch (error) {
      setStatus(errorText(error, "创建失败，请刷新列表后重试"));
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id) {
    setBusy(true);
    setStatus("");
    try {
      await request.delete(`/user/api-tokens/${id}`);
      setSecret("");
      await load();
      setStatus("Token 已撤销，立即失效");
    } catch (error) {
      setStatus(errorText(error, "撤销失败，请重试"));
    } finally {
      setBusy(false);
    }
  }
  const snippet = `{
  "mcpServers": {
    "visionary": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/bmdy6/visionary@main#subdirectory=mcp", "visionary-mcp"],
      "env": { "VISIONARY_URL": ${JSON.stringify(window.location.origin)}, "VISIONARY_TOKEN": "vsn_替换为你的Token" }
    }
  }
}`;
  return (
    <div className="api-mcp-page">
      <h1>API 与 MCP</h1>
      <p className="muted">
        让 Claude、Codex 等 Agent
        直接用你的账号生图。积分够就直接生成，不用确认；扣费规则和网页一样。
      </p>
      <section className="panel api-token-panel">
        <h2>API Token</h2>
        {!data && (
          <p role="status">
            {status || "正在读取 Token…"}{" "}
            <button
              onClick={() => load().catch(() => setStatus("读取失败，请重试"))}
            >
              重试读取
            </button>
          </p>
        )}
        {data && (
          <>
            <form className="api-token-create" onSubmit={create}>
              <label htmlFor="token-name" className="sr-only">
                Token 名称
              </label>
              <input
                id="token-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="名称，如 Claude Code"
                required
                maxLength={80}
                disabled={busy || !data.enabled || !!secret}
              />
              <button
                className="btn-primary"
                disabled={
                  busy ||
                  !data.enabled ||
                  !!secret ||
                  data.tokens.length >= data.limit
                }
              >
                {busy ? "处理中…" : "+ 新建 Token"}
              </button>
            </form>
            <p className="muted">
              {data.enabled
                ? `有效 Token ${data.tokens.length} / ${data.limit}`
                : "管理员已关闭 API 与 MCP；仍可撤销已有 Token。"}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {[
                      "名称",
                      "Token",
                      "创建时间",
                      "最近使用",
                      "本月调用",
                      "操作",
                    ].map((t) => (
                      <th key={t}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.tokens.map((t) => (
                    <tr key={t.id}>
                      <td>{t.name}</td>
                      <td>
                        <code>
                          {t.prefix}••••{t.suffix}
                        </code>
                      </td>
                      <td>{date(t.created_at)}</td>
                      <td>{date(t.last_used_at)}</td>
                      <td>{t.monthly_calls} 次</td>
                      <td>
                        <button disabled={busy} onClick={() => revoke(t.id)}>
                          撤销
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data.tokens.length && (
              <p className="empty-note">暂无 Token，新建一个连接你的 Agent。</p>
            )}
          </>
        )}
        {secret && (
          <div className="token-once" role="status">
            <strong>请立即复制保存，关闭后无法再次查看。</strong>
            <code aria-label="新建 Token 明文">{secret}</code>
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(secret);
                  setCopied(true);
                } catch {
                  setStatus("复制失败，请手动选择 Token 复制");
                }
              }}
            >
              {copied ? "已复制" : "复制 Token"}
            </button>
            <button onClick={() => setSecret("")}>已保存，关闭明文</button>
          </div>
        )}
        <p className="token-notice">
          新建后 Token 只完整显示一次，请复制保存。数据库里只存哈希。持有 Token
          可使用你的积分，请妥善保管。
        </p>
        <p className="muted">
          本月调用按 UTC+8 统计，包含余额、风格、生成及任务轮询请求。
        </p>
        {status && data && <p role="status">{status}</p>}
      </section>
      <section className="panel mcp-connect">
        <h2>接入 MCP</h2>
        <p className="muted">
          安装 uv 后，把下面的配置加到 Agent 里，替换成你的
          Token。服务地址使用你的 Visionary 部署域名。
        </p>
        <pre tabIndex={0} aria-label="MCP 配置示例">
          {snippet}
        </pre>
        <div className="mcp-tools">
          {[
            ["generate_image", "文生图 / 参考图生图"],
            ["get_balance", "查余额和试用次数"],
            ["list_styles", "风格和档位价格"],
            ["get_task", "查生成状态"],
          ].map(([tool, description]) => (
            <div key={tool}>
              <strong>{tool}</strong>
              <small>{description}</small>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
