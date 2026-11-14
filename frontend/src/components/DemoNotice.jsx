import { useEffect, useState } from 'react';
import request from '../api/request';
import './DemoNotice.css';

export default function DemoNotice() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    let active = true;
    request.get('/image/config').then(config => {
      if (active) setDemo(config.demo_mode === true);
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  return demo ? (
    <p className="demo-notice" role="status">
      演示模式：返回内置示例图，不根据提示词或参考图生成新图；成功后照常扣除本地积分。
    </p>
  ) : null;
}
