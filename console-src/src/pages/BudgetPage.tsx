/**
 * BudgetPage — 对齐 flutter_app/lib/pages/budget_page.dart
 *
 * 结构：Scaffold > AppBar(预算) > [项目选择器] > 概览统计 + 分项明细列表
 * API：GET /api/budgets/project/{id}（预算详情）
 *
 * Flutter 端有 3 tabs（当前预算/方案对比/模板），批次 4 实现"当前预算"主 tab，
 * 方案对比/模板留批次 5。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Budget, Project } from '../types/domain';

export default function BudgetPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  // 加载项目列表（供选择器）
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  // 默认选第一个项目
  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载预算（依赖选中项目）
  const { data: budget, loading, error, reload } = useAsync<Budget | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getBudget<Budget>(selectedProjectId);
      if (r.status === 404) return null; // 无预算
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const totalAmount = budget?.total_estimated ?? 0;
  const spentAmount = budget?.total_actual ?? 0;
  const remaining = totalAmount - spentAmount;
  const spentPercent = totalAmount > 0 ? Math.round((spentAmount / totalAmount) * 100) : 0;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-budget-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">💰 预算管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-budget-project-select"
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
            <div className="wb-state" data-testid="wb-budget-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-budget-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载预算中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-budget-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && !budget && (
            <div className="wb-state" data-testid="wb-budget-empty">
              <div className="wb-state__icon">💰</div>
              <div>该项目暂无预算</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与预算 Agent 对话生成，或从 BOM 自动生成
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && budget && (
            <div data-testid="wb-budget-content">
              {/* 概览统计 */}
              <div className="wb-budget-summary">
                <div className="wb-budget-stat">
                  <div className="wb-budget-stat__label">总预算</div>
                  <div className="wb-budget-stat__value">¥{totalAmount.toLocaleString()}</div>
                </div>
                <div className="wb-budget-stat wb-budget-stat--spent">
                  <div className="wb-budget-stat__label">已支出（{spentPercent}%）</div>
                  <div className="wb-budget-stat__value">¥{spentAmount.toLocaleString()}</div>
                </div>
                <div className="wb-budget-stat wb-budget-stat--remaining">
                  <div className="wb-budget-stat__label">剩余</div>
                  <div className="wb-budget-stat__value">¥{remaining.toLocaleString()}</div>
                </div>
              </div>

              {/* 进度条 */}
              <div className="wb-progress-bar" style={{ marginBottom: 20 }}>
                <div className="wb-progress-bar__fill" style={{ width: `${spentPercent}%` }} />
              </div>

              {/* 分项明细 */}
              <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', margin: '16px 0 10px' }}>
                分项明细（{budget.lines?.length ?? 0} 项）
              </div>
              {budget.lines && budget.lines.length > 0 ? (
                budget.lines.map((item, i) => (
                  <div className="wb-budget-item" key={item.id ?? i} data-testid={`wb-budget-item--${i}`}>
                    <div>
                      <div className="wb-budget-item__name">{item.name}</div>
                      {item.category && <div className="wb-budget-item__cat">{item.category}</div>}
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="wb-budget-item__amount">¥{(item.estimated_amount ?? 0).toLocaleString()}</div>
                      {item.actual_amount != null && item.actual_amount > 0 && (
                        <div className="wb-budget-item__spent">已花 ¥{item.actual_amount.toLocaleString()}</div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="wb-state">
                  <div>暂无分项明细</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
