/**
 * SmartHomePage — 智能家居方案
 *
 * 结构：Scaffold > AppBar(智能家居) > [项目选择器] > 状态筛选 + 方案卡片列表
 * API：GET /api/smart-home/schemes/project/{projectId}（对齐 app/api/smart_home.py）
 *
 * 后端字段（app/schemas/smart_home.py:SmartHomeSchemeResponse）：
 *   id / project_id / room_name / room_type / protocol / hub_brand /
 *   device_count / total_price / status / notes / created_at / updated_at
 *
 * 后端状态（app/models/smart_home.py）：draft | planned | installing | completed
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { SmartHomeScheme, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  draft: { label: '草稿', tone: 'muted' },
  planned: { label: '已规划', tone: 'info' },
  installing: { label: '安装中', tone: 'warning' },
  completed: { label: '已完成', tone: 'success' },
};

const PROTOCOL_MAP: Record<string, string> = {
  zigbee: 'Zigbee',
  zwave: 'Z-Wave',
  wifi: 'Wi-Fi',
  bluetooth: '蓝牙',
  matter: 'Matter',
  thread: 'Thread',
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'planned', label: '已规划' },
  { key: 'installing', label: '安装中' },
  { key: 'completed', label: '已完成' },
];

export default function SmartHomePage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: schemes, loading, error, reload } = useAsync<SmartHomeScheme[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getSmartHomeSchemes<SmartHomeScheme[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredSchemes = useMemo(() => {
    if (!schemes) return [];
    if (filterStatus === 'all') return schemes;
    return schemes.filter((s) => s.status === filterStatus);
  }, [schemes, filterStatus]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (schemes ?? []).forEach((s) => {
      counts[s.status] = (counts[s.status] ?? 0) + 1;
    });
    return counts;
  }, [schemes]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-smarthome-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🏠 智能家居</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-smarthome-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-smarthome-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-smarthome-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载方案中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-smarthome-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-smarthome-empty">
              <div className="wb-state__icon">🏠</div>
              <div>暂无智能家居方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与智能家居 Agent 对话生成方案
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) > 0 && (
            <div data-testid="wb-smarthome-content">
              <div className="wb-task-filter" role="tablist" aria-label="状态筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? schemes!.length : statusCounts[f.key] ?? 0;
                  return (
                    <button
                      key={f.key}
                      type="button"
                      role="tab"
                      aria-selected={filterStatus === f.key}
                      className={`wb-task-filter__chip ${
                        filterStatus === f.key ? 'wb-task-filter__chip--active' : ''
                      }`}
                      onClick={() => setFilterStatus(f.key)}
                      data-testid={`wb-smarthome-filter--${f.key}`}
                    >
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">
                方案（{filteredSchemes.length}/{schemes!.length}）
              </div>

              {filteredSchemes.map((scheme, i) => {
                const statusInfo = STATUS_MAP[scheme.status] ?? {
                  label: scheme.status,
                  tone: 'muted' as ChipTone,
                };
                return (
                  <div
                    key={scheme.id}
                    className="wb-smart-card"
                    data-testid={`wb-smarthome-item--${i}`}
                  >
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">
                        {scheme.room_name}
                        <span
                          style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--text-muted)',
                            fontWeight: 400,
                            marginLeft: 6,
                          }}
                        >
                          {scheme.room_type}
                        </span>
                      </div>
                      <span
                        className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                        data-testid={`wb-smarthome-status--${i}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📡 {PROTOCOL_MAP[scheme.protocol] ?? scheme.protocol}</span>
                      <span>🎛 {scheme.hub_brand}</span>
                      <span>🔌 {scheme.device_count} 设备</span>
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginTop: 8,
                      }}
                    >
                      <span className="wb-smart-card__price">
                        ¥{scheme.total_price.toLocaleString()}
                      </span>
                      {scheme.notes && (
                        <span
                          style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--text-muted)',
                            maxWidth: '60%',
                            textAlign: 'right',
                          }}
                        >
                          {scheme.notes}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
