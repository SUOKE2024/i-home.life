import React, { useEffect } from 'react';
import { useDidShow, useDidHide } from '@tarojs/taro';
import { callFunction } from '@/services/cloud';
// 全局样式
import './app.scss';

function App(props) {
  useEffect(() => {
    // 启动时预热一次数据层（所有平台统一走 src/data/ 本地数据源）
    callFunction('login')
      .then(() => console.info('[App] 本地数据源预热完成'))
      .catch((err) => console.error('[App] 本地数据源预热失败', err));
  }, []);

  // 对应 onShow
  useDidShow(() => {});

  // 对应 onHide
  useDidHide(() => {});

  return props.children;
}

export default App;