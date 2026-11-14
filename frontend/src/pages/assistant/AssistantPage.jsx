import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUp, Paperclip } from 'lucide-react';
import RechargeModal from '../../components/RechargeModal';
import useAssistant from './useAssistant';
import PlanCard from './PlanCard';

export default function AssistantPage({ billing, switcher }) {
  const a = useAssistant();
  const [message, setMessage] = useState('');
  const [reference, setReference] = useState(null);
  const [recharge, setRecharge] = useState(false);
  const end = useRef(null);
  const plan = a.conversation?.plan;
  useEffect(() => { end.current?.scrollIntoView({ block:'nearest' }); }, [a.conversation?.messages.length]);
  async function submit(e) {
    e.preventDefault();
    if (await a.send(message.trim(), reference)) { setMessage(''); setReference(null); }
  }
  function upload(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      a.setError('请选择不超过 5 MB 的 PNG、JPEG 或 WebP 图片'); return;
    }
    const reader = new FileReader();
    reader.onload = () => setReference({data:reader.result, name:file.name.slice(0,120)});
    reader.onerror = () => a.setError('图片读取失败，请重新选择');
    reader.readAsDataURL(file);
    e.target.value = '';
  }
  return <div className="assistant-workspace">
    <section className="assistant-chat" aria-label="AI 助手对话">
      <header className="assistant-chat-header">{switcher}<button type="button" className="assistant-link" disabled={a.busy} onClick={a.newConversation}>新对话 +</button></header>
      <div className="assistant-messages" role="log" aria-label="对话消息" aria-live="polite">
        {!a.conversation?.messages.length && <div className="assistant-empty"><h2>先聊聊你的灵感</h2><p>告诉我想做什么、送给谁，或上传一张参考图。我们先一起把方案定下来。</p></div>}
        {a.conversation?.messages.map((m,i) => <div key={i} className={`chat-message ${m.role}`}><p>{m.content}</p>{m.reference_name && <span className="reference-bound">📎 已绑定参考图 · {m.reference_name}</span>}{m.demo && <small>演示对话</small>}</div>)}
        {a.busy && <p className="muted" role="status">正在处理…</p>}<div ref={end} />
      </div>
      {a.error && <p className="assistant-error" role="alert">{a.error}</p>}
      {reference && <div className="pending-reference"><img src={reference.data} alt="待绑定参考图" /><span>{reference.name}</span><button type="button" onClick={() => setReference(null)} aria-label="取消上传">×</button></div>}
      <form className="assistant-composer" onSubmit={submit}>
        <label className="assistant-upload" title="上传参考图"><Paperclip size={18}/><span className="sr-only">上传参考图</span><input type="file" accept="image/png,image/jpeg,image/webp" disabled={a.busy} onChange={upload}/></label>
        <textarea aria-label="描述你的想法" placeholder="继续描述，或说「就这样」…" value={message} maxLength={1000} disabled={a.busy} onChange={e => setMessage(e.target.value)} />
        <button type="submit" className="btn-primary" aria-label="发送消息" disabled={a.busy || !message.trim()}><ArrowUp size={18}/></button>
      </form>
    </section>
    <div className="assistant-right">
      <PlanCard key={`${plan?.plan_id}-${plan?.version}`} plan={plan} charge={billing.charge(plan?.data.quality || 'standard')} pricing={billing.config?.pricing} busy={a.busy} onEdit={a.edit} onGenerate={a.generate} onRecharge={() => setRecharge(true)} />
      <section className="assistant-result" aria-label="生成结果" aria-live="polite">
        {!plan?.task_id ? <div className="assistant-empty">确认方案后，作品会在这里出现。</div> : a.task?.status === 'success' ? <>
          <img className="assistant-result-image" src={a.task.image_url} alt="AI 助手生成结果"/>
          <div className="assistant-result-actions"><a href={`/api/image/download?id=${plan.task_id}`} download className="assistant-link">下载图片</a><Link to="/history" className="assistant-link">我的作品 · 继续改</Link></div>
        </> : ['failed','deleted'].includes(a.task?.status) ? <div className="assistant-empty"><h2>{a.task.status === 'failed' ? '生成失败' : '作品已删除'}</h2><p>{a.task.status === 'failed' ? '本次冻结已释放；可编辑方案后重新确认。' : '本版保留提交记录，避免重复扣费。'}</p><Link to="/history">查看我的作品</Link></div> : <div className="assistant-empty"><h2>生成中…</h2><p>可以离开这个页面，完成后在「我的作品」里也能看到</p><progress aria-label="生成进度" /></div>}
      </section>
    </div>
    {recharge && <RechargeModal uid={billing.user?.uid} hasUsedExperience={billing.user?.has_used_experience} onClose={() => setRecharge(false)} onSuccess={billing.refresh}/>}
  </div>;
}
