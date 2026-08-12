/**
 * NotificationsPage — 通知（设备推送令牌管理，v1.13.x 前端缺口补齐 B3）
 *
 * 结构：Scaffold > AppBar(通知) > 注册设备表单 + 设备令牌列表（注销）
 * API（对齐 app/api/notifications.py，前缀 /api/notifications）：
 *   GET    /api/notifications/devices              设备令牌列表
 *   POST   /api/notifications/register-device      注册/更新令牌
 *   DELETE /api/notifications/devices/{device_id}  注销令牌
 *
 * 诚实降级：后端错误文案真实展示（如 platform 非法 422）。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { DeviceToken } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const PLATFORM_META: Record<string, { label: string; tone: ChipTone }> = {
  ios: { label: 'iOS', tone: 'info' },
  android: { label: 'Android', tone: 'success' },
  harmonyos: { label: '鸿蒙', tone: 'warning' },
};

const PLATFORM_OPTIONS = ['ios', 'android', 'harmonyos'];

function fmtDate(v: string | null | undefined): string {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN', { hour12: false });
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const [tokenInput, setTokenInput] = useState('');
  const [platform, setPlatform] = useState('ios');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data: devices, loading, error, reload } = useAsync<DeviceToken[]>(async () => {
    const r = await apiClient.listNotificationDevices<DeviceToken[]>();
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, []);

  async function handleRegister() {
    setFormError(null);
    if (!tokenInput.trim()) {
      setFormError('请输入设备推送令牌');
      return;
    }
    setSubmitting(true);
    try {
      const r = await apiClient.registerNotificationDevice({
        device_token: tokenInput.trim(),
        platform,
      });
      if (!r.isSuccess) throw new Error(r.error ?? '注册失败');
      setTokenInput('');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(d: DeviceToken) {
    setDeleteId(d.id);
    try {
      const r = await apiClient.unregisterNotificationDevice(d.id);
      if (!r.isSuccess) throw new Error(r.error ?? '注销失败');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleteId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-notifications-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🔔 通知</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 注册设备 */}
          <div className="wb-card" data-testid="wb-notifications-register">
            <div className="wb-card__title">注册设备推送令牌</div>
            <div className="wb-actions" data-testid="wb-notifications-register-form">
              <select
                className="wb-input wb-input--sm"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                aria-label="平台"
              >
                {PLATFORM_OPTIONS.map((p) => (<option key={p} value={p}>{PLATFORM_META[p]?.label ?? p}</option>))}
              </select>
              <input
                className="wb-input wb-input--sm"
                style={{ flex: 1, width: 'auto', minWidth: 200 }}
                type="text"
                placeholder="device_token（推送令牌）"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                aria-label="设备令牌"
              />
              <button
                className="wb-btn wb-btn--sm"
                disabled={submitting}
                onClick={handleRegister}
                type="button"
              >{submitting ? '注册中…' : '注册'}</button>
            </div>
            {formError && (
              <div className="wb-alert" data-testid="wb-notifications-form-error">⚠ {formError}</div>
            )}
          </div>

          {/* 设备列表 */}
          <div className="wb-card" data-testid="wb-notifications-list">
            <div className="wb-card__title">已注册设备（{devices?.length ?? 0}）</div>
            {loading && (
              <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载设备中…</div></div>
            )}
            {error && !loading && (
              <div className="wb-state wb-state--error" data-testid="wb-notifications-error">
                <div className="wb-state__icon">⚠</div><div>{error}</div>
                <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
              </div>
            )}
            {!loading && !error && devices && devices.length === 0 && (
              <div className="wb-state"><div className="wb-state__icon">📱</div><div>暂无注册设备</div></div>
            )}
            {!loading && !error && devices && devices.length > 0 && (
              <table className="wb-table">
                <thead>
                  <tr><th>平台</th><th>令牌</th><th>状态</th><th>更新时间</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {devices.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <span className={`wb-status-chip wb-status-chip--${PLATFORM_META[d.platform]?.tone ?? 'muted'}`}>
                          {PLATFORM_META[d.platform]?.label ?? d.platform}
                        </span>
                      </td>
                      <td title={d.device_token}>{(d.device_token ?? '').slice(0, 24)}{(d.device_token ?? '').length > 24 ? '…' : ''}</td>
                      <td>
                        <span className={`wb-status-chip wb-status-chip--${d.is_active ? 'success' : 'muted'}`}>
                          {d.is_active ? '活跃' : '已注销'}
                        </span>
                      </td>
                      <td>{fmtDate(d.updated_at)}</td>
                      <td>
                        {d.is_active && (
                          <button
                            className="wb-btn wb-btn--sm wb-btn--ghost"
                            disabled={deleteId === d.id}
                            onClick={() => handleDelete(d)}
                            type="button"
                          >{deleteId === d.id ? '处理中…' : '注销'}</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </SuokeLayout>
  );
}
