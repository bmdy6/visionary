import { useEffect, useState } from "react";
import request from "../api/request";
import CreditSettings from "./CreditSettings";
import { creditsChanged } from "../hooks/useBilling";
import { errorText, TIERS, SOURCES } from "../utils/creation";

export default function AdminPage() {
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [pending, setPending] = useState([]);
  const [detail, setDetail] = useState(null);
  const [amount, setAmount] = useState(10);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  async function load() {
    try {
      const [s, p, u] = await Promise.all([
        request.get("/admin/dashboard/stats"),
        request.get("/admin/recharge/pending"),
        request.get("/admin/users"),
      ]);
      setStats(s);
      setPending(p);
      setUsers(u);
    } catch (e) {
      setError(errorText(e, "后台读取失败"));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    Promise.all([
      request.get("/admin/dashboard/stats"),
      request.get("/admin/recharge/pending"),
      request.get("/admin/users"),
    ])
      .then(([s, p, u]) => {
        setStats(s);
        setPending(p);
        setUsers(u);
      })
      .catch((e) => setError(errorText(e, "后台读取失败")))
      .finally(() => setLoading(false));
  }, []);
  async function audit(id, approved) {
    setBusy(true);
    setError("");
    try {
      await request.post(`/admin/recharge/audit/${id}`, { approved });
      await load();
      creditsChanged();
    } catch (e) {
      setError(errorText(e, "审核失败"));
    } finally {
      setBusy(false);
    }
  }
  async function addPoints(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request.post("/admin/recharge", null, {
        params: { target_username: detail.username, amount },
      });
      setDetail(await request.get(`/admin/users/${detail.id}`));
      await load();
      creditsChanged();
    } catch (e) {
      setError(errorText(e, "加积分失败"));
    } finally {
      setBusy(false);
    }
  }
  const s = stats?.summary;
  return (
    <section className="admin-page">
      <h1 className="sr-only">管理后台</h1>
      <nav className="segmented admin-tabs" aria-label="后台导航">
        {Object.entries({
          overview: "概览",
          recharge: "充值审核",
          users: "用户",
          settings: "系统设置",
        }).map(([k, v]) => (
          <button key={k} aria-pressed={tab === k} onClick={() => setTab(k)}>
            {v}
            {k === "recharge" && pending.length > 0 && (
              <small>{pending.length}</small>
            )}
          </button>
        ))}
      </nav>
      {error && (
        <p role="alert" className="error-message">
          {error}
          <button onClick={load}>重试</button>
        </p>
      )}
      {loading && <p role="status">正在读取后台…</p>}
      {tab === "overview" && s && (
        <>
          <div className="stats-grid">
            {[
              ["用户", s.total_users, `本月新增 ${s.new_users}`],
              [
                "本月生成",
                s.monthly_images,
                `网页 ${s.sources.normal} · 助手 ${s.sources.assistant} · MCP ${s.sources.mcp}`,
              ],
              [
                "本月充值",
                `¥ ${s.monthly_revenue}`,
                `待审核 ${s.pending_recharges} 笔`,
              ],
              [
                "本月上游成本",
                `¥ ${Number(s.upstream_cost).toFixed(2)}`,
                `费率估算累计 · ${s.unknown_cost_count} 条未知`,
              ],
            ].map(([label, value, note]) => (
              <article className="panel stat-card" key={label}>
                <h2>{label}</h2>
                <strong>{value}</strong>
                <small>{note}</small>
              </article>
            ))}
          </div>
          <section className="panel recent-table">
            <header>
              <h2>最近生成</h2>
              <button onClick={() => setExpanded((v) => !v)}>
                {expanded ? "收起" : "查看全部"}
              </button>
            </header>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {[
                      "时间",
                      "用户",
                      "提示词",
                      "来源",
                      "清晰度",
                      "状态",
                      "积分",
                    ].map((t) => (
                      <th key={t}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_logs.slice(0, expanded ? 50 : 10).map((j) => (
                    <tr key={j.id}>
                      <td>{j.created_at.slice(5, 16).replace("T", " ")}</td>
                      <td>{j.username}</td>
                      <td>{j.prompt}</td>
                      <td>{SOURCES[j.source] || j.source}</td>
                      <td>{TIERS[j.quality]}</td>
                      <td>
                        {j.status === "success"
                          ? "成功"
                          : j.status === "failed"
                            ? "失败 · 已释放冻结"
                            : "生成中"}
                      </td>
                      <td>
                        {j.trial_used
                          ? "试用"
                          : j.status === "success"
                            ? j.cost_points
                            : 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!stats.recent_logs.length && (
              <p className="empty-note">暂无生成记录</p>
            )}
          </section>
        </>
      )}
      {tab === "recharge" && (
        <section className="panel recent-table">
          <h2>充值审核</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "时间",
                    "用户 UID / ID",
                    "金额",
                    "积分",
                    "凭证",
                    "操作",
                  ].map((t) => (
                    <th key={t}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pending.map((r) => (
                  <tr key={r.id}>
                    <td>{r.created_at.slice(5, 16).replace("T", " ")}</td>
                    <td>
                      {users.find((u) => u.id === r.user_id)?.uid || r.user_id}
                    </td>
                    <td>¥{r.money_amount}</td>
                    <td>{r.amount}</td>
                    <td>
                      {r.screenshot_url ? (
                        <a
                          href={r.screenshot_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          查看凭证
                        </a>
                      ) : (
                        "人工报备"
                      )}
                    </td>
                    <td>
                      <button disabled={busy} onClick={() => audit(r.id, true)}>
                        通过
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => audit(r.id, false)}
                      >
                        拒绝
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!pending.length && <p className="empty-note">暂无待审核充值</p>}
        </section>
      )}
      {tab === "users" && (
        <section className="panel recent-table">
          <h2>用户</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "用户",
                    "注册",
                    "积分",
                    "试用剩余",
                    "无限积分",
                    "本月生成",
                    "上游成本",
                    "操作",
                  ].map((t) => (
                    <th key={t}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>{u.created_at.slice(5, 10)}</td>
                    <td>{u.unlimited_credits ? "—" : u.points}</td>
                    <td>{u.unlimited_credits ? "—" : u.trial_remaining}</td>
                    <td>
                      <input
                        className="credits-toggle"
                        type="checkbox"
                        role="switch"
                        aria-label={`${u.username} 无限积分`}
                        checked={u.unlimited_credits}
                        disabled={busy}
                        onChange={async (e) => {
                          const enabled = e.target.checked;
                          setBusy(true);
                          setError("");
                          try {
                            const updated = await request.put(
                              `/admin/users/${u.id}/unlimited`,
                              { enabled },
                            );
                            setUsers((prev) =>
                              prev.map((row) =>
                                row.id === u.id ? updated : row,
                              ),
                            );
                            creditsChanged();
                          } catch (error) {
                            setError(errorText(error, "修改失败，请重试"));
                          } finally {
                            setBusy(false);
                          }
                        }}
                      />
                    </td>
                    <td>{u.monthly_images}</td>
                    <td>
                      ¥{Number(u.upstream_cost).toFixed(2)}
                      {u.unknown_cost_count > 0 && " + 未知"}
                    </td>
                    <td>
                      <button
                        onClick={async () => {
                          try {
                            setDetail(
                              await request.get(`/admin/users/${u.id}`),
                            );
                          } catch (e) {
                            setError(errorText(e, "读取用户失败"));
                          }
                        }}
                      >
                        详情
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {users.length >= 50 && (
            <button
              className="load-more"
              onClick={async () => {
                try {
                  const next = await request.get("/admin/users", {
                    params: { skip: users.length },
                  });
                  setUsers((prev) => [...prev, ...next]);
                } catch (e) {
                  setError(errorText(e, "读取用户失败"));
                }
              }}
            >
              加载更多用户
            </button>
          )}
        </section>
      )}
      {tab === "settings" && <CreditSettings />}
      {detail && (
        <div className="dialog-backdrop">
          <section
            className="panel user-detail"
            role="dialog"
            aria-modal="true"
            aria-label="用户详情"
          >
            <button
              className="dialog-close"
              autoFocus
              aria-label="关闭用户详情"
              onClick={() => setDetail(null)}
            >
              ×
            </button>
            <h2>{detail.username}</h2>
            <p>
              UID {detail.uid} · 积分 {detail.points} · 冻结{" "}
              {detail.frozen_points}
            </p>
            <p>
              试用剩余 {detail.trial_remaining} · 本月生成{" "}
              {detail.monthly_images}
            </p>
            <form onSubmit={addPoints}>
              <label>
                手动加积分
                <input
                  aria-label="手动加积分"
                  type="number"
                  required
                  min="1"
                  max="1000000"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </label>
              <button className="btn-primary" disabled={busy}>
                确认加积分
              </button>
            </form>
            {error && <p role="alert">{error}</p>}
          </section>
        </div>
      )}
    </section>
  );
}
