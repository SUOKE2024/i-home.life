/**
 * MaterialsPage — 物料管理
 *
 * 结构：Scaffold > AppBar(物料管理) > 分类筛选 chips + 物料卡片列表
 * API：
 *   GET /api/materials（对齐 app/api/materials.py:list_materials）
 *   GET /api/materials/categories（对齐 app/api/materials.py:list_categories）
 *
 * 后端字段（app/schemas/material.py）：
 *   MaterialResponse: id / category_id / name / sku / unit / unit_price /
 *     brand / spec / image_url / description / is_active / category(嵌套) /
 *     created_at / updated_at
 *   MaterialCategoryResponse: id / name / code / description / created_at
 *
 * 物料为全局数据（非项目维度），无需项目选择器。
 */

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Material, MaterialCategory } from '../types/domain';

export default function MaterialsPage() {
  const navigate = useNavigate();

  // 并行加载物料与分类（分类为公共数据，无越权风险）
  const { data: materials, loading, error, reload } = useAsync<Material[] | null>(
    async () => {
      const r = await apiClient.getMaterials<Material[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  const { data: categories } = useAsync<MaterialCategory[] | null>(
    async () => {
      const r = await apiClient.getMaterialCategories<MaterialCategory[]>();
      return r.isSuccess && r.data ? r.data : [];
    },
    [],
  );

  // 分类筛选状态（all 或 category_id）
  const selectedCategory = useMemo(() => {
    // 简单内联状态，避免额外 hook
    return (window.location.hash.match(/cat=([^&]+)/)?.[1] ?? 'all') as string;
  }, [window.location.hash]);

  const filteredMaterials = useMemo(() => {
    if (!materials) return [];
    if (selectedCategory === 'all' || !selectedCategory) return materials;
    return materials.filter((m) => m.category_id === selectedCategory);
  }, [materials, selectedCategory]);

  function setCategory(cat: string) {
    window.location.hash = cat === 'all' ? '' : `cat=${cat}`;
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-materials-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📦 物料管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-materials-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载物料中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-materials-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {!loading && !error && (materials?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-materials-empty">
              <div className="wb-state__icon">📦</div>
              <div>暂无物料数据</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与采购 Agent 对话生成物料清单
              </div>
            </div>
          )}

          {!loading && !error && (materials?.length ?? 0) > 0 && (
            <div data-testid="wb-materials-content">
              {/* 分类筛选 */}
              {categories && categories.length > 0 && (
                <div className="wb-task-filter" role="tablist" aria-label="物料分类筛选">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={selectedCategory === 'all' || !selectedCategory}
                    className={`wb-task-filter__chip ${
                      selectedCategory === 'all' || !selectedCategory
                        ? 'wb-task-filter__chip--active'
                        : ''
                    }`}
                    onClick={() => setCategory('all')}
                    data-testid="wb-materials-filter--all"
                  >
                    全部({materials!.length})
                  </button>
                  {categories.map((cat) => {
                    const count = materials!.filter(
                      (m) => m.category_id === cat.id,
                    ).length;
                    return (
                      <button
                        key={cat.id}
                        type="button"
                        role="tab"
                        aria-selected={selectedCategory === cat.id}
                        className={`wb-task-filter__chip ${
                          selectedCategory === cat.id ? 'wb-task-filter__chip--active' : ''
                        }`}
                        onClick={() => setCategory(cat.id)}
                        data-testid={`wb-materials-filter--${cat.code}`}
                      >
                        {cat.name}({count})
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="wb-section-label">物料（{filteredMaterials.length}）</div>

              {filteredMaterials.map((m, i) => (
                <div
                  key={m.id}
                  className="wb-material-card"
                  data-testid={`wb-materials-item--${i}`}
                >
                  {m.image_url ? (
                    <img
                      className="wb-material-card__img"
                      src={m.image_url}
                      alt={m.name}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="wb-material-card__img-placeholder">📦</div>
                  )}
                  <div className="wb-material-card__body">
                    <div className="wb-material-card__name">{m.name}</div>
                    <div className="wb-material-card__meta">
                      {m.category?.name && <span>🏷 {m.category.name}</span>}
                      {m.brand && <span>🏭 {m.brand}</span>}
                      {m.spec && <span>📐 {m.spec}</span>}
                      <span>SKU: {m.sku}</span>
                      {!m.is_active && (
                        <span style={{ color: 'var(--text-muted)' }}>已停用</span>
                      )}
                    </div>
                  </div>
                  <div className="wb-material-card__price">
                    ¥{m.unit_price.toLocaleString()}
                    <span
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--text-muted)',
                        fontWeight: 400,
                      }}
                    >
                      /{m.unit}
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
