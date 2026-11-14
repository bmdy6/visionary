import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import request from "../api/request";
import useBilling from "../hooks/useBilling";
import WorkDetail from "../components/WorkDetail";
import { continueFrom, errorText, SOURCES } from "../utils/creation";

export default function HistoryPage() {
  const [source, setSource] = useState("");
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const [detail, setDetail] = useState(null);
  const { user } = useBilling();
  const navigate = useNavigate();
  const epoch = useRef(0);
  useEffect(() => {
    let stopped = false;
    const requestEpoch = ++epoch.current;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const data = await request.get("/image/history", {
          params: { source: source || undefined, keyword, limit: 20 },
        });
        if (!stopped && requestEpoch === epoch.current) {
          setItems(data);
          setMore(data.length === 20);
        }
      } catch (e) {
        if (!stopped && requestEpoch === epoch.current)
          setError(errorText(e, "作品读取失败"));
      } finally {
        if (!stopped && requestEpoch === epoch.current) setLoading(false);
      }
    }, 200);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [source, keyword]);
  async function loadMore() {
    const requestEpoch = epoch.current;
    setLoading(true);
    try {
      const data = await request.get("/image/history", {
        params: {
          source: source || undefined,
          keyword,
          skip: items.length,
          limit: 20,
        },
      });
      if (requestEpoch === epoch.current) {
        setItems((prev) => [...prev, ...data]);
        setMore(data.length === 20);
      }
    } catch (e) {
      if (requestEpoch === epoch.current) setError(errorText(e, "读取失败"));
    } finally {
      if (requestEpoch === epoch.current) setLoading(false);
    }
  }
  function reuse(job) {
    sessionStorage.setItem("pending_reuse", JSON.stringify(continueFrom(job)));
    navigate("/");
  }
  return (
    <section className="history-page">
      <header className="page-heading">
        <h1>我的作品</h1>
        <input
          type="search"
          aria-label="搜索提示词"
          placeholder="搜索提示词"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <div className="segmented" aria-label="按来源筛选">
          {Object.entries({ "": "全部", ...SOURCES }).map(([k, v]) => (
            <button
              key={k}
              aria-pressed={source === k}
              onClick={() => setSource(k)}
            >
              {v}
            </button>
          ))}
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
      {loading && <p role="status">正在读取作品…</p>}
      {!loading && !items.length && (
        <div className="creation-empty">
          <h2>还没有作品</h2>
          <p>这个来源下还没有匹配的作品，试试其他筛选或去创作。</p>
        </div>
      )}
      <div className="history-grid">
        {items.map((job) => (
          <article key={job.id} className="history-card">
            <div className="history-image">
              <button
                className="history-open"
                aria-label={`打开作品 ${job.id}`}
                onClick={() => setDetail(job)}
              >
                {job.image_url ? (
                  <img src={job.image_url} alt={job.prompt} loading="lazy" />
                ) : (
                  <span>
                    {job.status === "failed" ? "生成失败" : "生成中…"}
                  </span>
                )}
              </button>
              {job.status === "success" && (
                <div className="hover-actions">
                  <button onClick={() => reuse(job)}>继续改</button>
                  <a href={`/api/image/download?id=${job.id}`} download>
                    下载
                  </a>
                  <button
                    aria-label={`作品 ${job.id} 详情`}
                    onClick={() => setDetail(job)}
                  >
                    ···
                  </button>
                </div>
              )}
            </div>
            <div className="history-caption">
              <p>{job.prompt}</p>
              <small>
                {job.created_at?.slice(5, 10)}
                {job.source !== "normal" &&
                  ` · ${SOURCES[job.source] || job.source}`}
              </small>
            </div>
          </article>
        ))}
      </div>
      {more && (
        <button className="load-more" disabled={loading} onClick={loadMore}>
          加载更多
        </button>
      )}
      {detail && (
        <WorkDetail
          key={detail.id}
          job={detail}
          user={user}
          onClose={() => setDetail(null)}
          onDelete={(id) => setItems((prev) => prev.filter((j) => j.id !== id))}
        />
      )}
    </section>
  );
}
