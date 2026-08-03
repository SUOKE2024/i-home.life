/**
 * BudgetComparePage — F11 多方案预算对比（对齐 flutter_app/lib/pages/budget_page.dart 方案对比 tab）
 *
 * 结构：Scaffold > AppBar(方案对比) > [面积输入 + 生成按钮] > 经济/舒适/品质三档对比卡 + 差异高亮
 * API：POST /api/budgets/compare-plans（app/agents/budget.py:compare_budget_plans，确定性算法）
 *
 * 后端返回：
 *   area / plans[{tier, tier_name, total_range, total_estimated, breakdown}] /
 *   differences{economy_to_comfort, comfort_to_premium} / recommendation / reply
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { BudgetComparePlan, BudgetCompareResult } from '../types/domain';

const TIER_TONE: Record<string, string> = {
  economy: 'var(--text-secondary)',
  comfort: 'var(--success)',
  premium: 'var(--accent)',
};

export default function BudgetComparePage() {
  const navigate = useNavigate();
  const [input, setInput] = useState('126㎡');
  const [message, setMessage] = useState('126㎡');

  // message 变化时自动触发对比（初始即加载默认 126㎡ 三档对比）
  const { data: result, loading, error, reload } = useAsync<BudgetCompareResult | null>(
    async () => {
      const r = await apiClient.compareBudgetPlans<BudgetCompareResult>(message);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '生成对比失败');
      return r.data;
    },
    [message],
  );

  const submit = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setMessage(trimmed);
  };

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-budget-compare-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📊 多方案预算对比</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 面积输入 + 生成 */}
          <div className="wb-project-picker" style={{ alignItems: 'stretch' }}>
            <input
              className="wb-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入房屋面积，如 126㎡"
              aria-label="房屋面积"
              data-testid="wb-budget-compare-input"
              style={{ flex: 1, minWidth: 0 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submit();
              }}
            />
            <button
              type="button"
              className="wb-theme-option wb-theme-option--active"
              onClick={submit}
              disabled={loading}
              data-testid="wb-budget-compare-generate"
            >
              {loading ? '生成中…' : '⚡ 生成三档对比'}
            </button>
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-budget-compare-loading">
              <div className="wb-state__icon">⏳</div>
              <div>正在生成 {message} 三档预算对比…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-budget-compare-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {!loading && !error && result && (
            <div data-testid="wb-budget-compare-content">
              {/* 面积标题 */}
              <div className="wb-section-label">
                📐 {result.area}㎡ 三档预算对比（{result.plans.length} 档）
              </div>

              {/* 三档方案卡 */}
              {result.plans.map((plan, i) => (
                <PlanCard key={plan.tier} plan={plan} index={i} />
              ))}

              {/* 档位差异高亮 */}
              {result.differences && (
                <div
                  style={{
                    marginTop: 16,
                    padding: '12px 14px',
                    background: 'rgba(201, 122, 59, 0.1)',
                    border: '1px solid var(--warning)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--font-size-sm)',
                  }}
                  data-testid="wb-budget-compare-diff"
                >
                  <div style={{ fontWeight: 600, color: 'var(--warning)', marginBottom: 6 }}>
                    📈 档位差异
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    经济型 → 舒适型：+¥{(result.differences.economy_to_comfort ?? 0).toLocaleString()}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    舒适型 → 品质型：+¥{(result.differences.comfort_to_premium ?? 0).toLocaleString()}
                  </div>
                </div>
              )}

              {/* 推荐方案 */}
              {result.recommendation && (
                <div
                  style={{
                    marginTop: 12,
                    padding: '12px 14px',
                    background: 'var(--surface1)',
                    border: '1px solid var(--border-active)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--accent)',
                    fontStyle: 'italic',
                  }}
                  data-testid="wb-budget-compare-recommend"
                >
                  💡 {result.recommendation}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}

/** 单个档位方案卡（含分项明细） */
function PlanCard({ plan, index }: { plan: BudgetComparePlan; index: number }) {
  const [min, max] = plan.total_range ?? [0, 0];
  return (
    <div
      className="wb-budget-item"
      style={{ flexDirection: 'column', alignItems: 'stretch', gap: 4 }}
      data-testid={`wb-budget-compare-plan--${index}`}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="wb-budget-item__name">{plan.tier_name}</div>
        <div
          className="wb-budget-item__amount"
          style={{ fontSize: 20, color: TIER_TONE[plan.tier] ?? 'var(--text-primary)' }}
        >
          ¥{Math.round(plan.total_estimated).toLocaleString()}
        </div>
      </div>
      <div className="wb-budget-item__cat">
        价格区间：¥{Math.round(min).toLocaleString()} ~ ¥{Math.round(max).toLocaleString()}
      </div>
      {plan.breakdown && Object.keys(plan.breakdown).length > 0 && (
        <div style={{ marginTop: 8 }}>
          {Object.entries(plan.breakdown).map(([cat, amount]) => (
            <div
              key={cat}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                padding: '3px 0',
                borderBottom: '1px dashed var(--border)',
              }}
            >
              <span>{cat}</span>
              <span>¥{Math.round(amount).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
