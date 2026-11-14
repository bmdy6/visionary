import { useCallback, useEffect, useState } from 'react';
import request from '../api/request';

export const creditsChanged = () => window.dispatchEvent(new Event('credits-changed'));

export function chargeFor(user, config, tier) {
  if (!user || !config?.pricing) return { ready: false, allowed: false, text: '正在读取费用…' };
  const trials = Math.max(0, user.trial_remaining - user.frozen_trials);
  const trial = trials > 0 && config.trial_allowed_tiers.includes(tier);
  const cost = config.pricing[tier];
  const short = Math.max(0, cost - (user.points - user.frozen_points));
  return { ready: true, allowed: trial || short === 0, trial, cost, short,
    text: trial ? `本次免费，用 1 次试用，剩 ${trials - 1} 次` : short ? `积分不足，还差 ${short}` : `消耗 ${cost} 积分` };
}

export default function useBilling() {
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const refresh = useCallback(() => {
    const isGuest = localStorage.getItem('isGuest') === 'true';
    return Promise.all([isGuest ? null : request.get('/auth/me'), request.get('/image/config')])
      .then(([info, settings]) => { setUser(info); setConfig(settings); })
      .catch(() => { /* Keep the last confirmed snapshot; server validates every request. */ });
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener('credits-changed', refresh);
    window.addEventListener('focus', refresh);
    const timer = setInterval(refresh, 60000);
    return () => { clearInterval(timer); window.removeEventListener('credits-changed', refresh); window.removeEventListener('focus', refresh); };
  }, [refresh]);
  return { user, config, refresh, charge: (tier) => chargeFor(user, config, tier) };
}

export function trialBadge(user) {
  const trials = Math.max(0, (user?.trial_remaining || 0) - (user?.frozen_trials || 0));
  return trials ? `🎁 免费试用 剩 ${trials} 次 · ${user?.points || 0} 积分` : `${user?.points || 0} 积分`;
}
