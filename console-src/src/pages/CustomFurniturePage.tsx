/**
 * CustomFurniturePage — 定制家具设计
 *
 * 结构：Scaffold > AppBar(定制家具) > [项目选择器] > 设计卡片列表（可展开详情）
 * API：
 *   GET /api/custom-furniture/designs/project/{projectId}                 — 设计列表
 *   GET /api/custom-furniture/designs/{designId}/modules                  — 模块
 *   GET /api/custom-furniture/designs/{designId}/bom                      — BOM
 *   GET /api/custom-furniture/designs/{designId}/price                    — 价格估算
 *   GET /api/custom-furniture/designs/{designId}/panels                   — 板材计算
 *   GET /api/custom-furniture/designs/{designId}/validation               — 规格校验
 *
 * 后端字段（app/schemas/custom_furniture.py）：
 *   CustomFurnitureDesignResponse: room_name / furniture_type / total_width /
 *   total_height / total_depth / panel_material / panel_thickness / edge_banding /
 *   hardware_brand / color / style / total_price / status
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  Project,
  CustomFurnitureDesign,
  FurnitureModule,
  FurnitureBOMItem,
  FurniturePriceEstimate,
  FurniturePanelCompute,
  FurnitureValidation,
} from '../types/domain';

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  draft: { label: '草稿', cls: 'pending' },
  pricing: { label: '估价中', cls: 'active' },
  quoted: { label: '已报价', cls: 'completed' },
  ordered: { label: '已下单', cls: 'completed' },
  production: { label: '生产中', cls: 'active' },
  delivered: { label: '已交付', cls: 'completed' },
};

const FURNITURE_TYPE_LABELS: Record<string, string> = {
  wardrobe: '衣柜',
  kitchen_cabinet: '橱柜',
  bathroom_vanity: '浴室柜',
  bookshelf: '书柜',
  shoe_cabinet: '鞋柜',
  tv_cabinet: '电视柜',
  wine_cabinet: '酒柜',
  sideboard: '餐边柜',
  full_wall_cabinet: '满墙柜',
};

const STYLE_LABELS: Record<string, string> = {
  modern: '现代',
  nordic: '北欧',
  japanese: '日式',
  luxury: '轻奢',
  chinese: '中式',
  industrial: '工业风',
  coastal: '海滨',
};

type DetailTab = 'modules' | 'bom' | 'price' | 'panels' | 'validation';

interface DetailState {
  modules: FurnitureModule[];
  bom: FurnitureBOMItem[];
  price: FurniturePriceEstimate | null;
  panels: FurniturePanelCompute | null;
  validation: FurnitureValidation | null;
}

export default function CustomFurniturePage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>('price');
  const [detail, setDetail] = useState<DetailState | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: designs, loading, error, reload } = useAsync<CustomFurnitureDesign[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getCustomFurnitureDesigns<CustomFurnitureDesign[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  // 收起时清理详情
  useEffect(() => {
    if (expandedId === null) {
      setDetail(null);
      setDetailError(null);
    }
  }, [expandedId]);

  const loadDetail = useCallback(async (designId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const [modulesR, bomR, priceR, panelsR, validationR] = await Promise.all([
        apiClient.getFurnitureModules<FurnitureModule[]>(designId),
        apiClient.getFurnitureBom<FurnitureBOMItem[]>(designId),
        apiClient.getFurniturePrice<FurniturePriceEstimate>(designId),
        apiClient.getFurniturePanels<FurniturePanelCompute>(designId),
        apiClient.getFurnitureValidation<FurnitureValidation>(designId),
      ]);
      setDetail({
        modules: modulesR.isSuccess && modulesR.data ? modulesR.data : [],
        bom: bomR.isSuccess && bomR.data ? bomR.data : [],
        price: priceR.isSuccess && priceR.data ? priceR.data : null,
        panels: panelsR.isSuccess && panelsR.data ? panelsR.data : null,
        validation: validationR.isSuccess && validationR.data ? validationR.data : null,
      });
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : '加载详情失败');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const toggleExpand = (designId: string) => {
    if (expandedId === designId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(designId);
    setActiveTab('price');
    void loadDetail(designId);
  };

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-customfurniture-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🪑 定制家具</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-customfurniture-project-select"
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
            <div className="wb-state" data-testid="wb-customfurniture-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-customfurniture-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载定制家具设计中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-customfurniture-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (designs?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-customfurniture-empty">
              <div className="wb-state__icon">🪑</div>
              <div>暂无定制家具设计</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与定制家具 Agent 对话生成
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (designs?.length ?? 0) > 0 && (
            <div data-testid="wb-customfurniture-content">
              <div className="wb-section-label">定制家具设计（{designs!.length}）</div>

              {designs!.map((d, i) => {
                const expanded = expandedId === d.id;
                const st = STATUS_LABELS[d.status] ?? { label: d.status, cls: 'pending' };
                return (
                  <div
                    key={d.id}
                    className="wb-project-card"
                    data-testid={`wb-customfurniture-item--${i}`}
                  >
                    <button
                      type="button"
                      className="wb-furniture-card__head"
                      onClick={() => toggleExpand(d.id)}
                      data-testid={`wb-customfurniture-toggle--${i}`}
                      aria-expanded={expanded}
                    >
                      <div className="wb-project-card__title">
                        {FURNITURE_TYPE_LABELS[d.furniture_type] ?? d.furniture_type}
                        <span
                          style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--text-muted)',
                            marginLeft: 8,
                          }}
                        >
                          {d.room_name}
                        </span>
                      </div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">
                          📐 {d.total_width}×{d.total_height}×{d.total_depth}mm
                        </span>
                        {d.total_price > 0 && (
                          <span className="wb-project-card__meta-item">
                            💰 ¥{d.total_price.toLocaleString()}
                          </span>
                        )}
                        <span className="wb-project-card__meta-item">
                          🎨 {STYLE_LABELS[d.style] ?? d.style}
                        </span>
                      </div>
                      <div className="wb-project-card__meta">
                        <span
                          className={`wb-status-badge wb-status--${st.cls}`}
                          data-testid={`wb-customfurniture-status--${i}`}
                        >
                          {st.label}
                        </span>
                        <span
                          style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--text-muted)',
                            marginLeft: 'auto',
                          }}
                        >
                          {expanded ? '收起 ▲' : '展开详情 ▼'}
                        </span>
                      </div>
                    </button>

                    {expanded && (
                      <div
                        className="wb-furniture-detail"
                        data-testid={`wb-customfurniture-detail--${i}`}
                      >
                        <div className="wb-furniture-detail__spec">
                          <span>板材: {d.panel_material}（{d.panel_thickness}mm）</span>
                          <span>封边: {d.edge_banding}</span>
                          <span>五金: {d.hardware_brand}</span>
                          {d.color && <span>颜色: {d.color}</span>}
                        </div>

                        {detailLoading && (
                          <div className="wb-state" style={{ padding: '12px' }}>
                            <div className="wb-state__icon">⏳</div>
                            <div>加载详情…</div>
                          </div>
                        )}
                        {detailError && !detailLoading && (
                          <div className="wb-state wb-state--error" style={{ padding: '12px' }}>
                            <div className="wb-state__icon">⚠</div>
                            <div>{detailError}</div>
                          </div>
                        )}

                        {detail && !detailLoading && (
                          <>
                            <div
                              className="wb-task-filter"
                              role="tablist"
                              aria-label="详情视图"
                              data-testid={`wb-customfurniture-tabs--${i}`}
                            >
                              {([
                                ['price', '💰 价格'],
                                ['modules', '🧱 模块'],
                                ['bom', '📋 BOM'],
                                ['panels', '📐 板材'],
                                ['validation', '✓ 校验'],
                              ] as Array<[DetailTab, string]>).map(([key, label]) => (
                                <button
                                  key={key}
                                  type="button"
                                  role="tab"
                                  aria-selected={activeTab === key}
                                  className={`wb-task-filter__chip ${activeTab === key ? 'wb-task-filter__chip--active' : ''}`}
                                  onClick={() => setActiveTab(key)}
                                  data-testid={`wb-customfurniture-tab--${key}`}
                                >
                                  {label}
                                </button>
                              ))}
                            </div>

                            {activeTab === 'price' && (
                              <div
                                className="wb-takeoff-summary"
                                data-testid={`wb-customfurniture-price--${i}`}
                              >
                                {detail.price ? (
                                  <div className="wb-takeoff-stat-grid">
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        ¥{detail.price.panel_cost.toLocaleString()}
                                      </div>
                                      <div className="wb-takeoff-stat__label">板材费用</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        ¥{detail.price.hardware_cost.toLocaleString()}
                                      </div>
                                      <div className="wb-takeoff-stat__label">五金费用</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        ¥{detail.price.door_cost.toLocaleString()}
                                      </div>
                                      <div className="wb-takeoff-stat__label">门板费用</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        ¥{detail.price.process_cost.toLocaleString()}
                                      </div>
                                      <div className="wb-takeoff-stat__label">加工费</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        <span>¥{detail.price.total_price.toLocaleString()}</span>
                                      </div>
                                      <div className="wb-takeoff-stat__label">总价</div>
                                    </div>
                                  </div>
                                ) : (
                                  <div style={{ color: 'var(--text-muted)' }}>暂无价格估算</div>
                                )}
                              </div>
                            )}

                            {activeTab === 'modules' && (
                              <div data-testid={`wb-customfurniture-modules--${i}`}>
                                {detail.modules.length === 0 ? (
                                  <div style={{ color: 'var(--text-muted)' }}>暂无模块，请先执行参数化设计</div>
                                ) : (
                                  detail.modules.map((m, mi) => (
                                    <div
                                      key={m.id}
                                      className="wb-furniture-line"
                                      data-testid={`wb-customfurniture-module--${mi}`}
                                    >
                                      <span className="wb-furniture-line__name">
                                        {m.module_type} × {m.quantity}
                                      </span>
                                      <span className="wb-furniture-line__spec">
                                        {m.width}×{m.height}×{m.depth}mm
                                      </span>
                                      {m.price > 0 && (
                                        <span className="wb-furniture-line__price">
                                          ¥{m.price.toLocaleString()}
                                        </span>
                                      )}
                                    </div>
                                  ))
                                )}
                              </div>
                            )}

                            {activeTab === 'bom' && (
                              <div data-testid={`wb-customfurniture-bom--${i}`}>
                                {detail.bom.length === 0 ? (
                                  <div style={{ color: 'var(--text-muted)' }}>暂无 BOM</div>
                                ) : (
                                  detail.bom.map((b, bi) => (
                                    <div
                                      key={b.id}
                                      className="wb-furniture-line"
                                      data-testid={`wb-customfurniture-bomitem--${bi}`}
                                    >
                                      <span className="wb-furniture-line__name">{b.item_name}</span>
                                      <span className="wb-furniture-line__spec">
                                        {b.quantity} {b.unit} × ¥{b.unit_price}
                                      </span>
                                      <span className="wb-furniture-line__price">
                                        ¥{b.total_price.toLocaleString()}
                                      </span>
                                    </div>
                                  ))
                                )}
                              </div>
                            )}

                            {activeTab === 'panels' && (
                              <div
                                className="wb-takeoff-summary"
                                data-testid={`wb-customfurniture-panels--${i}`}
                              >
                                {detail.panels ? (
                                  <div className="wb-takeoff-stat-grid">
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        {detail.panels.total_panel_area_m2.toFixed(2)}
                                      </div>
                                      <div className="wb-takeoff-stat__label">展开面积(㎡)</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        {detail.panels.panel_sheets.toFixed(1)}
                                      </div>
                                      <div className="wb-takeoff-stat__label">板材用量(张)</div>
                                    </div>
                                    <div className="wb-takeoff-stat">
                                      <div className="wb-takeoff-stat__value">
                                        {detail.panels.hardware_list.length}
                                      </div>
                                      <div className="wb-takeoff-stat__label">五金件项数</div>
                                    </div>
                                  </div>
                                ) : (
                                  <div style={{ color: 'var(--text-muted)' }}>暂无板材计算</div>
                                )}
                              </div>
                            )}

                            {activeTab === 'validation' && (
                              <div data-testid={`wb-customfurniture-validation--${i}`}>
                                {detail.validation ? (
                                  detail.validation.valid ? (
                                    <div
                                      className="wb-status-badge wb-status--completed"
                                      data-testid={`wb-customfurniture-validation-ok--${i}`}
                                    >
                                      ✓ 规格校验通过
                                    </div>
                                  ) : (
                                    <div data-testid={`wb-customfurniture-validation-issues--${i}`}>
                                      <div
                                        className="wb-status-badge wb-status--error"
                                        style={{ marginBottom: 8 }}
                                      >
                                        ⚠ 发现 {detail.validation.issues.length} 个问题
                                      </div>
                                      {detail.validation.issues.map((iss, ii) => (
                                        <div
                                          key={ii}
                                          className="wb-furniture-line"
                                          data-testid={`wb-customfurniture-issue--${ii}`}
                                        >
                                          <span className="wb-furniture-line__name">
                                            {(iss.field as string) ?? '问题'}
                                          </span>
                                          <span className="wb-furniture-line__spec">
                                            {(iss.message as string) ?? JSON.stringify(iss)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  )
                                ) : (
                                  <div style={{ color: 'var(--text-muted)' }}>暂无校验结果</div>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
