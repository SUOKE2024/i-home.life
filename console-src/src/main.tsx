import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { initTheme } from './services/theme';
import './tokens/tokens.css';

// 启动时应用持久化主题，避免主题 FOUC（对齐 Flutter ThemeState 启动加载）
initTheme();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename="/console">
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
