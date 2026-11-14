import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import request, { logout } from "../api/request";
import useBilling, { creditsChanged } from "../hooks/useBilling";
import ApiMcp from "./ApiMcp";
import RechargeModal from "../components/RechargeModal";
import { errorText, TIERS, SOURCES } from "../utils/creation";

function Ledger() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState(20);
  useEffect(() => {
    let stopped = false;
    Promise.all([
      request.get("/user/consumption"),
      request.get("/user/recharge/history"),
    ])
      .then(([images, recharges]) => {
        if (stopped) return;
        setRows(
          [
            ...images
              .filter((j) => ["success", "failed"].includes(j.status))
              .map((j) => ({
                key: `i${j.id}`,
                date: j.created_at,
                type:
                  j.status === "failed"
                    ? "失败"
                    : j.trial_used
                      ? "试用"
                      : "生成",
                description: `${j.prompt} · ${TIERS[j.quality]}${j.source !== "normal" ? ` · ${SOURCES[j.source] || j.source}` : ""}${j.status === "failed" ? " · 已释放冻结" : ""}`,
                amount: j.status === "success" ? -j.cost_points : 0,
              })),
            ...recharges
              .filter((r) => r.amount !== 0)
              .map((r) => ({
                key: `r${r.id}`,
                date: r.created_at,
                type: "充值",
                description: r.money_amount
                  ? `人工/在线充值 ¥${r.money_amount} · 已审核`
                  : r.admin_note || "积分调整",
                amount: r.amount,
              })),
          ].sort((a, b) => b.date.localeCompare(a.date)),
        );
      })
      .catch(() => {
        if (!stopped) setError("积分明细读取失败，请刷新重试");
      });
    return () => {
      stopped = true;
    };
  }, []);
  return (
    <section className="panel ledger">
      <h2>积分明细</h2>
      {error && <p role="alert">{error}</p>}
      {!rows && !error && <p role="status">正在读取…</p>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>说明</th>
              <th>变动</th>
            </tr>
          </thead>
          <tbody>
            {rows?.slice(0, limit).map((r) => (
              <tr key={r.key}>
                <td>{r.date.slice(5, 16).replace("T", " ")}</td>
                <td>{r.type}</td>
                <td>{r.description}</td>
                <td className={r.amount > 0 ? "positive" : ""}>
                  {r.amount > 0 ? "+" : ""}
                  {r.amount}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows?.length === 0 && <p className="empty-note">暂无积分变动</p>}
      {rows?.length > limit && (
        <button className="load-more" onClick={() => setLimit((v) => v + 20)}>
          加载更多
        </button>
      )}
    </section>
  );
}
function Security({ user, refresh }) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e, path, payload) {
    e.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      await request.post(path, payload);
      setStatus("已保存");
      e.target.reset();
      refresh();
    } catch (err) {
      setStatus(errorText(err, "保存失败，请检查输入"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel security">
      <h1>安全设置</h1>
      <p className="muted">绑定邮箱后，可以通过邮件找回密码。</p>
      <p>
        邮箱：{user?.email || "未绑定"} · 手机：
        {user?.phone
          ? `${user.phone.slice(0, 3)}****${user.phone.slice(-4)}`
          : "未绑定"}
      </p>
      <form
        onSubmit={(e) => {
          const data = new FormData(e.target);
          submit(e, "/auth/change-password", Object.fromEntries(data));
        }}
      >
        <h2>修改密码</h2>
        <label>
          当前密码
          <input
            name="old_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          新密码
          <input
            name="new_password"
            type="password"
            minLength={6}
            autoComplete="new-password"
            required
          />
        </label>
        <button className="btn-primary" disabled={busy}>
          保存密码
        </button>
      </form>
      {!user?.email && (
        <form
          onSubmit={(e) => {
            const data = new FormData(e.target);
            submit(e, "/auth/bind-email", {
              ...Object.fromEntries(data),
              username: user?.username || "",
              password: "",
            });
          }}
        >
          <h2>绑定邮箱</h2>
          <label>
            邮箱
            <input name="email" type="email" required />
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={async (e) => {
              const email = e.currentTarget.form.elements.email.value;
              try {
                await request.post("/auth/send-code", { email });
                setStatus("验证码已发送");
              } catch (err) {
                setStatus(errorText(err, "发送失败"));
              }
            }}
          >
            发送验证码
          </button>
          <label>
            验证码
            <input name="code" required />
          </label>
          <button className="btn-primary" disabled={busy}>
            绑定邮箱
          </button>
        </form>
      )}
      {!user?.phone && (
        <form
          onSubmit={(e) => {
            const data = new FormData(e.target);
            submit(e, "/auth/bind-phone", {
              ...Object.fromEntries(data),
              password: "",
              captcha_code: "",
            });
          }}
        >
          <h2>绑定手机</h2>
          <label>
            手机号
            <input name="phone" pattern="[0-9]{11}" required />
          </label>
          <button className="btn-primary" disabled={busy}>
            绑定手机
          </button>
        </form>
      )}
      <p role="status">{status}</p>
    </section>
  );
}
export default function ProfilePage() {
  const billing = useBilling();
  const [tab, setTab] = useState("account");
  const [recharge, setRecharge] = useState(false);
  const user = billing.user;
  return (
    <div className="profile-page panel">
      <aside className="profile-sidebar">
        <div className="profile-identity">
          <span className="avatar" />
          <div>
            <strong>{user?.username || "账户"}</strong>
            <small>UID: {user?.uid || "…"}</small>
          </div>
        </div>
        <button
          aria-pressed={tab === "account"}
          onClick={() => setTab("account")}
        >
          账户与积分
        </button>
        <button aria-pressed={tab === "api"} onClick={() => setTab("api")}>
          API 与 MCP
        </button>
        <button
          aria-pressed={tab === "security"}
          onClick={() => setTab("security")}
        >
          安全设置
        </button>
        {user?.is_admin && <Link to="/admin">管理后台</Link>}
        <button className="logout-button" onClick={logout}>
          退出登录
        </button>
      </aside>
      <div className="profile-content">
        {tab === "account" ? (
          <>
            <section className="balance-card">
              <div>
                <h1>可用积分</h1>
                <strong>
                  {user?.unlimited_credits
                    ? "∞ 无限积分"
                    : Math.max(
                        0,
                        (user?.points || 0) - (user?.frozen_points || 0),
                      )}
                </strong>
                <p>
                  免费试用剩{" "}
                  {Math.max(
                    0,
                    (user?.trial_remaining || 0) - (user?.frozen_trials || 0),
                  )}{" "}
                  次 · 冻结中 {user?.frozen_points || 0} 积分 /{" "}
                  {user?.frozen_trials || 0} 次
                </p>
              </div>
              <button onClick={() => setRecharge(true)}>充值</button>
            </section>
            <Ledger />
          </>
        ) : tab === "api" ? (
          <ApiMcp />
        ) : (
          <Security user={user} refresh={billing.refresh} />
        )}
      </div>
      {recharge && (
        <RechargeModal
          uid={user?.uid}
          hasUsedExperience={user?.has_used_experience}
          onClose={() => setRecharge(false)}
          onSuccess={() => {
            billing.refresh();
            creditsChanged();
          }}
        />
      )}
    </div>
  );
}
