/**
 * SettingsPage — 对齐 flutter_app/lib/pages/settings_page.dart
 *
 * 结构：Scaffold > AppBar(设置) > ListView[个人资料/主题/通知/其他(退出)]
 * API：GET /api/auth/me（用户信息）、POST /api/auth/logout（退出）
 *
 * 主题：light/dark/system 三态，system 由 matchMedia 解析；持久化 'settings_theme_mode'。
 *      主题逻辑复用 services/theme.ts（main.tsx 启动时也调用 initTheme 避免 FOUC）。
 */

import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import { applyTheme, readStoredMode, type ThemeMode } from '../services/theme';
import type { User } from '../types/domain';
import { useState, useEffect } from 'react';

const ROLE_LABELS: Record<string, string> = {
  homeowner: '业主',
  owner: '业主',
  designer: '设计师',
  contractor: '施工方',
  supplier: '供应商',
  admin: '管理员',
};

export default function SettingsPage() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<ThemeMode>('system');
  const [notifyOrder, setNotifyOrder] = useState(true);
  const [notifyTask, setNotifyTask] = useState(true);
  const [notifyQuality, setNotifyQuality] = useState(true);

  useEffect(() => {
    // 初始化：读取持久化主题（main.tsx 已应用，此处仅同步 state）
    setTheme(readStoredMode());
    // system 模式下，跟随 OS 主题变化实时更新 data-theme
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = () => {
      if (readStoredMode() === 'system') applyTheme('system');
    };
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, []);

  const { data: user, loading, error } = useAsync<User>(async () => {
    const r = await apiClient.getCurrentUser<User>();
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? '未登录');
    return r.data;
  }, []);

  function changeTheme(mode: ThemeMode) {
    setTheme(mode);
    applyTheme(mode);
  }

  async function handleLogout() {
    if (!confirm('确定退出登录？')) return;
    await apiClient.logout();
    navigate('/');
    // 刷新以重置应用状态
    window.location.reload();
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-settings-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">设置</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-settings-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-settings-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
            </div>
          )}

          {user && !loading && (
            <>
              {/* 个人资料 */}
              <div className="wb-settings-section" data-testid="wb-settings-profile">
                <div className="wb-settings-profile">
                  <div className="wb-settings-profile__avatar">
                    {user.avatar_url ? <img src={user.avatar_url} alt="头像" /> : '👤'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div className="wb-settings-profile__name">{user.name || '未设置'}</div>
                    <div className="wb-settings-profile__phone">{user.phone}</div>
                    <span className="wb-settings-profile__role">
                      {ROLE_LABELS[user.role] ?? user.role}
                      {user.is_verified ? ' · 已认证' : ''}
                    </span>
                  </div>
                </div>
                <div className="wb-settings-row">
                  <span className="wb-settings-row__label">修改密码</span>
                  <span className="wb-settings-row__value">待开放</span>
                </div>
              </div>

              {/* 主题设置 */}
              <div className="wb-settings-section">
                <div className="wb-settings-section__title">主题设置</div>
                <div className="wb-settings-row">
                  <span className="wb-settings-row__label">显示模式</span>
                  <div className="wb-theme-options">
                    {(['light', 'dark', 'system'] as ThemeMode[]).map((m) => (
                      <button
                        key={m}
                        type="button"
                        className={`wb-theme-option ${theme === m ? 'wb-theme-option--active' : ''}`}
                        aria-pressed={theme === m}
                        onClick={() => changeTheme(m)}
                        data-testid={`wb-theme-option--${m}`}
                      >
                        {m === 'light' ? '浅色' : m === 'dark' ? '深色' : '跟随系统'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* 通知设置 */}
              <div className="wb-settings-section">
                <div className="wb-settings-section__title">通知设置</div>
                <ToggleRow
                  label="订单通知"
                  checked={notifyOrder}
                  onChange={setNotifyOrder}
                  testId="wb-notify-order"
                />
                <ToggleRow
                  label="任务提醒"
                  checked={notifyTask}
                  onChange={setNotifyTask}
                  testId="wb-notify-task"
                />
                <ToggleRow
                  label="质检预警"
                  checked={notifyQuality}
                  onChange={setNotifyQuality}
                  testId="wb-notify-quality"
                />
              </div>

              {/* 其他 */}
              <div className="wb-settings-section">
                <div className="wb-settings-section__title">其他</div>
                <div className="wb-settings-row">
                  <span className="wb-settings-row__label">版本</span>
                  <span className="wb-settings-row__value">v1.8.0 · Web 控制台</span>
                </div>
              </div>

              <button
                className="wb-logout-btn"
                onClick={handleLogout}
                type="button"
                data-testid="wb-logout"
              >
                退出登录
              </button>
            </>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
  testId,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  testId: string;
}) {
  return (
    <div className="wb-settings-row">
      <span className="wb-settings-row__label">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        data-testid={testId}
        style={{
          width: 40,
          height: 22,
          borderRadius: 11,
          border: 'none',
          background: checked ? 'var(--accent)' : 'var(--surface3)',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background 0.2s',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: checked ? 20 : 2,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: 'var(--surface0)',
            transition: 'left 0.2s',
          }}
        />
      </button>
    </div>
  );
}
