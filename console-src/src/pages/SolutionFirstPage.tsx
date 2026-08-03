/**
 * SolutionFirstPage — 方案前置决策（F45, v1.5.0）
 *
 * 结构：Scaffold > AppBar(方案前置) > [项目选择器] > 生成按钮 + 3 套布局卡片 + 预算区间卡 + 推荐建议
 * API（对齐 app/api/solution_first.py）：
 *   POST /api/solution-first/generate   生成 3 套前置方案 + 预算区间（source: rule_based）
 *
 * 布局由内置规则引擎生成（诚实标注 source=rule_based），可后续接入 LLM 升级。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, SolutionFirstPackage } from '../types/domain';

const PLAN_TONES = ['accent', 'info', 'success'];

export default function SolutionFirstPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pkg, setPkg] = useState<SolutionFirstPackage | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  async function handleGenerate() {
    if (!selectedProjectId) return;
    setGenerating(true);
    setError(null);
    try {
      const r = await apiClient.generateSolutionFirst<SolutionFirstPackage>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '生成失败');
      setPkg(r.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPkg(null);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-solution-first-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🚀 方案前置</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-solution-first-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-solution-first-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && (
            <div data-testid="wb-solution-first-content">
              <div className="wb-create-form" data-testid="wb-solution-first-generate">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🚀</div>
                  <div>
                    <div className="wb-create-form__title">方案前置决策</div>
                    <div className="wb-create-form__subtitle">上传户型后先生成 3 套布局方案 + 预算区间（source: rule_based）</div>
                  </div>
                </div>
                {error && (
                  <div className="wb-create-form__error" data-testid="wb-solution-first-error">
                    ⚠ {error}
                  </div>
                )}
                <div className="wb-create-form__actions" style={{ marginTop: 12 }}>
                  <button className="wb-theme-option wb-theme-option--active" type="button" onClick={handleGenerate} disabled={generating} data-testid="wb-solution-first-submit" style={{ width: '100%' }}>
                    {generating ? '生成中…' : '🚀 生成 3 套方案'}
                  </button>
                </div>
              </div>

              {!generating && pkg && (
                <div data-testid="wb-solution-first-result">
                  <div className="wb-smart-card__meta" style={{ marginBottom: 10 }}>
                    <span>📐 项目 {pkg.project_name}（{pkg.project_id}）</span>
                    <span>🧩 {pkg.plan_count} 套方案</span>
                    <span>🕒 {new Date(pkg.generated_at).toLocaleString('zh-CN')}</span>
                  </div>

                  {/* 3 套布局卡片 */}
                  {pkg.layouts.map((layout, i) => (
                    <div key={layout.plan_no} className="wb-smart-card" data-testid={`wb-solution-first-layout--${i}`}>
                      <div className="wb-smart-card__head">
                        <div className="wb-smart-card__room">方案 {layout.plan_no} · {layout.name}</div>
                        <span className={`wb-status-chip wb-status-chip--${PLAN_TONES[i % PLAN_TONES.length]}`}>{layout.plan_no}</span>
                      </div>
                      <div className="wb-smart-card__meta">
                        <span>💡 {layout.summary}</span>
                      </div>
                      <div className="wb-section-label" style={{ marginTop: 10 }}>布局要点</div>
                      {layout.layout_points.map((point, j) => (
                        <div key={j} className="wb-co-item">
                          <span>• {point}</span>
                        </div>
                      ))}
                      <div className="wb-section-label" style={{ marginTop: 10 }}>优势</div>
                      <div className="wb-smart-card__meta" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                        {layout.pros.map((pro, j) => (<span key={j}>✅ {pro}</span>))}
                      </div>
                      <div className="wb-section-label" style={{ marginTop: 10 }}>不足</div>
                      <div className="wb-smart-card__meta" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                        {layout.cons.map((con, j) => (<span key={j}>⚠ {con}</span>))}
                      </div>
                    </div>
                  ))}

                  {/* 预算区间卡 */}
                  <div className="wb-smart-card" data-testid="wb-solution-first-budget">
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">预算区间（{pkg.budget_range.level} 档主推）</div>
                      <span className="wb-status-chip wb-status-chip--accent">¥{pkg.budget_range.lower.toLocaleString()} - ¥{pkg.budget_range.upper.toLocaleString()}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>单价 ¥{pkg.budget_range.per_sqm_lower}-{pkg.budget_range.per_sqm_upper}/㎡</span>
                      <span>{pkg.budget_range.note}</span>
                    </div>
                    <div className="wb-section-label" style={{ marginTop: 10 }}>三档明细</div>
                    {pkg.budget_range.levels.map((lv) => (
                      <div key={lv.level} className="wb-co-item">
                        <div>
                          <strong>{lv.level}</strong>
                          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                            {' '}¥{lv.per_sqm_lower}-{lv.per_sqm_upper}/㎡ · 总价 ¥{lv.lower.toLocaleString()}-{lv.upper.toLocaleString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* 推荐建议 */}
                  <div className="wb-smart-card" data-testid="wb-solution-first-recommendations">
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">推荐建议</div>
                    </div>
                    {pkg.recommendations.map((rec, i) => (
                      <div key={i} className="wb-co-item">
                        <span>{i + 1}. {rec}</span>
                      </div>
                    ))}
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }}>{pkg.source_note}</div>
                  </div>
                </div>
              )}

              {!generating && !pkg && !error && (
                <div className="wb-state" data-testid="wb-solution-first-empty">
                  <div className="wb-state__icon">🚀</div><div>尚未生成方案</div>
                  <div style={{ fontSize: 'var(--font-size-sm)' }}>点击上方按钮为当前项目生成 3 套前置方案与预算区间</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
