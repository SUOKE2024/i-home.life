/**
 * ProductsPage — 产品/服务管理
 *
 * 结构：Scaffold > AppBar(产品管理) > 分类筛选 chips + 产品卡片列表
 * API：GET /api/products（对齐 app/api/products.py:113，全局 user 维度列表）
 *
 * 后端字段（app/schemas/product.py:ProductResponse）：
 *   name / category / price_min / price_max / unit / cover_image / tags /
 *   stock_status / status / ai_generated / description
 *
 * 产品为全局数据（非项目维度），无需项目选择器。
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Product } from '../types/domain';

export default function ProductsPage() {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const { data: products, loading, error, reload } = useAsync<Product[] | null>(
    async () => {
      const r = await apiClient.getProducts<Product[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  // 从产品列表派生分类（动态提取，无独立分类端点）
  const categories = useMemo(() => {
    if (!products) return [];
    const set = new Map<string, number>();
    products.forEach((p) => set.set(p.category, (set.get(p.category) ?? 0) + 1));
    return Array.from(set.entries()).map(([name, count]) => ({ name, count }));
  }, [products]);

  const filtered = useMemo(() => {
    if (!products) return [];
    if (selectedCategory === 'all') return products;
    return products.filter((p) => p.category === selectedCategory);
  }, [products, selectedCategory]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-products-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🛒 产品管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-products-loading">
              <div className="wb-state__icon">⏳</div><div>加载产品中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-products-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {!loading && !error && (products?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-products-empty">
              <div className="wb-state__icon">🛒</div><div>暂无产品数据</div>
            </div>
          )}

          {!loading && !error && (products?.length ?? 0) > 0 && (
            <div data-testid="wb-products-content">
              {categories.length > 1 && (
                <div className="wb-task-filter" role="tablist" aria-label="产品分类筛选" data-testid="wb-products-filters">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={selectedCategory === 'all'}
                    className={`wb-task-filter__chip ${selectedCategory === 'all' ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setSelectedCategory('all')}
                    data-testid="wb-products-filter--all"
                  >
                    全部({products!.length})
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat.name}
                      type="button"
                      role="tab"
                      aria-selected={selectedCategory === cat.name}
                      className={`wb-task-filter__chip ${selectedCategory === cat.name ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setSelectedCategory(cat.name)}
                      data-testid={`wb-products-filter--${cat.name}`}
                    >
                      {cat.name}({cat.count})
                    </button>
                  ))}
                </div>
              )}

              <div className="wb-section-label">产品（{filtered.length}）</div>

              {filtered.map((p, i) => (
                <div key={p.id} className="wb-material-card" data-testid={`wb-products-item--${i}`}>
                  {p.cover_image ? (
                    <img
                      className="wb-material-card__img"
                      src={p.cover_image}
                      alt={p.name}
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    <div className="wb-material-card__img-placeholder">🛒</div>
                  )}
                  <div className="wb-material-card__body">
                    <div className="wb-material-card__name">
                      {p.name}
                      {p.ai_generated && <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginLeft: 4 }}>AI</span>}
                    </div>
                    <div className="wb-material-card__meta">
                      <span>📦 {p.category}</span>
                      {p.stock_status && <span>📊 {p.stock_status}</span>}
                      {p.status !== 'active' && <span style={{ color: 'var(--text-muted)' }}>{p.status}</span>}
                    </div>
                  </div>
                  <div className="wb-material-card__price">
                    {p.price_min != null && p.price_max != null
                      ? `¥${p.price_min.toLocaleString()}-${p.price_max.toLocaleString()}`
                      : p.price_min != null
                        ? `¥${p.price_min.toLocaleString()}`
                        : '面议'}
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>
                      /{p.unit}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
