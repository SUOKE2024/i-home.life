/**
 * MepPage — 水电暖通点位标准
 *
 * 结构：Scaffold > AppBar(水电暖通) > 房型 tab + 点位标准展示
 * API：GET /api/mep/room-standards/{room_type}
 *      （对齐 app/api/mep.py:54，返回 ROOM_MEP_STANDARDS[room_type]）
 *
 * 后端字段（app/services/mep_service.py:ROOM_MEP_STANDARDS）：
 *   name / switches / sockets / lights / network / tv / ac / details[]
 *   details: [{name, height, count, type}]
 *
 * 7 种房型：living_room/bedroom/kitchen/bathroom/dining/study/balcony
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { MepRoomStandard } from '../types/domain';

const ROOM_TYPES: Array<{ key: string; label: string; emoji: string }> = [
  { key: 'living_room', label: '客厅', emoji: '🛋' },
  { key: 'bedroom', label: '卧室', emoji: '🛏' },
  { key: 'kitchen', label: '厨房', emoji: '🍳' },
  { key: 'bathroom', label: '卫生间', emoji: '🚿' },
  { key: 'dining', label: '餐厅', emoji: '🍽' },
  { key: 'study', label: '书房', emoji: '📚' },
  { key: 'balcony', label: '阳台', emoji: '🌿' },
];

const POINT_TYPE_LABELS: Record<string, string> = {
  socket: '插座', ac_socket: '空调插座', floor_socket: '地插',
  switch: '开关', network: '网络面板', tv: '电视面板',
};

export default function MepPage() {
  const navigate = useNavigate();
  const [activeRoom, setActiveRoom] = useState<string>('living_room');

  const { data: standard, loading, error, reload } = useAsync<MepRoomStandard | null>(
    async () => {
      const r = await apiClient.getMepRoomStandard<MepRoomStandard>(activeRoom);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [activeRoom],
  );

  const stats = standard
    ? [
        { label: '开关', value: standard.switches, emoji: '🔘' },
        { label: '插座', value: standard.sockets, emoji: '🔌' },
        { label: '灯具', value: standard.lights, emoji: '💡' },
        { label: '网络', value: standard.network, emoji: '🌐' },
        ...(standard.tv != null ? [{ label: '电视', value: standard.tv, emoji: '📺' }] : []),
        { label: '空调', value: standard.ac, emoji: '❄' },
      ]
    : [];

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-mep-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">⚡ 水电暖通</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 房型 tab */}
          <div className="wb-task-filter" role="tablist" aria-label="房型选择" data-testid="wb-mep-tabs">
            {ROOM_TYPES.map((r) => (
              <button
                key={r.key}
                type="button"
                role="tab"
                aria-selected={activeRoom === r.key}
                className={`wb-task-filter__chip ${activeRoom === r.key ? 'wb-task-filter__chip--active' : ''}`}
                onClick={() => setActiveRoom(r.key)}
                data-testid={`wb-mep-tab--${r.key}`}
              >
                {r.emoji} {r.label}
              </button>
            ))}
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-mep-loading">
              <div className="wb-state__icon">⏳</div><div>加载点位标准中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-mep-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {!loading && !error && standard && (
            <div data-testid="wb-mep-content">
              <div className="wb-section-label">{standard.name} · 点位配置标准</div>

              {/* 统计网格 */}
              <div className="wb-takeoff-grid" data-testid="wb-mep-stats">
                {stats.map((s) => (
                  <div key={s.label} className="wb-takeoff-stat">
                    <div className="wb-takeoff-stat__value">{s.emoji} {s.value}</div>
                    <div className="wb-takeoff-stat__label">{s.label}</div>
                  </div>
                ))}
              </div>

              {/* 详细点位列表 */}
              {standard.details && standard.details.length > 0 && (
                <>
                  <div className="wb-section-label">详细点位（{standard.details.length}）</div>
                  {standard.details.map((d, i) => (
                    <div key={i} className="wb-project-card" data-testid={`wb-mep-detail--${i}`}>
                      <div className="wb-project-card__title">{d.name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📦 {POINT_TYPE_LABELS[d.type] ?? d.type}</span>
                        <span className="wb-project-card__meta-item">🔢 ×{d.count}</span>
                        <span className="wb-project-card__meta-item">📏 {d.height === 0 ? '地插' : `H${d.height}mm`}</span>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
