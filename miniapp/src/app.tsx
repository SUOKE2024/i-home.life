import { useEffect } from 'react';
import { useDidShow, useDidHide } from '@tarojs/taro';
import { callFunction, getDataSource, subscribeDataSource } from '@/services/cloud';
import { bootstrapSession, subscribeSession } from '@/services/session';
import { installWeappPrivacyGate } from '@/services/privacy-gate';
import { useAppStore } from '@/store/useAppStore';
// 全局样式
import './app.scss';

function App(props) {
  useEffect(() => {
    // 隐私授权门：需在调用任何隐私接口前安装（app.json 已开启 __usePrivacyCheck__）。
    // 非微信端或基础库过低时返回 false，不影响启动。
    installWeappPrivacyGate();

    // 数据来源与数据层解耦：任意页面触发降级，全局状态同步，页面可展示「演示数据」标识
    const offSource = subscribeDataSource((source, reason) => {
      const state = useAppStore.getState();
      if (state.dataSource !== source || state.dataSourceReason !== reason) {
        state.setDataSource(source, reason);
      }
    });

    const offSession = subscribeSession((phase) => {
      useAppStore.getState().setSessionPhase(phase);
    });

    // 启动：先建会话（微信小程序静默登录），再预热业务数据；失败不阻塞首屏
    bootstrapSession()
      .then((ok) => {
        console.info('[App] 会话初始化完成', { authenticated: ok });
        return callFunction('login');
      })
      .catch((err) => console.error('[App] 启动初始化失败', err));

    const current = getDataSource();
    if (current.source !== 'unknown') {
      useAppStore.getState().setDataSource(current.source, current.reason);
    }

    return () => {
      offSource();
      offSession();
    };
  }, []);

  // 对应 onShow
  useDidShow(() => {});

  // 对应 onHide
  useDidHide(() => {});

  return props.children;
}

export default App;
