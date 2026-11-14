import { useState } from 'react';
import HomePage from './HomePage';
import MobileHomePage from './MobileHomePage';
import AssistantPage from './assistant/AssistantPage';
import useBilling from '../hooks/useBilling';
import './assistant/assistant.css';

function savedMode() {
  try {
    if (sessionStorage.getItem('pending_reuse') || sessionStorage.getItem('pending_prompt')) return 'normal';
    return localStorage.getItem('visionary_creation_mode') === 'assistant' ? 'assistant' : 'normal';
  } catch { return 'normal'; }
}

export default function CreationPage({ isMobile }) {
  const [mode, setMode] = useState(savedMode);
  const billing = useBilling();
  const assistant = billing.config?.assistant_mode_enabled && mode === 'assistant';
  function selectMode(value) {
    setMode(value);
    try { localStorage.setItem('visionary_creation_mode', value); } catch { /* Private browsing may disable storage. */ }
  }
  const switcher = billing.config?.assistant_mode_enabled && <div className="creation-switch" aria-label="创作模式">
    <button type="button" aria-pressed={!assistant} onClick={() => selectMode('normal')}>普通模式</button>
    <button type="button" aria-pressed={!!assistant} onClick={() => selectMode('assistant')}>AI 助手</button>
  </div>;
  return assistant ? <AssistantPage billing={billing} switcher={switcher} /> : <>
    <div className="normal-mode-switch">{switcher}</div>
    {isMobile ? <MobileHomePage /> : <HomePage />}
  </>;
}
