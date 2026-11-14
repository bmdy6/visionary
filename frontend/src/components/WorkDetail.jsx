import { lazy, Suspense, useState } from "react";
import { useNavigate } from "react-router-dom";
import request from "../api/request";
import useDialog from "../hooks/useDialog";
import {
  continueFrom,
  TIERS,
  STYLES,
  SOURCES,
  errorText,
  active,
} from "../utils/creation";
const SharePosterModal = lazy(() => import("./SharePosterModal"));

export function WorkActions({ job, onContinue, onDetail }) {
  return (
    <div className="work-actions">
      <button className="btn-primary" onClick={() => onContinue(job)}>
        以此为参考继续改
      </button>
      <a
        className="quiet-button"
        href={`/api/image/download?id=${job.id}`}
        download
      >
        下载
      </a>
      {onDetail && (
        <button
          className="quiet-button"
          aria-label="作品详情"
          onClick={() => onDetail(job)}
        >
          ···
        </button>
      )}
    </div>
  );
}
export default function WorkDetail({ job, onClose, onDelete, onContinue }) {
  const navigate = useNavigate();
  const dialog = useDialog(onClose);
  const [poster, setPoster] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function reuse(value) {
    if (onContinue) {
      onContinue(value);
      onClose();
      return;
    }
    sessionStorage.setItem(
      "pending_reuse",
      JSON.stringify(continueFrom(value)),
    );
    navigate("/");
  }
  async function remove() {
    if (!window.confirm("删除这张作品？此操作无法撤销。")) return;
    setBusy(true);
    try {
      await request.delete(`/image/${job.id}`);
      onDelete?.(job.id);
      onClose();
    } catch (e) {
      setError(errorText(e, "删除失败，请重试"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        className="work-detail panel"
        role="dialog"
        aria-modal="true"
        aria-label="作品详情"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="dialog-close"
          autoFocus
          onClick={onClose}
          aria-label="关闭详情"
        >
          ×
        </button>
        {job.image_url ? (
          <img src={job.image_url} alt={job.prompt} />
        ) : (
          <p className="creation-empty">
            {job.status === "failed" ? "生成失败，冻结已释放" : "正在生成…"}
          </p>
        )}
        <div className="detail-content">
          <h2>作品详情</h2>
          <p>{job.prompt}</p>
          <p className="muted">
            {job.aspect_ratio} · {TIERS[job.quality]} ·{" "}
            {STYLES[job.style] || job.style} · {SOURCES[job.source] || "网页"}
          </p>
          {job.status === "success" && (
            <WorkActions job={job} onContinue={reuse} />
          )}
          <div className="work-actions">
            {job.status === "success" && (
              <button onClick={() => setPoster(true)}>分享海报</button>
            )}
            <button disabled={busy || active(job)} onClick={remove}>
              删除作品
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
        </div>
        {poster && (
          <Suspense fallback={<p role="status">正在加载海报…</p>}>
            <SharePosterModal imageLog={job} onClose={() => setPoster(false)} />
          </Suspense>
        )}
      </section>
    </div>
  );
}
