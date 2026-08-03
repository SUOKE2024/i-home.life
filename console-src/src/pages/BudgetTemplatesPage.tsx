/**
 * BudgetTemplatesPage — F13 预算模板库（对齐 flutter_app/lib/pages/budget_page.dart 模板库 tab）
 *
 * 结构：Scaffold > AppBar(模板库) > 模板卡片列表（含"应用"） + 应用结果详情
 * API：
 *   GET /api/budgets/templates（app/agents/budget.py:list_templates）
 *   POST /api/budgets/templates/apply（app/agents/budget.py:apply_template，按面积等比缩放）
 *
 * 后端返回模板字段：code / name / area / tier / style / total_range / line_count
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  BudgetTemplate,
  BudgetTemplateApplyResult,
  BudgetTemplateList,
} from '../types/domain';

const TIER_CN: Record<string, string> = {
  economy: '经济型',
  comfort: '舒适型',
  premium: '品质型',
  luxury: '豪华型',
};

export default function BudgetTemplatesPage() {
  const navigate = useNavigate();
  const [applied, setApplied] = useState<BudgetTemplateApplyResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, loading, error, reload } = useAsync<BudgetTemplateList | null>(
    async () => {
      const r = await apiClient.listBudgetTemplates<BudgetTemplateList>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载模板失败');
      return r.data;
    },
    [],
  );

  const templates = data?.templates ?? [];

  const applyTemplate = async (code: string) => {
    setApplying(true);
    setActionError(null);
    try {
      const r = await apiClient.applyBudgetTemplate<BudgetTemplateApplyResult>(code);
      if (!r.isSuccess || !r.data) {
        setActionError(r.error ?? '应用失败');
      } else {
        setApplied(r.data);
      }
    } finally {
      setApplying(false);
    }
  };

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-budget-templates-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📚 预算模板库</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {data && (
            <div className="wb-section-label">
              💬 {data.reply}（共 {data.total} 套）
            </div>
          )}

          {loading && (
            <div className="wb-state" data-testid="wb-budget-templates-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载模板库中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-budget-templates-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {!loading && !error && templates.length === 0 && (
            <div className="wb-state" data-testid="wb-budget-templates-empty">
              <div className="wb-state__icon">📚</div>
              <div>暂无预算模板</div>
            </div>
          )}

          {!loading && !error && templates.length > 0 && (
            <div data-testid="wb-budget-templates-content">
              {templates.map((tpl, i) => (
                <TemplateCard
                  key={tpl.code}
                  tpl={tpl}
                  index={i}
                  applying={applying}
                  onApply={() => applyTemplate(tpl.code)}
                />
              ))}

              {actionError && (
                <div
                  className="wb-state wb-state--error"
                  style={{ padding: '16px' }}
                  data-testid="wb-budget-templates-action-error"
                >
                  <div>{actionError}</div>
                </div>
              )}

              {/* 应用结果详情 */}
              {applied && (
                <div
                  style={{
                    marginTop: 16,
                    padding: '14px 16px',
                    background: 'rgba(74, 158, 110, 0.1)',
                    border: '1px solid var(--success)',
                    borderRadius: 'var(--radius-md)',
                  }}
                  data-testid="wb-budget-templates-applied"
                >
                  <div
                    style={{
                      fontWeight: 600,
                      color: 'var(--success)',
                      marginBottom: 6,
                      fontSize: 'var(--font-size-sm)',
                    }}
                  >
                    ✅ {applied.reply}
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--font-size-md)',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      marginBottom: 8,
                    }}
                  >
                    模板总价 ¥{Math.round(applied.total_estimated).toLocaleString()}
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                      （面积 {applied.applied_area}㎡，缩放比例 {applied.scale}）
                    </span>
                  </div>
                  {applied.lines && applied.lines.length > 0 && (
                    <div>
                      {applied.lines.map((line, li) => (
                        <div
                          key={li}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--text-secondary)',
                            padding: '3px 0',
                            borderBottom: '1px dashed var(--border)',
                          }}
                        >
                          <span>
                            {line.name}
                            <span style={{ color: 'var(--text-muted)' }}>
                              {' '}
                              × {line.quantity} {line.unit}
                            </span>
                          </span>
                          <span>¥{Math.round(line.estimated_amount).toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}

function TemplateCard({
  tpl,
  index,
  applying,
  onApply,
}: {
  tpl: BudgetTemplate;
  index: number;
  applying: boolean;
  onApply: () => void;
}) {
  const [min, max] = tpl.total_range ?? [0, 0];
  return (
    <div className="wb-budget-item" data-testid={`wb-budget-template--${index}`}>
      <div style={{ minWidth: 0 }}>
        <div className="wb-budget-item__name">{tpl.name}</div>
        <div className="wb-budget-item__cat">
          {tpl.area}㎡ · {TIER_CN[tpl.tier] ?? tpl.tier} · {tpl.style} · {tpl.line_count} 项
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div className="wb-budget-item__amount">
          ¥{Math.round(min).toLocaleString()} ~ ¥{Math.round(max).toLocaleString()}
        </div>
        <button
          type="button"
          className="wb-theme-option wb-theme-option--active"
          onClick={onApply}
          disabled={applying}
          data-testid={`wb-budget-template-apply--${index}`}
          style={{ marginTop: 6 }}
        >
          {applying ? '应用中…' : '应用模板'}
        </button>
      </div>
    </div>
  );
}
