/**
 * FurniturePage — 家具品类库
 *
 * 结构：Scaffold > AppBar(家具品类) > 分类筛选 chips + 家具卡片列表
 * API：GET /api/furniture-catalog（对齐 app/api/furniture_catalog.py:26，全局列表）
 *
 * 后端字段（app/schemas/furniture_catalog.py:FurnitureCatalogItemResponse）：
 *   name / category / subcategory / brand / style / price / sale_price /
 *   image_url / ar_preview_supported / stock_count / rating / material / dimensions
 *
 * 家具为全局数据（非项目维度），无需项目选择器。
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { FurnitureCatalogItem } from '../types/domain';

export default function FurniturePage() {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const { data: items, loading, error, reload } = useAsync<FurnitureCatalogItem[] | null>(
    async () => {
      const r = await apiClient.getFurnitureCatalog<FurnitureCatalogItem[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  const categories = useMemo(() => {
    if (!items) return [];
    const set = new Map<string, number>();
    items.forEach((it) => set.set(it.category, (set.get(it.category) ?? 0) + 1));
    return Array.from(set.entries()).map(([name, count]) => ({ name, count }));
  }, [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (selectedCategory === 'all') return items;
    return items.filter((it) => it.category === selectedCategory);
  }, [items, selectedCategory]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-furniture-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🪑 家具品类</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-furniture-loading">
              <div className="wb-state__icon">⏳</div><div>加载家具中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-furniture-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {!loading && !error && (items?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-furniture-empty">
              <div className="wb-state__icon">🪑</div><div>暂无家具数据</div>
            </div>
          )}

          {!loading && !error && (items?.length ?? 0) > 0 && (
            <div data-testid="wb-furniture-content">
              {categories.length > 1 && (
                <div className="wb-task-filter" role="tablist" aria-label="家具分类筛选" data-testid="wb-furniture-filters">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={selectedCategory === 'all'}
                    className={`wb-task-filter__chip ${selectedCategory === 'all' ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setSelectedCategory('all')}
                    data-testid="wb-furniture-filter--all"
                  >
                    全部({items!.length})
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat.name}
                      type="button"
                      role="tab"
                      aria-selected={selectedCategory === cat.name}
                      className={`wb-task-filter__chip ${selectedCategory === cat.name ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setSelectedCategory(cat.name)}
                      data-testid={`wb-furniture-filter--${cat.name}`}
                    >
                      {cat.name}({cat.count})
                    </button>
                  ))}
                </div>
              )}

              <div className="wb-section-label">家具（{filtered.length}）</div>

              {filtered.map((it, i) => (
                <div key={it.id} className="wb-material-card" data-testid={`wb-furniture-item--${i}`}>
                  {it.image_url ? (
                    <img
                      className="wb-material-card__img"
                      src={it.image_url}
                      alt={it.name}
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    <div className="wb-material-card__img-placeholder">🪑</div>
                  )}
                  <div className="wb-material-card__body">
                    <div className="wb-material-card__name">
                      {it.name}
                      {it.ar_preview_supported && <span style={{ fontSize: 'var(--font-size-xs)', marginLeft: 4 }}>📱AR</span>}
                    </div>
                    <div className="wb-material-card__meta">
                      <span>📦 {it.subcategory}</span>
                      {it.brand && <span>🏭 {it.brand}</span>}
                      <span>🎨 {it.style}</span>
                      {it.material && <span>🧱 {it.material}</span>}
                      <span>⭐ {it.rating}</span>
                      {it.stock_count > 0 ? <span>📦 库存 {it.stock_count}</span> : <span style={{ color: 'var(--text-muted)' }}>缺货</span>}
                    </div>
                  </div>
                  <div className="wb-material-card__price">
                    {it.sale_price != null ? (
                      <>
                        <span style={{ textDecoration: 'line-through', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                          ¥{it.price.toLocaleString()}
                        </span>
                        <br />¥{it.sale_price.toLocaleString()}
                      </>
                    ) : (
                      <>¥{it.price.toLocaleString()}</>
                    )}
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
