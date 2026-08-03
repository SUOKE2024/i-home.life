/**
 * DesignPage — 设计（AI 方案生成 + 动线分析）
 *
 * 结构：Scaffold > AppBar(设计) > 双视图 tab
 *   ① 设计方案：表单（需求 + 房间信息）→ POST /api/agents/design → 4 字段卡片
 *   ② 动线分析：房间布局编辑器 → POST /api/agents/design/circulation → 三动线评分
 *
 * 后端两端点均为纯算法、确定性（无 LLM），适合真实后端 E2E：
 *   - app/api/agents.py:1268 request_design → DesignerAgent.generate_layouts
 *   - app/api/agents.py:1292 analyze_circulation → DesignerAgent.analyze_circulation
 *
 * 前端动线评分展示镜像后端 analyze_circulation 返回结构（circulations[]/overall_score/rating）。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { apiClient } from '../services/api-client';
import type {
  DesignPlanResult,
  CirculationRoom,
  CirculationAnalysisResult,
  DesignProposalSpec,
  DesignProposalResult,
  DesignProposalReviseResult,
} from '../types/domain';

type View = 'plan' | 'circulation' | 'proposals';

// 房间类型选项（对齐后端 CIRCULATION_TYPES.preferred_path 用到的 type）
const ROOM_TYPES: Array<{ value: string; label: string }> = [
  { value: 'entryway', label: '玄关' },
  { value: 'living_room', label: '客厅' },
  { value: 'dining_room', label: '餐厅' },
  { value: 'kitchen', label: '厨房' },
  { value: 'bedroom', label: '卧室' },
  { value: 'bathroom', label: '卫生间' },
  { value: 'balcony', label: '阳台' },
  { value: 'cloakroom', label: '衣帽间' },
  { value: 'study', label: '书房' },
];

// 典型两居室布局预设（坐标单位：米，左下原点）
const PRESET_ROOMS: CirculationRoom[] = [
  { name: '玄关', type: 'entryway', x: 0, y: 4, w: 1.5, h: 2 },
  { name: '客厅', type: 'living_room', x: 1.5, y: 3, w: 5, h: 4 },
  { name: '餐厅', type: 'dining_room', x: 1.5, y: 1, w: 3, h: 2 },
  { name: '厨房', type: 'kitchen', x: 0, y: 1, w: 1.5, h: 3 },
  { name: '主卧', type: 'bedroom', x: 6.5, y: 4, w: 4, h: 3 },
  { name: '次卧', type: 'bedroom', x: 6.5, y: 1, w: 3.5, h: 3 },
  { name: '主卫', type: 'bathroom', x: 9, y: 4, w: 1.5, h: 2 },
  { name: '阳台', type: 'balcony', x: 4.5, y: 0, w: 5.5, h: 1 },
];

const RATING_LABEL: Record<string, string> = {
  excellent: '优秀',
  good: '良好',
  fair: '一般',
  poor: '需优化',
};

const RATING_CLASS: Record<string, string> = {
  excellent: 'wb-design-rating--excellent',
  good: 'wb-design-rating--good',
  fair: 'wb-design-rating--fair',
  poor: 'wb-design-rating--poor',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '提示',
};

function emptyRoom(): CirculationRoom {
  return { name: '', type: 'living_room', x: 0, y: 0, w: 3, h: 3 };
}

export default function DesignPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<View>('plan');

  // ── 设计方案生成状态 ──
  const [message, setMessage] = useState('');
  const [roomInfo, setRoomInfo] = useState('');
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [plan, setPlan] = useState<DesignPlanResult | null>(null);
  const [showFullReply, setShowFullReply] = useState(false);

  // ── 动线分析状态 ──
  const [rooms, setRooms] = useState<CirculationRoom[]>([emptyRoom()]);
  const [circLoading, setCircLoading] = useState(false);
  const [circError, setCircError] = useState<string | null>(null);
  const [circResult, setCircResult] = useState<CirculationAnalysisResult | null>(null);

  // ── 讨论式方案交互状态（POST /design/proposals + revise）──
  const [proposalReq, setProposalReq] = useState('');
  const [proposals, setProposals] = useState<DesignProposalSpec[] | null>(null);
  const [proposalSessionId, setProposalSessionId] = useState('');
  const [proposalSource, setProposalSource] = useState('');
  const [proposalLoading, setProposalLoading] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [reviseId, setReviseId] = useState('');
  const [reviseChange, setReviseChange] = useState('');
  const [revising, setRevising] = useState(false);

  async function handleGeneratePlan() {
    if (!message.trim()) {
      setPlanError('请输入设计需求');
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    setPlan(null);
    try {
      const r = await apiClient.requestDesign<DesignPlanResult>(message.trim(), roomInfo.trim() || undefined);
      if (!r.isSuccess || !r.data) {
        setPlanError(r.error ?? '生成失败');
        return;
      }
      setPlan(r.data);
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : String(err));
    } finally {
      setPlanLoading(false);
    }
  }

  function updateRoom(idx: number, patch: Partial<CirculationRoom>) {
    setRooms((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function addRoom() {
    setRooms((prev) => [...prev, emptyRoom()]);
  }

  function removeRoom(idx: number) {
    setRooms((prev) => prev.filter((_, i) => i !== idx));
  }

  function loadPreset() {
    setRooms(PRESET_ROOMS.map((r) => ({ ...r })));
    setCircResult(null);
    setCircError(null);
  }

  async function handleAnalyzeCirculation() {
    const valid = rooms.filter((r) => r.name.trim() && r.type);
    if (valid.length === 0) {
      setCircError('请至少添加一个房间（含名称和类型）');
      return;
    }
    setCircLoading(true);
    setCircError(null);
    setCircResult(null);
    try {
      const r = await apiClient.analyzeCirculation<CirculationAnalysisResult>(valid);
      if (!r.isSuccess || !r.data) {
        setCircError(r.error ?? '分析失败');
        return;
      }
      setCircResult(r.data);
    } catch (err) {
      setCircError(err instanceof Error ? err.message : String(err));
    } finally {
      setCircLoading(false);
    }
  }

  async function handleGenerateProposals() {
    if (!proposalReq.trim()) {
      setProposalError('请输入设计需求');
      return;
    }
    setProposalLoading(true);
    setProposalError(null);
    setProposals(null);
    setProposalSource('');
    try {
      const r = await apiClient.generateDesignProposals<DesignProposalResult>(proposalReq.trim());
      if (!r.isSuccess || !r.data) {
        setProposalError(r.error ?? '生成失败');
        return;
      }
      setProposals(r.data.proposals);
      setProposalSessionId(r.data.session_id);
      setProposalSource(r.data.source);
      setReviseChange('');
      if (r.data.proposals.length > 0) setReviseId(r.data.proposals[0].proposal_id);
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : String(err));
    } finally {
      setProposalLoading(false);
    }
  }

  async function handleReviseProposal() {
    if (!reviseId) {
      setProposalError('请先选择一个方案');
      return;
    }
    if (!reviseChange.trim()) {
      setProposalError('请输入修改指令');
      return;
    }
    setRevising(true);
    setProposalError(null);
    try {
      const r = await apiClient.reviseDesignProposal<DesignProposalReviseResult>(
        reviseId,
        reviseChange.trim(),
        proposalSessionId || undefined,
      );
      if (!r.isSuccess || !r.data) {
        setProposalError(r.error ?? '修订失败');
        return;
      }
      const revised = r.data.proposal;
      setProposals((prev) =>
        (prev ?? []).map((p) => (p.proposal_id === revised.proposal_id ? revised : p)),
      );
      setReviseChange('');
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : String(err));
    } finally {
      setRevising(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-design-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📐 设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 视图切换 */}
          <div className="wb-task-filter" role="tablist" aria-label="设计视图切换">
            <button
              type="button"
              role="tab"
              aria-selected={view === 'plan'}
              className={`wb-task-filter__chip ${view === 'plan' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('plan')}
              data-testid="wb-design-view--plan"
            >
              🎨 设计方案生成
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'circulation'}
              className={`wb-task-filter__chip ${view === 'circulation' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('circulation')}
              data-testid="wb-design-view--circulation"
            >
              🚶 动线分析
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'proposals'}
              className={`wb-task-filter__chip ${view === 'proposals' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('proposals')}
              data-testid="wb-design-view--proposals"
            >
              🗣 方案交互
            </button>
          </div>

          {/* ── 视图 1：设计方案生成 ── */}
          {view === 'plan' && (
            <div data-testid="wb-design-plan-content">
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="wb-design-message">
                  设计需求 <span style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <textarea
                  id="wb-design-message"
                  className="wb-textarea"
                  rows={3}
                  placeholder="例：90㎡ 两居室，南北通透，现代简约风，主卧带衣帽间"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  data-testid="wb-design-message"
                />
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="wb-design-roominfo">
                  房间信息（可选）
                </label>
                <input
                  id="wb-design-roominfo"
                  className="wb-input"
                  type="text"
                  placeholder="例：建筑面积 90㎡，层高 2.8m，三室两厅"
                  value={roomInfo}
                  onChange={(e) => setRoomInfo(e.target.value)}
                  data-testid="wb-design-roominfo"
                />
              </div>
              <button
                type="button"
                className="wb-theme-option wb-theme-option--active"
                onClick={handleGeneratePlan}
                disabled={planLoading}
                data-testid="wb-design-generate-btn"
              >
                {planLoading ? '生成中…' : '生成设计方案'}
              </button>

              {planError && (
                <div className="wb-state wb-state--error" data-testid="wb-design-plan-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{planError}</div>
                </div>
              )}

              {plan && !planError && (
                <div data-testid="wb-design-plan-result" style={{ marginTop: 12 }}>
                  <div className="wb-project-card" data-testid="wb-design-card--space">
                    <div className="wb-project-card__title">📐 空间规划</div>
                    <div className="wb-design-card__body">{plan.space_planning || '—'}</div>
                  </div>
                  <div className="wb-project-card" data-testid="wb-design-card--style">
                    <div className="wb-project-card__title">🎨 风格建议</div>
                    <div className="wb-design-card__body">{plan.style_suggestion || '—'}</div>
                  </div>
                  <div className="wb-project-card" data-testid="wb-design-card--circulation">
                    <div className="wb-project-card__title">🚶 动线分析</div>
                    <div className="wb-design-card__body">{plan.circulation_analysis || '—'}</div>
                  </div>
                  <div className="wb-project-card" data-testid="wb-design-card--material">
                    <div className="wb-project-card__title">🧱 材料方案</div>
                    <div className="wb-design-card__body wb-design-card__body--mono">
                      {plan.material_plan || '—'}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="wb-theme-option"
                    onClick={() => setShowFullReply((v) => !v)}
                    style={{ marginTop: 8 }}
                    data-testid="wb-design-toggle-full"
                  >
                    {showFullReply ? '隐藏' : '查看'}完整响应
                  </button>
                  {showFullReply && (
                    <pre className="wb-design-fullreply" data-testid="wb-design-full-reply">
                      {plan.full_reply}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── 视图 2：动线分析 ── */}
          {view === 'circulation' && (
            <div data-testid="wb-design-circ-content">
              <div className="wb-section-label">房间布局（坐标单位：米）</div>
              <div className="wb-design-rooms" data-testid="wb-design-rooms">
                {rooms.map((r, idx) => (
                  <div className="wb-design-room-row" key={idx} data-testid={`wb-design-room--${idx}`}>
                    <input
                      className="wb-input wb-input--name"
                      type="text"
                      placeholder="名称"
                      value={r.name}
                      onChange={(e) => updateRoom(idx, { name: e.target.value })}
                      aria-label={`房间${idx + 1}名称`}
                    />
                    <select
                      className="wb-input wb-input--type"
                      value={r.type}
                      onChange={(e) => updateRoom(idx, { type: e.target.value })}
                      aria-label={`房间${idx + 1}类型`}
                    >
                      {ROOM_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                    <input
                      className="wb-input wb-input--num"
                      type="number"
                      step="0.1"
                      placeholder="x"
                      value={r.x}
                      onChange={(e) => updateRoom(idx, { x: Number(e.target.value) || 0 })}
                      aria-label={`房间${idx + 1} x`}
                    />
                    <input
                      className="wb-input wb-input--num"
                      type="number"
                      step="0.1"
                      placeholder="y"
                      value={r.y}
                      onChange={(e) => updateRoom(idx, { y: Number(e.target.value) || 0 })}
                      aria-label={`房间${idx + 1} y`}
                    />
                    <input
                      className="wb-input wb-input--num"
                      type="number"
                      step="0.1"
                      placeholder="宽"
                      value={r.w}
                      onChange={(e) => updateRoom(idx, { w: Number(e.target.value) || 0 })}
                      aria-label={`房间${idx + 1} 宽`}
                    />
                    <input
                      className="wb-input wb-input--num"
                      type="number"
                      step="0.1"
                      placeholder="高"
                      value={r.h}
                      onChange={(e) => updateRoom(idx, { h: Number(e.target.value) || 0 })}
                      aria-label={`房间${idx + 1} 高`}
                    />
                    <button
                      type="button"
                      className="wb-design-room-del"
                      onClick={() => removeRoom(idx)}
                      aria-label={`删除房间${idx + 1}`}
                      data-testid={`wb-design-room-del--${idx}`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
              <div className="wb-design-actions">
                <button type="button" className="wb-theme-option" onClick={addRoom} data-testid="wb-design-add-room">
                  + 添加房间
                </button>
                <button type="button" className="wb-theme-option" onClick={loadPreset} data-testid="wb-design-preset">
                  📋 加载两居室示例
                </button>
                <button
                  type="button"
                  className="wb-theme-option wb-theme-option--active"
                  onClick={handleAnalyzeCirculation}
                  disabled={circLoading}
                  data-testid="wb-design-analyze-btn"
                >
                  {circLoading ? '分析中…' : '分析动线'}
                </button>
              </div>

              {circError && (
                <div className="wb-state wb-state--error" data-testid="wb-design-circ-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{circError}</div>
                </div>
              )}

              {circResult && !circError && (
                <div data-testid="wb-design-circ-result" style={{ marginTop: 12 }}>
                  {/* 综合评分卡 */}
                  <div className="wb-project-card wb-design-score-card" data-testid="wb-design-score">
                    <div className="wb-project-card__title">综合评分</div>
                    <div className="wb-design-score-row">
                      <span className={`wb-design-rating ${RATING_CLASS[circResult.rating] ?? ''}`}>
                        {circResult.overall_score}
                      </span>
                      <span className="wb-design-rating-text">
                        {circResult.rating_text || RATING_LABEL[circResult.rating] || circResult.rating}
                      </span>
                      <span className="wb-design-meta">
                        {circResult.rooms_count} 房间 · {circResult.total_issues} 问题
                        （{circResult.critical_count} 严重 / {circResult.warning_count} 警告）
                      </span>
                    </div>
                    {circResult.reply && (
                      <div className="wb-design-card__body" style={{ marginTop: 8 }}>
                        {circResult.reply}
                      </div>
                    )}
                  </div>

                  {/* 三动线卡片 */}
                  <div className="wb-section-label" style={{ marginTop: 12 }}>
                    三大动线（{circResult.circulations.length}）
                  </div>
                  {circResult.circulations.map((c, i) => (
                    <div
                      className="wb-project-card"
                      key={c.type}
                      data-testid={`wb-design-circ-item--${i}`}
                    >
                      <div className="wb-project-card__title">
                        {c.name}
                        <span className={`wb-design-circ-score ${RATING_CLASS[
                          c.score >= 85 ? 'excellent' : c.score >= 70 ? 'good' : c.score >= 60 ? 'fair' : 'poor'
                        ] ?? ''}`}>
                          {c.score}
                        </span>
                      </div>
                      <div className="wb-design-card__body">
                        <div className="wb-design-circ-desc">{c.description}</div>
                        <div className="wb-design-circ-meta">
                          路径：{c.path.map((p) => p.name).join(' → ') || '无'} · 总长 {c.total_length}m
                        </div>
                        {c.segments.length > 0 && (
                          <div className="wb-design-segments">
                            {c.segments.map((s, si) => (
                              <span key={si} className="wb-design-segment">
                                {s.from}→{s.to}：{s.distance}m
                              </span>
                            ))}
                          </div>
                        )}
                        {c.crossed_rooms.length > 0 && (
                          <div className="wb-design-warn">⚠ 穿越房间：{c.crossed_rooms.join('、')}</div>
                        )}
                        {c.missing_types.length > 0 && (
                          <div className="wb-design-info">ℹ 缺少：{c.missing_types.join('、')}</div>
                        )}
                        {c.issues.length > 0 && (
                          <ul className="wb-design-issues">
                            {c.issues.map((iss, ii) => (
                              <li key={ii} className={`wb-design-issue wb-design-issue--${iss.severity}`}>
                                <span className="wb-design-issue-sev">
                                  [{SEVERITY_LABEL[iss.severity] ?? iss.severity}]
                                </span>{' '}
                                {iss.detail}
                              </li>
                            ))}
                          </ul>
                        )}
                        {c.suggestions.length > 0 && (
                          <div className="wb-design-suggestions">
                            {c.suggestions.map((s, si) => (
                              <div key={si}>💡 {s}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* 全局优化建议 */}
                  {circResult.suggestions.length > 0 && (
                    <>
                      <div className="wb-section-label" style={{ marginTop: 12 }}>
                        优化建议（{circResult.suggestions.length}）
                      </div>
                      <div className="wb-project-card" data-testid="wb-design-suggestions">
                        {circResult.suggestions.map((s, si) => (
                          <div key={si} className="wb-design-suggestion-item">
                            💡 {s}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── 视图 3：讨论式方案交互 ── */}
          {view === 'proposals' && (
            <div data-testid="wb-design-proposals-content">
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="wb-design-proposal-req">
                  设计需求 <span style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <textarea
                  id="wb-design-proposal-req"
                  className="wb-textarea"
                  rows={3}
                  placeholder="例：帮我设计一个开放式厨房，U 型布局，预算 3 万"
                  value={proposalReq}
                  onChange={(e) => setProposalReq(e.target.value)}
                  data-testid="wb-design-proposal-req"
                />
              </div>
              <button
                type="button"
                className="wb-theme-option wb-theme-option--active"
                onClick={handleGenerateProposals}
                disabled={proposalLoading}
                data-testid="wb-design-proposal-generate-btn"
              >
                {proposalLoading ? '生成中…' : '生成方案'}
              </button>

              {proposalError && (
                <div className="wb-state wb-state--error" data-testid="wb-design-proposal-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{proposalError}</div>
                </div>
              )}

              {proposalSource === 'fallback' && !proposalError && (
                <div className="wb-state" data-testid="wb-design-proposal-fallback">
                  <div className="wb-state__icon">ℹ</div>
                  <div>LLM 暂不可用，已降级为确定性单方案（source=fallback）</div>
                </div>
              )}

              {proposals && !proposalError && (
                <div style={{ marginTop: 12 }} data-testid="wb-design-proposals-result">
                  <div className="wb-section-label">方案列表（{proposals.length}）</div>
                  {proposals.map((p) => (
                    <div
                      className="wb-project-card"
                      key={p.proposal_id}
                      data-testid={`wb-design-proposal-card--${p.proposal_id}`}
                      style={{ borderLeft: `4px solid ${reviseId === p.proposal_id ? 'var(--accent)' : 'transparent'}` }}
                    >
                      <div className="wb-project-card__title">
                        方案{p.proposal_id} · {p.title}
                        {reviseId === p.proposal_id && (
                          <span
                            style={{
                              marginLeft: 6,
                              padding: '1px 8px',
                              borderRadius: 10,
                              fontSize: 11,
                              background: 'var(--accent)',
                              color: 'var(--on-accent)',
                            }}
                          >
                            已选中
                          </span>
                        )}
                      </div>
                      <div className="wb-design-card__body">
                        <div className="wb-design-circ-meta">
                          {p.layout_type} · {p.area_sqm}㎡ · 预算 ¥{p.budget_cny.toLocaleString()}
                        </div>
                        {p.highlights.length > 0 && (
                          <div className="wb-design-suggestions">
                            {p.highlights.map((h, hi) => (
                              <div key={hi}>✨ {h}</div>
                            ))}
                          </div>
                        )}
                        {p.rationale && <div className="wb-design-card__body">{p.rationale}</div>}
                        {p.change_log.length > 0 && (
                          <div className="wb-design-info">
                            📝 修订记录：{p.change_log.join('；')}
                          </div>
                        )}
                        <button
                          type="button"
                          className="wb-theme-option"
                          onClick={() => setReviseId(p.proposal_id)}
                          data-testid={`wb-design-proposal-select--${p.proposal_id}`}
                        >
                          选择该方案进行修改
                        </button>
                      </div>
                    </div>
                  ))}

                  {/* 修订表单 */}
                  <div className="wb-section-label" style={{ marginTop: 12 }}>
                    修订方案{reviseId ? `（${reviseId}）` : ''}
                  </div>
                  <div className="wb-field">
                    <label className="wb-field__label" htmlFor="wb-design-revise-change">
                      修改指令
                    </label>
                    <input
                      id="wb-design-revise-change"
                      className="wb-input"
                      type="text"
                      placeholder="例：方案B加中岛，预算提高到 2.8 万"
                      value={reviseChange}
                      onChange={(e) => setReviseChange(e.target.value)}
                      data-testid="wb-design-revise-change"
                    />
                  </div>
                  <button
                    type="button"
                    className="wb-theme-option wb-theme-option--active"
                    onClick={handleReviseProposal}
                    disabled={revising || !reviseId}
                    data-testid="wb-design-revise-btn"
                  >
                    {revising ? '修订中…' : '应用修改'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
