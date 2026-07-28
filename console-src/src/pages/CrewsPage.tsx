/**
 * CrewsPage — 工程队
 *
 * 结构：Scaffold > AppBar(工程队) > [项目选择器] > 视图切换（工程队列表/项目匹配）+ 卡片
 * API：
 *   GET /api/crews（对齐 app/api/crews.py:list_crews，全局工程队列表）
 *   GET /api/crews/matches/{projectId}（对齐 app/api/crews.py:project_matches）
 *
 * 后端字段（app/schemas/construction_crew.py）：
 *   ConstructionCrewResponse: id / name / leader / phone / city / district /
 *     qualification / specialties[] / rating / completed_projects / avg_duration /
 *     daily_rate / status / introduction / created_at / updated_at
 *   CrewMatchResponse: id / project_id / crew_id / match_score / score_breakdown /
 *     recommendation / status / crew(嵌套) / created_at / updated_at
 *
 * 工程队列表为全局数据（无项目维度）；匹配结果需项目维度。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ConstructionCrew, CrewMatch, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';
type View = 'list' | 'matches';

const CREW_STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  available: { label: '空闲', tone: 'success' },
  busy: { label: '施工中', tone: 'warning' },
  offline: { label: '离线', tone: 'muted' },
};

function matchScoreTone(score: number): ChipTone {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'muted';
}

function matchScoreClass(score: number): string {
  if (score >= 80) return 'high';
  if (score >= 60) return 'mid';
  return 'low';
}

export default function CrewsPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<View>('list');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 工程队列表（全局）
  const { data: crews, loading: crewsLoading, error: crewsError, reload: crewsReload } =
    useAsync<ConstructionCrew[] | null>(
      async () => {
        const r = await apiClient.getCrews<ConstructionCrew[]>();
        if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
        return r.data;
      },
      [],
    );

  // 项目匹配结果
  const {
    data: matches,
    loading: matchesLoading,
    error: matchesError,
    reload: matchesReload,
  } = useAsync<CrewMatch[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getCrewMatches<CrewMatch[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const loading = view === 'list' ? crewsLoading : matchesLoading;
  const error = view === 'list' ? crewsError : matchesError;
  const reload = view === 'list' ? crewsReload : matchesReload;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-crews-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">👷 工程队</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 视图切换 */}
          <div className="wb-task-filter" role="tablist" aria-label="视图切换">
            <button
              type="button"
              role="tab"
              aria-selected={view === 'list'}
              className={`wb-task-filter__chip ${view === 'list' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('list')}
              data-testid="wb-crews-view--list"
            >
              📋 全部工程队
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'matches'}
              className={`wb-task-filter__chip ${view === 'matches' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('matches')}
              data-testid="wb-crews-view--matches"
            >
              🎯 项目匹配
            </button>
          </div>

          {/* 项目选择器（仅匹配视图）*/}
          {view === 'matches' && (
            <div className="wb-project-picker">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                aria-label="选择项目"
                data-testid="wb-crews-project-select"
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

          {view === 'matches' && !selectedProjectId && (
            <div className="wb-state" data-testid="wb-crews-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {((view === 'list') || (view === 'matches' && selectedProjectId)) && loading && (
            <div className="wb-state" data-testid="wb-crews-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载中…</div>
            </div>
          )}

          {((view === 'list') || (view === 'matches' && selectedProjectId)) &&
            error &&
            !loading && (
              <div className="wb-state wb-state--error" data-testid="wb-crews-error">
                <div className="wb-state__icon">⚠</div>
                <div>{error}</div>
                <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                  重试
                </button>
              </div>
            )}

          {/* 工程队列表视图 */}
          {view === 'list' && !loading && !error && (crews?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-crews-empty">
              <div className="wb-state__icon">👷</div>
              <div>暂无工程队数据</div>
            </div>
          )}

          {view === 'list' && !loading && !error && (crews?.length ?? 0) > 0 && (
            <div data-testid="wb-crews-content">
              <div className="wb-section-label">工程队（{crews!.length}）</div>
              {crews!.map((crew, i) => {
                const statusInfo = CREW_STATUS_MAP[crew.status] ?? {
                  label: crew.status,
                  tone: 'muted' as ChipTone,
                };
                return (
                  <div
                    key={crew.id}
                    className="wb-crew-card"
                    data-testid={`wb-crews-item--${i}`}
                  >
                    <div className="wb-crew-card__head">
                      <div className="wb-crew-card__name">{crew.name}</div>
                      <span
                        className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                        data-testid={`wb-crews-status--${i}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="wb-crew-card__meta">
                      <span>👤 {crew.leader}</span>
                      <span className="wb-crew-card__rating">⭐ {crew.rating.toFixed(1)}</span>
                      <span>🏆 {crew.completed_projects} 个完工</span>
                      <span>📅 平均 {crew.avg_duration} 天</span>
                      <span>💰 ¥{crew.daily_rate}/天</span>
                      {crew.city && <span>📍 {crew.city}</span>}
                      <span>资质 {crew.qualification}</span>
                    </div>
                    {crew.specialties && crew.specialties.length > 0 && (
                      <div className="wb-crew-card__tags">
                        {crew.specialties.map((s, si) => (
                          <span className="wb-crew-tag" key={si}>
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {crew.introduction && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--text-muted)',
                          marginTop: 8,
                        }}
                      >
                        {crew.introduction}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 匹配结果视图 */}
          {view === 'matches' && selectedProjectId && !loading && !error && (matches?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-crews-matches-empty">
              <div className="wb-state__icon">🎯</div>
              <div>暂无匹配结果</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与施工 Agent 对话发起工程队匹配
              </div>
            </div>
          )}

          {view === 'matches' &&
            selectedProjectId &&
            !loading &&
            !error &&
            (matches?.length ?? 0) > 0 && (
              <div data-testid="wb-crews-matches-content">
                <div className="wb-section-label">匹配结果（{matches!.length}）</div>
                {matches!.map((match, i) => {
                  const crew = match.crew;
                  const tone = matchScoreTone(match.match_score);
                  const scoreClass = matchScoreClass(match.match_score);
                  return (
                    <div
                      key={match.id}
                      className="wb-crew-card"
                      data-testid={`wb-crews-match--${i}`}
                    >
                      <div className="wb-crew-card__head">
                        <div className="wb-crew-card__name">
                          {crew?.name ?? `工程队 #${match.crew_id.slice(0, 6)}`}
                        </div>
                        <span
                          className={`wb-crew-match-score wb-crew-match-score--${scoreClass}`}
                          data-testid={`wb-crews-match-score--${i}`}
                        >
                          匹配度 {match.match_score.toFixed(0)}
                        </span>
                      </div>
                      {crew && (
                        <div className="wb-crew-card__meta">
                          <span>👤 {crew.leader}</span>
                          <span className="wb-crew-card__rating">
                            ⭐ {crew.rating.toFixed(1)}
                          </span>
                          <span>💰 ¥{crew.daily_rate}/天</span>
                          <span>📅 {crew.avg_duration} 天</span>
                          {crew.city && <span>📍 {crew.city}</span>}
                        </div>
                      )}
                      {match.recommendation && (
                        <div
                          style={{
                            fontSize: 'var(--font-size-sm)',
                            color: `var(--${tone === 'success' ? 'success' : tone === 'warning' ? 'warning' : 'text-secondary'})`,
                            marginTop: 6,
                          }}
                        >
                          💡 {match.recommendation}
                        </div>
                      )}
                      {crew?.specialties && crew.specialties.length > 0 && (
                        <div className="wb-crew-card__tags">
                          {crew.specialties.map((s, si) => (
                            <span className="wb-crew-tag" key={si}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
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
