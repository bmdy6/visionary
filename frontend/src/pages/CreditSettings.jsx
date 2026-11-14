import { useEffect, useState } from 'react';
import request from '../api/request';
import { creditsChanged } from '../hooks/useBilling';

const LABELS = { NEW_USER_FREE_GENERATIONS:'新用户免费试用次数', NEW_USER_POINTS:'新用户赠送积分', INVITE_REWARD_POINTS:'邀请奖励积分', INVITE_DAILY_LIMIT:'邀请每日上限' };
const TIERS = { standard:'标准', hd:'高清', master:'大师' };
export default function CreditSettings() {
  const [values, setValues] = useState(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const load = () => request.get('/admin/settings/credits').then(setValues).catch(() => setStatus('读取失败，请重试'));
  useEffect(() => { load(); }, []);
  const change = (key, value) => setValues(v => ({...v, [key]:{...v[key], value}}));
  async function save(e) {
    e.preventDefault(); setBusy(true); setStatus('');
    const payload = Object.fromEntries(Object.entries(values).map(([key,{value}]) => [key,
      key === 'TIER_COSTS' ? Object.entries(value).map(([k,v]) => `${k}:${v}`).join(',') : Array.isArray(value) ? value.join(',') : String(value)]));
    try { setValues(await request.put('/admin/settings/credits', payload)); setStatus('已保存，立即生效'); creditsChanged(); }
    catch(e) { setStatus(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '保存失败，请检查输入'); }
    finally { setBusy(false); }
  }
  function number(key) {
    return <div className="credits-setting-row" key={key}><div><label htmlFor={key}>{LABELS[key]}</label><small>{key} · 默认 {values[key].default}{key === 'NEW_USER_FREE_GENERATIONS' ? '，填 0 关闭；仅影响之后注册的新用户' : ''}</small></div>
      <input id={key} type="number" min="0" max="1000000" step="1" required value={values[key].value} onChange={e => change(key,e.target.value)}/></div>;
  }
  return <section className="credits-settings"><h2>系统设置 · 积分与试用</h2><p>改完立即生效，不用重启。未设置时用 .env 的值，再没有就用默认值。</p>
    {!values ? <div role="status">{status || '正在读取设置…'}<button className="assistant-link" onClick={load}>重试读取</button></div> : <form onSubmit={save}>
      <div className="credits-settings-card"><fieldset disabled={busy} className="credits-settings-fields">
        {number('NEW_USER_FREE_GENERATIONS')}
        <div className="credits-setting-row"><div><strong>试用可用档位</strong><small>TRIAL_ALLOWED_TIERS · 默认只有标准档</small></div><div className="plan-options">
          {Object.entries(TIERS).map(([k,v]) => <button type="button" key={k} aria-pressed={values.TRIAL_ALLOWED_TIERS.value.includes(k)} onClick={() => change('TRIAL_ALLOWED_TIERS', values.TRIAL_ALLOWED_TIERS.value.includes(k) ? values.TRIAL_ALLOWED_TIERS.value.filter(t => t !== k) : [...values.TRIAL_ALLOWED_TIERS.value,k])}>{v}</button>)}
        </div></div>
        {number('NEW_USER_POINTS')}
        <div className="credits-setting-row"><div><strong>各档位价格</strong><small>TIER_COSTS · 默认 {values.TIER_COSTS.default}</small></div><div className="credits-tier-inputs">{Object.entries(TIERS).map(([k,v]) => <label key={k}>{v}<input aria-label={`${v}积分价格`} type="number" required min="0" max="1000000" step="1" value={values.TIER_COSTS.value[k]} onChange={e => change('TIER_COSTS', {...values.TIER_COSTS.value, [k]:e.target.value})}/></label>)}</div></div>
        {number('INVITE_REWARD_POINTS')}{number('INVITE_DAILY_LIMIT')}
        <div className="credits-setting-row"><div><label htmlFor="ASSISTANT_MODE_ENABLED">开放 AI 助手模式</label><small>ASSISTANT_MODE_ENABLED · 默认开启</small></div><input id="ASSISTANT_MODE_ENABLED" className="credits-toggle" type="checkbox" checked={values.ASSISTANT_MODE_ENABLED.value} onChange={e => change('ASSISTANT_MODE_ENABLED', e.target.checked)}/></div>
      </fieldset></div>
      <div className="credits-settings-actions"><button className="btn-primary" type="submit" disabled={busy}>{busy ? '保存中…' : '保存设置'}</button><span role="status">{status}</span></div>
    </form>}
  </section>;
}
