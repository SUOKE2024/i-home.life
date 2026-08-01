/**
 * DashboardPage — v1.2.9 Bento 仪表盘（跨项目聚合）
 *
 * 数据源：GET /api/dashboard/overview（项目状态分布 + 预算汇总）
 * 视觉：复用 .wb-bento 模块化非对称卡片语言（2026 趋势）
 * 对齐 Flutter dashboard_page.dart（如有）。
 */

import './pages.css';
import { SuokeLayout } from '../components/layout';
import { LoadingSkeleton } from '../components';
import { apiClient } from '../services/api-client';
import { useAsync } from '../hooks/useAsync';
import { useNavigate } from 'react-router-dom';

interface DashboardData {
  projects: { total: number; draft: number; in_progress: number; completed: number };
  budget: { total_estimated: number; total_actual: number; utilization: number };
}

const fmtMoney = (n: number): string =>
  `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync<DashboardData>(async () => {
    const r = await apiClient.getDashboardOverview();
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
    return r.data;
  }, []);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-dashboard-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">仪表盘</div>
          <button
            className="wb-page-header__back"
            onClick={reload}
            aria-label="刷新"
            type="button"
            style={{ fontSize: 'var(--font-size-md)' }}
          >
            ↻
          </button>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading ? (
            <LoadingSkeleton height={120} />
          ) : error ? (
            <div
              className="wb-bento__cell"
              role="alert"
              style={{ textAlign: 'center', color: 'var(--text-secondary)' }}
            >
              <p style={{ marginBottom: 'var(--spacing-md)' }}>{error}</p>
              <button
                type="button"
                onClick={reload}
                style={{
                  padding: '10px 20px',
                  borderRadius: 'var(--radius-input)',
                  border: '1px solid var(--accent)',
                  background: 'var(--accent)',
                  color: 'var(--bg-deep)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  minHeight: 44,
                }}
              >
                重试
              </button>
            </div>
          ) : data ? (
            <section className="wb-bento" aria-label="仪表盘概览" data-testid="wb-dashboard-bento">
              {/* 项目总数 hero */}
              <div className="wb-bento__cell wb-bento__cell--hero">
                <div>
                  <div className="wb-bento__label">项目总数</div>
                  <div className="wb-bento__value wb-bento__value--accent">
                    {data.projects.total}
                  </div>
                </div>
                <div className="wb-bento__hint">施工中 {data.projects.in_progress}</div>
              </div>

              {/* 项目状态分布 */}
              <div className="wb-bento__stats">
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">草稿</div>
                  <div className="wb-bento__value">{data.projects.draft}</div>
                </div>
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">施工中</div>
                  <div className="wb-bento__value">{data.projects.in_progress}</div>
                </div>
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">已完工</div>
                  <div className="wb-bento__value">{data.projects.completed}</div>
                </div>
              </div>

              {/* 预算汇总 */}
              <div className="wb-bento__cell">
                <div className="wb-bento__label">预算汇总</div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    margin: 'var(--spacing-sm) 0',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                    预估
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>
                    {fmtMoney(data.budget.total_estimated)}
                  </span>
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    margin: 'var(--spacing-sm) 0',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                    实际
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)', color: 'var(--accent)' }}>
                    {fmtMoney(data.budget.total_actual)}
                  </span>
                </div>
                {/* 执行率进度条 */}
                <div style={{ marginTop: 'var(--spacing-md)' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 'var(--font-size-sm)',
                      color: 'var(--text-secondary)',
                      marginBottom: 4,
                    }}
                  >
                    <span>执行率</span>
                    <span>{Math.round(data.budget.utilization * 100)}%</span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      background: 'var(--surface3)',
                      borderRadius: 'var(--radius-pill)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(data.budget.utilization * 100, 100)}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, var(--accent), var(--accent-bright))',
                        borderRadius: 'var(--radius-pill)',
                        transition: 'width var(--duration-slow) var(--ease-standard)',
                      }}
                    />
                  </div>
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </SuokeLayout>
  );
}
