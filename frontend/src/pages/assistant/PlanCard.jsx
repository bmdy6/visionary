import { useState } from 'react';

const STYLES = { illustration:'治愈插画', real:'真实摄影', watercolor:'水彩', default:'默认风格' };
const TIERS = { standard:'标准', hd:'高清', master:'大师' };

export default function PlanCard({ plan, charge, pricing, busy, onEdit, onGenerate, onRecharge }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(plan?.data);
  const [removeReference, setRemoveReference] = useState(false);
  const data = editing ? draft : plan?.data;
  const change = (key, value) => setDraft(d => ({ ...d, [key]:value }));
  async function save(e) {
    e.preventDefault();
    if (await onEdit(draft, removeReference)) setEditing(false);
  }
  function options(key, values) {
    return <div className="plan-options">{Object.entries(values).map(([value, label]) => <button key={value} type="button"
      disabled={!editing || busy} aria-pressed={data[key] === value} onClick={() => change(key, value)}>{label}</button>)}</div>;
  }
  return <section className="assistant-plan">
    <header><h1>生成方案 {plan && <span className="plan-version">第 {plan.version} 版</span>}</h1></header>
    <p className="discussion-notice">只是讨论，确认前不会生成，也不扣积分</p>
    {!data ? <div className="assistant-empty">先说说想画什么，聊好后方案会出现在这里。</div> : <form onSubmit={save}>
      <dl className="plan-fields">
        <dt>画面描述</dt><dd>{editing ? <textarea required aria-label="画面描述" maxLength={1000} value={draft.prompt} onChange={e => change('prompt', e.target.value)} /> : <p>{data.prompt}</p>}</dd>
        <dt>比例</dt><dd>{options('aspect_ratio', { '1:1':'1:1', '9:16':'9:16', '16:9':'16:9' })}</dd>
        <dt>风格</dt><dd><select aria-label="方案风格" disabled={!editing || busy} value={data.style} onChange={e => change('style', e.target.value)}>{Object.entries(STYLES).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></dd>
        <dt>档位</dt><dd>{options('quality', Object.fromEntries(Object.entries(TIERS).map(([k,v]) => [k, `${v} ${pricing?.[k] ?? '…'} 积分`])) )}</dd>
        <dt>参考图</dt><dd>{data.ref_image_url && !removeReference ? <div className="plan-reference"><img src={data.ref_image_url} alt="绑定的参考图" />{editing && <button type="button" onClick={() => setRemoveReference(true)} aria-label="移除参考图">×</button>}</div> : <span className="muted">未绑定，可在对话中上传</span>}</dd>
      </dl>
      {editing ? <div key="editing" className="plan-edit-actions"><button type="button" className="assistant-secondary" onClick={() => setEditing(false)}>取消编辑</button><button className="btn-primary" type="submit" disabled={busy || !draft.prompt.trim()}>保存方案</button></div> : <div key="confirmation" className="assistant-confirm">
        <div className="charge-description" aria-live="polite">{plan.task_id ? '本版已提交，可在“我的创作”查看' : charge.text}</div>
        <button className="assistant-secondary" type="button" disabled={busy} onClick={() => { setDraft(plan.data); setEditing(true); }}>编辑方案</button>
        <button className="btn-primary" type="button" disabled={busy || !charge.allowed || !!plan.task_id} onClick={onGenerate}>{plan.task_id ? '本版已提交' : busy ? '正在提交…' : '确认生成'}</button>
        {!charge.allowed && charge.ready && !plan.task_id && <button className="assistant-link" type="button" onClick={onRecharge}>去充值</button>}
      </div>}
    </form>}
  </section>;
}
