/**
 * AppliancePage — 家电管理
 *
 * 结构：Scaffold > AppBar(家电管理) > 分类筛选 chips + 电器卡片列表
 * API：
 *   GET /api/appliances/categories（对齐 app/api/appliance.py:48）
 *   GET /api/appliances/search?category_id=（对齐 app/api/appliance.py:113）
 *
 * 后端字段（app/schemas/appliance.py）：
 *   ApplianceResponse: id / category_id / name / brand / model / subcategory /
 *     spec / power_rating / energy_label / price / image_url / tags / status
 *   ApplianceCategoryResponse: id / name / code / description
 *
 * 家电为全局数据（非项目维度），无需项目选择器。
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Appliance, ApplianceCategory } from '../types/domain';

export default function AppliancePage() {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const { data: categories } = useAsync<ApplianceCategory[] | null>(async () => {
    const r = await apiClient.getApplianceCategories<ApplianceCategory[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  // 按 category_id 筛选（依赖 selectedCategory）
  const { data: appliances, loading, error, reload } = useAsync<Appliance[] | null>(
    async () => {
      const r = await apiClient.searchAppliances<Appliance[]>(
        selectedCategory !== 'all' ? { categoryId: selectedCategory } : {},
      );
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedCategory],
  );

  const subcategoryLabels = useMemo(() => ({
    air_conditioner: '空调', refrigerator: '冰箱', washing_machine: '洗衣机',
    water_heater: '热水器', tv: '电视', range_hood: '油烟机', cooktop: '灶具',
    dishwasher: '洗碗机', steam_oven: '蒸烤箱', microwave: '微波炉',
    water_purifier: '净水器', garbage_disposal: '垃圾处理器', robot_vacuum: '扫地机器人',
    vacuum_cleaner: '吸尘器', dehumidifier: '除湿机', fresh_air_system: '新风系统',
  }), []);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-appliance-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🔌 家电管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-appliance-loading">
              <div className="wb-state__icon">⏳</div><div>加载家电中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-appliance-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {!loading && !error && (appliances?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-appliance-empty">
              <div className="wb-state__icon">🔌</div><div>暂无家电数据</div>
            </div>
          )}

          {!loading && !error && (appliances?.length ?? 0) > 0 && (
            <div data-testid="wb-appliance-content">
              {/* 分类筛选 */}
              {categories && categories.length > 0 && (
                <div className="wb-task-filter" role="tablist" aria-label="家电分类筛选" data-testid="wb-appliance-filters">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={selectedCategory === 'all'}
                    className={`wb-task-filter__chip ${selectedCategory === 'all' ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setSelectedCategory('all')}
                    data-testid="wb-appliance-filter--all"
                  >
                    全部
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      role="tab"
                      aria-selected={selectedCategory === cat.id}
                      className={`wb-task-filter__chip ${selectedCategory === cat.id ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setSelectedCategory(cat.id)}
                      data-testid={`wb-appliance-filter--${cat.code}`}
                    >
                      {cat.name}
                    </button>
                  ))}
                </div>
              )}

              <div className="wb-section-label">家电（{appliances!.length}）</div>

              {appliances!.map((a, i) => (
                <div key={a.id} className="wb-material-card" data-testid={`wb-appliance-item--${i}`}>
                  {a.image_url ? (
                    <img
                      className="wb-material-card__img"
                      src={a.image_url}
                      alt={a.name}
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    <div className="wb-material-card__img-placeholder">🔌</div>
                  )}
                  <div className="wb-material-card__body">
                    <div className="wb-material-card__name">{a.name}</div>
                    <div className="wb-material-card__meta">
                      <span>📦 {(subcategoryLabels as Record<string, string>)[a.subcategory] ?? a.subcategory}</span>
                      {a.brand && <span>🏭 {a.brand}</span>}
                      {a.spec && <span>📐 {a.spec}</span>}
                      {a.power_rating && <span>⚡ {a.power_rating}W</span>}
                      {a.energy_label && <span>🏷 {a.energy_label}</span>}
                      {a.status !== 'active' && <span style={{ color: 'var(--text-muted)' }}>已停用</span>}
                    </div>
                  </div>
                  <div className="wb-material-card__price">
                    ¥{a.price.toLocaleString()}
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
