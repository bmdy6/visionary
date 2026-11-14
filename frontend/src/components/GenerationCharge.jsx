import { useState } from 'react';
import RechargeModal from './RechargeModal';

export default function GenerationCharge({ billing, quality }) {
  const [open, setOpen] = useState(false);
  const charge = billing.charge(quality);
  return <div className="normal-charge" aria-live="polite"><span>{charge.text}</span>
    {charge.ready && !charge.allowed && <button type="button" className="assistant-link" onClick={() => setOpen(true)}>去充值</button>}
    {open && <RechargeModal uid={billing.user?.uid} hasUsedExperience={billing.user?.has_used_experience} onClose={() => setOpen(false)} onSuccess={billing.refresh} />}
  </div>;
}
