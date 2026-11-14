import { useEffect, useRef, useState } from "react";
import request from "../api/request";
import useBilling, { creditsChanged } from "../hooks/useBilling";
import GenerationCharge from "../components/GenerationCharge";
import WorkDetail, { WorkActions } from "../components/WorkDetail";
import {
  active,
  continueFrom,
  errorText,
  STYLES,
  TIERS,
} from "../utils/creation";

function initialDraft() {
  try {
    const saved = JSON.parse(sessionStorage.getItem("pending_reuse") || "null");
    return (
      saved || {
        prompt: sessionStorage.getItem("pending_prompt") || "",
        quality: "standard",
        style: "default",
        aspect_ratio: "1:1",
        ref_image_url: "",
      }
    );
  } catch {
    return {
      prompt: "",
      quality: "standard",
      style: "default",
      aspect_ratio: "1:1",
      ref_image_url: "",
    };
  }
}
export default function HomePage({ switcher }) {
  const billing = useBilling();
  const [draft, setDraft] = useState(initialDraft);
  const [jobs, setJobs] = useState([]);
  const [restored, setRestored] = useState(false);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [original, setOriginal] = useState("");
  const input = useRef(null);
  const requestLock = useRef(false);
  const change = (key, value) => setDraft((d) => ({ ...d, [key]: value }));
  const selectedJob = jobs.find((j) => j.id === selected) || jobs[0];
  const running = jobs.filter(active).length;
  const charge = billing.charge(draft.quality);
  useEffect(() => {
    let mounted = true;
    if (localStorage.getItem("isGuest") !== "true")
      request
        .get("/image/history?limit=100")
        .then((data) => {
          if (mounted) {
            setRestored(true);
            setJobs(data);
            setSelected(data[0]?.id);
          }
        })
        .catch(() => {
          if (mounted) {
            setError("作品读取失败，请刷新重试");
            setRestored(true);
          }
        });
    const pending =
      sessionStorage.getItem("pending_reuse") ||
      sessionStorage.getItem("pending_prompt");
    sessionStorage.removeItem("pending_reuse");
    sessionStorage.removeItem("pending_prompt");
    if (pending) input.current?.focus();
    return () => {
      mounted = false;
    };
  }, []);
  useEffect(() => {
    if (!jobs.some(active)) return;
    let stopped = false;
    let polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const updates = await Promise.all(
          jobs.filter(active).map(async (job) => {
            try {
              return {
                ...job,
                ...(await request.get(`/image/status/${job.id}`)),
              };
            } catch (e) {
              if (e.response?.status === 404)
                return { ...job, status: "failed", error: "任务已不存在" };
              return job;
            }
          }),
        );
        if (!stopped) {
          setJobs((prev) =>
            prev.map((j) => updates.find((u) => u.id === j.id) || j),
          );
          if (updates.some((j) => !active(j))) creditsChanged();
        }
      } finally {
        polling = false;
      }
    };
    const timer = setInterval(poll, 1000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [jobs]);
  async function generate(e) {
    e.preventDefault();
    if (
      requestLock.current ||
      running >= 3 ||
      !draft.prompt.trim() ||
      !restored ||
      !charge.allowed
    )
      return;
    requestLock.current = true;
    setSubmitting(true);
    setError("");
    const payload = { ...draft, prompt: draft.prompt.trim() };
    try {
      const task = await request.post("/image/generate", payload);
      setJobs((prev) => [{ ...payload, ...task }, ...prev]);
      setSelected(task.id);
      creditsChanged();
    } catch (e) {
      setError(errorText(e, "生成提交失败，请重试"));
    } finally {
      requestLock.current = false;
      setSubmitting(false);
    }
  }
  function useReference(job) {
    setDraft(continueFrom(job));
    input.current?.focus();
  }
  function uploadFile(file) {
    if (!file) return;
    if (
      !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
      file.size > 5 * 1024 * 1024
    ) {
      setError("请选择不超过 5 MB 的 PNG、JPEG 或 WebP 图片");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => change("ref_image_url", reader.result);
    reader.onerror = () => setError("图片读取失败");
    reader.readAsDataURL(file);
  }
  async function enhance() {
    if (!draft.prompt.trim() || enhancing) return;
    setEnhancing(true);
    setError("");
    try {
      const r = await request.post("/image/enhance-prompt", {
        prompt: draft.prompt,
        style_id: draft.style,
      });
      setOriginal(draft.prompt);
      change("prompt", r.enhanced);
    } catch (e) {
      setError(errorText(e, "润色失败，请重试"));
    } finally {
      setEnhancing(false);
    }
  }
  return (
    <div className="normal-workspace">
      <section className="creation-panel panel" aria-label="创作输入">
        {switcher}
        <h1 className="sr-only">创作</h1>
        <form className="creation-form" onSubmit={generate}>
          <div className="prompt-box">
            <textarea
              ref={input}
              aria-label="画面描述"
              placeholder="描述你想生成的画面…"
              value={draft.prompt}
              maxLength={1000}
              onChange={(e) => change("prompt", e.target.value)}
              onPaste={(e) => {
                const file = [...e.clipboardData.items]
                  .find((i) => i.type.startsWith("image/"))
                  ?.getAsFile();
                if (file) {
                  e.preventDefault();
                  uploadFile(file);
                }
              }}
            />
            <div className="prompt-tools">
              {draft.ref_image_url && (
                <div className="reference-thumb">
                  <img src={draft.ref_image_url} alt="参考图" />
                  <button
                    type="button"
                    aria-label="移除参考图"
                    onClick={() => change("ref_image_url", "")}
                  >
                    ×
                  </button>
                </div>
              )}
              <label className="upload-button">
                📎 参考图
                <input
                  type="file"
                  aria-label="上传参考图"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    uploadFile(e.target.files[0]);
                    e.target.value = "";
                  }}
                />
              </label>
              <button
                type="button"
                disabled={
                  enhancing ||
                  !draft.prompt.trim() ||
                  !["default", "real", "product", "tech_poster"].includes(
                    draft.style,
                  )
                }
                onClick={enhance}
              >
                {enhancing ? "润色中…" : "✨ 润色"}
              </button>
              {original && (
                <button
                  type="button"
                  onClick={() => {
                    change("prompt", original);
                    setOriginal("");
                  }}
                >
                  撤销
                </button>
              )}
              <label className="mobile-style">
                <span className="sr-only">风格</span>
                <select
                  aria-label="移动风格"
                  value={draft.style}
                  onChange={(e) => change("style", e.target.value)}
                >
                  {Object.entries(STYLES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <small>{draft.prompt.length}/1000</small>
            </div>
          </div>
          <fieldset className="ratio-options">
            <legend>比例</legend>
            <div className="option-row">
              {["1:1", "9:16", "16:9"].map((r) => (
                <button
                  type="button"
                  key={r}
                  aria-pressed={draft.aspect_ratio === r}
                  onClick={() => change("aspect_ratio", r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="desktop-style">
            风格
            <select
              aria-label="风格"
              value={draft.style}
              onChange={(e) => change("style", e.target.value)}
            >
              {Object.entries(STYLES).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="tier-options">
            <legend>清晰度</legend>
            <div className="option-row">
              {Object.entries(TIERS).map(([k, v]) => (
                <button
                  type="button"
                  key={k}
                  aria-pressed={draft.quality === k}
                  onClick={() => change("quality", k)}
                >
                  {v} {billing.config?.pricing[k] ?? "…"}
                </button>
              ))}
            </div>
          </fieldset>
          <button
            className="btn-primary generate-button"
            disabled={
              submitting ||
              !restored ||
              running >= 3 ||
              !draft.prompt.trim() ||
              !charge.allowed ||
              enhancing
            }
          >
            {submitting
              ? "提交中…"
              : charge.unlimited
                ? "生成 · 无限积分"
                : charge.trial
                  ? "免费试用"
                  : `生成 · ${charge.cost ?? "…"} 积分`}
          </button>
          <GenerationCharge billing={billing} quality={draft.quality} />
          <p className="concurrency-note">
            生成中也可以继续提交，最多同时 3 张
            {running > 0 && ` · ${running} 张进行中`}
          </p>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>
      <section className="result-panel panel" aria-label="本次作品">
        <div className="result-main">
          {!selectedJob ? (
            <div className="creation-empty">
              <h2>把灵感变成画面</h2>
              <p>写下描述，选择比例和风格，开始创作。</p>
            </div>
          ) : selectedJob.status === "success" ? (
            <>
              <button
                className="result-image-button"
                onClick={() => setDetail(selectedJob)}
                aria-label="查看作品详情"
              >
                <img src={selectedJob.image_url} alt={selectedJob.prompt} />
              </button>
              <p className="result-caption">
                {selectedJob.prompt} · {selectedJob.aspect_ratio} ·{" "}
                {TIERS[selectedJob.quality]}
              </p>
              <WorkActions
                job={selectedJob}
                onContinue={useReference}
                onDetail={setDetail}
              />
            </>
          ) : selectedJob.status === "failed" ? (
            <div className="creation-empty">
              <h2>生成失败</h2>
              <p>冻结额度已释放，可以修改后重试。</p>
              <p>{selectedJob.error}</p>
            </div>
          ) : (
            <div className="creation-empty" role="status">
              <h2>正在生成…</h2>
              <p>可以继续输入并提交下一张</p>
              <progress aria-label="生成进度" />
            </div>
          )}
        </div>
        {jobs.length > 0 && (
          <aside className="job-strip" aria-label="作品列表">
            <small>最近</small>
            {jobs.map((job) => (
              <button
                key={job.id}
                aria-label={`查看任务 ${job.id}`}
                aria-pressed={job.id === selectedJob?.id}
                onClick={() => setSelected(job.id)}
              >
                {job.status === "success" ? (
                  <img src={job.image_url} alt="作品缩略图" />
                ) : job.status === "failed" ? (
                  "失败"
                ) : (
                  "生成中"
                )}
              </button>
            ))}
          </aside>
        )}
      </section>
      {detail && (
        <WorkDetail
          job={detail}
          user={billing.user}
          onClose={() => setDetail(null)}
          onContinue={useReference}
          onDelete={(id) => setJobs((prev) => prev.filter((j) => j.id !== id))}
        />
      )}
    </div>
  );
}
