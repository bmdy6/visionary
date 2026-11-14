import { useEffect, useRef, useState } from 'react';
import request from '../../api/request';
import { creditsChanged } from '../../hooks/useBilling';

export default function useAssistant() {
  const [conversation, setConversation] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [taskState, setTask] = useState(null);
  const mounted = useRef(true);
  const lock = useRef(false);
  useEffect(() => {
    mounted.current = true;
    request.get('/assistant/conversations/latest').then(c => { if (mounted.current) setConversation(c); }).catch(() => { if (mounted.current) setError('对话加载失败，请刷新重试'); }).finally(() => { if (mounted.current) setBusy(false); });
    return () => { mounted.current = false; };
  }, []);
  const taskId = conversation?.plan?.task_id;
  useEffect(() => {
    if (!taskId) return;
    let stopped = false;
    let timer;
    let attempts = 0;
    async function poll() {
      try {
        const t = await request.get(`/image/status/${taskId}`);
        if (stopped) return;
        setTask(t);
        if (['success', 'failed'].includes(t.status)) { creditsChanged(); return; }
      } catch (e) {
        if (stopped) return;
        if (e.response?.status === 404) { setTask({ id:taskId, status: 'deleted' }); return; }
      }
      if (!stopped && ++attempts < 180) timer = setTimeout(poll, 2000);
      else if (!stopped) setError('等待较久，可在“我的创作”查看结果；未重复提交任务。');
    }
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [taskId]);

  async function run(action) {
    if (lock.current) return false;
    lock.current = true; setBusy(true); setError('');
    try { await action(); return true; }
    catch (e) {
      const detail = e.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : '操作失败，请检查网络后重试');
      if (e.response?.status === 409 && conversation) {
        const latest = await request.get(`/assistant/conversations/${conversation.id}`).catch(() => null);
        if (latest) setConversation(latest);
      }
      return false;
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  const newConversation = () => run(async () => setConversation(await request.post('/assistant/conversations')));
  const send = (message, reference) => run(async () => {
    const c = conversation || await request.post('/assistant/conversations');
    // Keep a newly created conversation even when the first turn fails.
    setConversation(c);
    const next = await request.post(`/assistant/conversations/${c.id}/messages`, {
      message, revision:c.revision, reference_data:reference?.data, reference_name:reference?.name,
    });
    setConversation(next);
  });
  const edit = (plan, removeReference) => run(async () => setConversation(await request.put(`/assistant/conversations/${conversation.id}/plan`, {
    revision:conversation.revision, plan, remove_reference:removeReference,
  })));
  const generate = () => run(async () => {
    const p = conversation.plan;
    const result = await request.post('/image/generate', { prompt:p.data.prompt, plan_id:p.plan_id, plan_version:p.version });
    setConversation(c => ({...c, plan:{...c.plan, task_id:result.id}}));
    creditsChanged();
  });
  return { conversation, task:taskState?.id === taskId ? taskState : null, busy, error, setError, newConversation, send, edit, generate };
}
