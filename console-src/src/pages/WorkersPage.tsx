/**
 * WorkersPage — F35 服务商匹配（对齐 flutter_app/lib/pages/worker_page.dart）
 *
 * 结构：Scaffold > AppBar(服务商匹配) > 视图切换（服务商/匹配记录/智能匹配）
 * API（app/api/workers.py）：
 *   GET  /api/workers（列表，支持 role 过滤）
 *   POST /api/workers/match（智能匹配，六维评分）
 *   GET  /api/workers/matches/{projectId}（项目匹配记录）
 *   PATCH /api/workers/matches/{matchId}/status?status=（更新状态）
 *
 * 服务商角色：designer 设计师 / supervisor 监理 / estimator 预算师 /
 *   carpenter 木工 / plumber_electrician 水电安装工 / curtain_installer 窗帘安装工
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, ServiceWorker, WorkerMatch } from '../types/domain';

type View = 'workers' | 'matches' | 'smart';

const ROLE_LABELS: Record<string, string> = {
  designer: '设计师',
  supervisor: '监理',
  estimator: '预算师',
  carpenter: '木工',
  plumber_electrician: '水电安装工',
  curtain_installer: '窗帘安装工',
};

const ROLE_KEYS = Object.keys(ROLE_LABELS);

const MATCH_STATUS_CN: Record<string, string> = {
  pending: '待处理',
  shortlisted: '已入围',
  hired: '已录用',
  rejected: '已拒绝',
};

const DIMENSION_CN: Record<string, string> = {
  style: '风格',
  experience: '经验',
  rating: '评分',
  portfolio: '案例',
  price: '价格',
  location: '地域',
  phase: '阶段',
  budget_type: '预算类型',
  skill: '技能',
  specialty: '专业',
  curtain_type: '窗帘类型',
};

function scoreTone(score: number): 'success' | 'warning' | 'muted' {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'muted';
}

export default function WorkersPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<View>('workers');
  const [roleFilter, setRoleFilter] = useState<string>('designer');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [matchRole, setMatchRole] = useState<string>('designer');
  const [matching, setMatching] = useState(false);
  const [matchMsg, setMatchMsg] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 服务商列表（依赖角色筛选）
  const {
    data: workers,
    loading: workersLoading,
    error: workersError,
    reload: workersReload,
  } = useAsync<ServiceWorker[] | null>(
    async () => {
      const r = await apiClient.listWorkers<ServiceWorker[]>(roleFilter);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [roleFilter],
  );

  // 匹配记录（依赖项目）
  const {
    data: matches,
    loading: matchesLoading,
    error: matchesError,
    reload: matchesReload,
  } = useAsync<WorkerMatch[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getWorkerMatches<WorkerMatch[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const startMatch = async () => {
    if (!selectedProjectId) return;
    setMatching(true);
    setMatchMsg(null);
    try {
      const r = await apiClient.matchWorkers<WorkerMatch[]>({
        project_id: selectedProjectId,
        role: matchRole,
      });
      if (!r.isSuccess) {
        setMatchMsg(`匹配失败：${r.error ?? '未知错误'}`);
      } else {
        setMatchMsg(
          `✅ 已生成 ${(r.data ?? []).length} 位${ROLE_LABELS[matchRole] ?? matchRole}匹配结果`,
        );
        await matchesReload();
        setView('matches');
      }
    } finally {
      setMatching(false);
    }
  };

  const updateStatus = async (matchId: string, status: 'shortlisted' | 'hired' | 'rejected') => {
    const r = await apiClient.updateWorkerMatchStatus<WorkerMatch>(matchId, status);
    if (r.isSuccess) {
      await matchesReload();
    }
  };

  const loading = view === 'workers' ? workersLoading : matchesLoading;
  const error = view === 'workers' ? workersError : matchesError;
  const reload = view === 'workers' ? workersReload : matchesReload;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-workers-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🧑‍🔧 服务商匹配</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 视图切换 */}
          <div className="wb-task-filter" role="tablist" aria-label="视图切换">
            <button
              type="button"
              role="tab"
              aria-selected={view === 'workers'}
              className={`wb-task-filter__chip ${view === 'workers' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('workers')}
              data-testid="wb-workers-view--list"
            >
              📋 服务商
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'matches'}
              className={`wb-task-filter__chip ${view === 'matches' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('matches')}
              data-testid="wb-workers-view--matches"
            >
              🎯 匹配记录
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'smart'}
              className={`wb-task-filter__chip ${view === 'smart' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('smart')}
              data-testid="wb-workers-view--smart"
            >
              ⚡ 智能匹配
            </button>
          </div>

          {/* 服务商视图：角色筛选 */}
          {view === 'workers' && (
            <div className="wb-task-filter" style={{ marginTop: 0 }}>
              {ROLE_KEYS.map((role) => (
                <button
                  key={role}
                  type="button"
                  className={`wb-task-filter__chip ${roleFilter === role ? 'wb-task-filter__chip--active' : ''}`}
                  onClick={() => setRoleFilter(role)}
                  data-testid={`wb-workers-role--${role}`}
                >
                  {ROLE_LABELS[role]}
                </button>
              ))}
            </div>
          )}

          {/* 项目选择器（匹配记录/智能匹配视图）*/}
          {view !== 'workers' && (
            <div className="wb-project-picker">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                aria-label="选择项目"
                data-testid="wb-workers-project-select"
              >
                <option value="">选择项目…</option>
                {projects?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {view !== 'workers' && !selectedProjectId && (
            <div className="wb-state" data-testid="wb-workers-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {/* 智能匹配面板 */}
          {view === 'smart' && selectedProjectId && (
            <div className="wb-vent-box" style={{ marginBottom: 16 }} data-testid="wb-workers-smart">
              <div className="wb-vent-box__head">
                <div className="wb-vent-box__title">发起智能匹配</div>
              </div>
              <div className="wb-project-picker" style={{ marginBottom: 10 }}>
                <select
                  value={matchRole}
                  onChange={(e) => setMatchRole(e.target.value)}
                  aria-label="匹配角色"
                  data-testid="wb-workers-match-role"
                >
                  {ROLE_KEYS.map((role) => (
                    <option key={role} value={role}>
                      {ROLE_LABELS[role]}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                className="wb-theme-option wb-theme-option--active"
                onClick={startMatch}
                disabled={matching}
                data-testid="wb-workers-match-start"
              >
                {matching ? '匹配中…' : '⚡ 开始匹配'}
              </button>
              {matchMsg && (
                <div
                  style={{
                    marginTop: 10,
                    fontSize: 'var(--font-size-sm)',
                    color: matchMsg.startsWith('✅') ? 'var(--success)' : 'var(--danger)',
                  }}
                >
                  {matchMsg}
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="wb-state" data-testid="wb-workers-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-workers-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {/* 服务商列表 */}
          {view === 'workers' && !loading && !error && (workers?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-workers-empty">
              <div className="wb-state__icon">🧑‍🔧</div>
              <div>暂无{ROLE_LABELS[roleFilter]}服务商</div>
            </div>
          )}
          {view === 'workers' &&
            !loading &&
            !error &&
            (workers?.length ?? 0) > 0 &&
            workers!.map((w, i) => (
              <div key={w.id} className="wb-crew-card" data-testid={`wb-workers-item--${i}`}>
                <div className="wb-crew-card__head">
                  <div className="wb-crew-card__name">
                    {w.name}
                    <span className="wb-crew-tag" style={{ marginLeft: 8 }}>
                      {ROLE_LABELS[w.role] ?? w.role}
                    </span>
                  </div>
                  <span className="wb-crew-card__rating">⭐ {w.rating.toFixed(1)}</span>
                </div>
                <div className="wb-crew-card__meta">
                  <span>🏆 {w.completed_projects} 个完工</span>
                  <span>📅 {w.years_of_experience} 年经验</span>
                  <span>💰 ¥{w.daily_rate}/天{w.hourly_rate ? ` · ¥${w.hourly_rate}/时` : ''}</span>
                  {w.city && <span>📍 {w.city}{w.district ? ` ${w.district}` : ''}</span>}
                  <span>资质 {w.qualification}</span>
                  <span className="wb-status-chip wb-status-chip--muted">{w.status}</span>
                </div>
                {w.introduction && (
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }}>
                    {w.introduction}
                  </div>
                )}
                {w.certifications && w.certifications.length > 0 && (
                  <div className="wb-crew-card__tags">
                    {w.certifications.map((c, ci) => (
                      <span className="wb-crew-tag" key={ci}>
                        🏅 {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}

          {/* 匹配记录 */}
          {view === 'matches' && selectedProjectId && !loading && !error && (matches?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-workers-matches-empty">
              <div className="wb-state__icon">🎯</div>
              <div>暂无匹配记录</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>切换到「智能匹配」发起六维评分匹配</div>
            </div>
          )}
          {view === 'matches' &&
            selectedProjectId &&
            !loading &&
            !error &&
            (matches?.length ?? 0) > 0 &&
            matches!.map((m, i) => {
              const tone = scoreTone(m.match_score);
              return (
                <div key={m.id} className="wb-crew-card" data-testid={`wb-workers-match--${i}`}>
                  <div className="wb-crew-card__head">
                    <div className="wb-crew-card__name">
                      {m.worker?.name ?? `服务商 #${m.worker_id.slice(0, 6)}`}
                      <span className="wb-crew-tag" style={{ marginLeft: 8 }}>
                        {ROLE_LABELS[m.role] ?? m.role}
                      </span>
                    </div>
                    <span className={`wb-status-chip wb-status-chip--${tone}`}>
                      匹配度 {m.match_score.toFixed(0)}
                    </span>
                  </div>
                  {m.worker && (
                    <div className="wb-crew-card__meta">
                      <span className="wb-crew-card__rating">⭐ {m.worker.rating.toFixed(1)}</span>
                      <span>🏆 {m.worker.completed_projects} 个完工</span>
                      <span>📅 {m.worker.years_of_experience} 年经验</span>
                      <span>💰 ¥{m.worker.daily_rate}/天</span>
                      {m.worker.city && <span>📍 {m.worker.city}</span>}
                    </div>
                  )}
                  {/* 六维评分明细 */}
                  {m.score_breakdown && Object.keys(m.score_breakdown).length > 0 && (
                    <div className="wb-crew-card__tags" data-testid={`wb-workers-score--${i}`}>
                      {Object.entries(m.score_breakdown).map(([dim, score]) => (
                        <span className="wb-crew-tag" key={dim}>
                          {DIMENSION_CN[dim] ?? dim} {Math.round(score)}分
                        </span>
                      ))}
                    </div>
                  )}
                  {m.recommendation && (
                    <div
                      style={{
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--text-secondary)',
                        marginTop: 6,
                      }}
                    >
                      💡 {m.recommendation}
                    </div>
                  )}
                  {/* 状态 + 操作 */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      marginTop: 10,
                      borderTop: '1px dashed var(--border)',
                      paddingTop: 10,
                    }}
                  >
                    <span className={`wb-status-chip wb-status-chip--${tone}`}>
                      {MATCH_STATUS_CN[m.status] ?? m.status}
                    </span>
                    {['shortlisted', 'hired', 'rejected'].map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="wb-task-filter__chip"
                        onClick={() =>
                          updateStatus(m.id, s as 'shortlisted' | 'hired' | 'rejected')
                        }
                        data-testid={`wb-workers-match-status--${s}`}
                      >
                        {s === 'shortlisted' ? '入围' : s === 'hired' ? '录用' : '拒绝'}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </SuokeLayout>
  );
}
