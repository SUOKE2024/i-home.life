/**
 * AdminPage — 管理后台（v1.13.x 前端缺口补齐 B3）
 *
 * 结构：Scaffold > AppBar(管理后台) > 平台统计 + 用户管理 + 审计日志
 * API（对齐 app/api/admin.py，前缀 /api/admin；非管理员返回 403）：
 *   GET  /api/admin/stats                  平台统计
 *   GET  /api/admin/users                  用户列表（role/is_active 筛选）
 *   PUT  /api/admin/users/{id}/role        修改角色
 *   PUT  /api/admin/users/{id}/status      启用/禁用
 *   GET  /api/admin/audit-logs             审计日志（分页）
 *
 * 诚实降级：非管理员 403 时错误文案真实展示，不伪造数据。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { AuditLogPage, PlatformStats, User } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const ROLE_LABELS: Record<string, string> = {
  homeowner: '业主',
  designer: '设计师',
  contractor: '施工方',
  supplier: '供应商',
  admin: '管理员',
};

const ROLE_TONE: Record<string, ChipTone> = {
  homeowner: 'muted',
  designer: 'info',
  contractor: 'warning',
  supplier: 'success',
  admin: 'danger',
};

const ROLE_OPTIONS = ['homeowner', 'designer', 'contractor', 'supplier', 'admin'];

function fmtDate(v: string | null | undefined): string {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN', { hour12: false });
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [roleFilter, setRoleFilter] = useState('');
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: stats } = useAsync<PlatformStats | null>(async () => {
    const r = await apiClient.getPlatformStats<PlatformStats>();
    return r.isSuccess && r.data ? r.data : null;
  }, []);

  const { data: users, loading, error, reload } = useAsync<User[]>(async () => {
    const r = await apiClient.listUsers<User[]>({ role: roleFilter || undefined, limit: 100 });
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [roleFilter]);

  const { data: auditLogs } = useAsync<AuditLogPage | null>(async () => {
    const r = await apiClient.listAuditLogs<AuditLogPage>({ limit: 50 });
    return r.isSuccess && r.data ? r.data : null;
  }, []);

  async function runAction(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  function handleRoleChange(u: User, role: string) {
    if (!role || role === u.role) return;
    setActionId(u.id);
    runAction(async () => {
      const r = await apiClient.updateUserRole(u.id, { role });
      if (!r.isSuccess) throw new Error(r.error ?? '修改角色失败');
    });
  }

  function handleToggleActive(u: User) {
    setActionId(u.id);
    runAction(async () => {
      const r = await apiClient.updateUserStatus(u.id, { is_active: !u.is_active });
      if (!r.isSuccess) throw new Error(r.error ?? '修改状态失败');
    });
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-admin-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🛠 管理后台</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {actionError && (
            <div className="wb-alert" data-testid="wb-admin-action-error">⚠ {actionError}</div>
          )}

          {/* 平台统计 */}
          <div className="wb-grid wb-grid--2" data-testid="wb-admin-stats">
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">用户总数</div>
              <div className="wb-stat-card__value">{stats?.total_users ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">本周新增</div>
              <div className="wb-stat-card__value">{stats?.weekly_new_users ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">项目总数</div>
              <div className="wb-stat-card__value">{stats?.total_projects ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">进行中项目</div>
              <div className="wb-stat-card__value">{stats?.active_projects ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">待审核认证</div>
              <div className="wb-stat-card__value">{stats?.pending_verifications ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">物料数</div>
              <div className="wb-stat-card__value">{stats?.total_materials ?? '—'}</div>
            </div>
            <div className="wb-stat-card">
              <div className="wb-stat-card__label">供应商数</div>
              <div className="wb-stat-card__value">{stats?.total_suppliers ?? '—'}</div>
            </div>
          </div>

          {/* 用户管理 */}
          <div className="wb-card" data-testid="wb-admin-users">
            <div className="wb-card__title">
              用户管理（{users?.length ?? 0}）
              <select
                className="wb-input wb-input--sm"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                aria-label="按角色筛选"
                style={{ marginLeft: 12 }}
              >
                <option value="">全部角色</option>
                {ROLE_OPTIONS.map((r) => (<option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>))}
              </select>
            </div>

            {loading && (
              <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载用户中…</div></div>
            )}
            {error && !loading && (
              <div className="wb-state wb-state--error" data-testid="wb-admin-users-error">
                <div className="wb-state__icon">⚠</div><div>{error}</div>
                <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
              </div>
            )}
            {!loading && !error && users && users.length === 0 && (
              <div className="wb-state"><div className="wb-state__icon">👤</div><div>暂无用户</div></div>
            )}

            {!loading && !error && users && users.length > 0 && (
              <table className="wb-table">
                <thead>
                  <tr>
                    <th>姓名</th><th>手机号</th><th>角色</th><th>状态</th><th>注册时间</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>{u.name}</td>
                      <td>{u.phone}</td>
                      <td>
                        <select
                          className="wb-input wb-input--sm"
                          value={u.role}
                          disabled={actionId === u.id}
                          onChange={(e) => handleRoleChange(u, e.target.value)}
                          aria-label={`修改 ${u.name} 角色`}
                        >
                          {ROLE_OPTIONS.map((r) => (<option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>))}
                        </select>
                        <span className={`wb-status-chip wb-status-chip--${ROLE_TONE[u.role] ?? 'muted'}`} style={{ marginLeft: 6 }}>
                          {ROLE_LABELS[u.role] ?? u.role}
                        </span>
                      </td>
                      <td>
                        <span className={`wb-status-chip wb-status-chip--${u.is_active ? 'success' : 'muted'}`}>
                          {u.is_active ? '启用' : '禁用'}
                        </span>
                      </td>
                      <td>
                        {fmtDate(u.created_at)}
                        <button
                          className="wb-btn wb-btn--sm wb-btn--ghost"
                          style={{ marginLeft: 8 }}
                          disabled={actionId === u.id}
                          onClick={() => handleToggleActive(u)}
                          type="button"
                        >
                          {u.is_active ? '禁用' : '启用'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* 审计日志 */}
          <div className="wb-card" data-testid="wb-admin-audit-logs">
            <div className="wb-card__title">审计日志（{auditLogs?.total ?? 0}）</div>
            {!auditLogs || auditLogs.items.length === 0 ? (
              <div className="wb-state"><div className="wb-state__icon">📜</div><div>暂无审计日志</div></div>
            ) : (
              <table className="wb-table">
                <thead>
                  <tr>
                    <th>时间</th><th>操作</th><th>资源</th><th>操作者</th><th>IP</th><th>详情</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.items.map((log) => (
                    <tr key={log.id}>
                      <td>{fmtDate(log.created_at)}</td>
                      <td>{log.action}</td>
                      <td>{log.resource_type ? `${log.resource_type}${log.resource_id ? `/${log.resource_id}` : ''}` : '—'}</td>
                      <td>{log.user_id ?? '—'}</td>
                      <td>{log.request_ip ?? '—'}</td>
                      <td title={log.details ?? ''}>{(log.details ?? '').slice(0, 40) || '—'}</td>
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
