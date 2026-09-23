/**
 * SpaceAssetsPage — 空间资产台账（Phase 3 存量空间资产化，v1.16.0）
 *
 * 承载云南区域存量空间资源（康养 / 疗愈 / 旅居 / 文旅 / 适老住宅）的
 * 「资产评估 → AI 智能化改造 → 交付 → 运营指标」全周期台账。
 *
 * 轻资产约束（CLAUDE.md 商业模式红线）：platform_role 恒为 service_provider，
 * 资产持有方必须为外部主体，页面不接受平台自持录入。
 *
 * API（对齐 app/api/space_assets.py）：
 *   GET    /api/space-assets/enums | /summary | / | /{id} | /{id}/readiness
 *   POST   /api/space-assets | /{id}/status
 *   PATCH  /api/space-assets/{id}
 *   DELETE /api/space-assets/{id}
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  SpaceAsset,
  SpaceAssetCreateInput,
  SpaceAssetEnums,
  SpaceAssetSummary,
} from '../types/domain';

const CATEGORY_LABEL: Record<string, string> = {
  kangyang: '康养',
  healing: '疗愈',
  travel_residence: '旅居',
  cultural_tourism: '文旅',
  elderly_housing: '适老住宅',
};

const FORMAT_LABEL: Record<string, string> = {
  herb_food_courtyard: '药膳小院',
  forest_herbal_bath: '森林药浴',
  kangyang_study: '康养研学',
  seasonal_stay: '节气旅居',
  wellness_resort: '疗愈度假',
  cultural_site: '文旅点位',
  elderly_home: '适老住宅',
  other: '其他',
};

const STATUS_LABEL: Record<string, string> = {
  pending_assessment: '待评估',
  assessed: '已评估',
  in_renovation: '改造中',
  delivered: '已交付',
  operating: '运营中',
  suspended: '暂停',
};

const STATUS_TONE: Record<string, string> = {
  pending_assessment: 'wb-status-chip--muted',
  assessed: 'wb-status-chip--info',
  in_renovation: 'wb-status-chip--warning',
  delivered: 'wb-status-chip--success',
  operating: 'wb-status-chip--success',
  suspended: 'wb-status-chip--danger',
};

const HOLDER_LABEL: Record<string, string> = {
  private: '个人业主',
  enterprise: '企业',
  collective: '集体',
  government: '政府/平台公司',
};

const EMPTY_FORM: SpaceAssetCreateInput = {
  name: '',
  asset_holder: '',
  city: '昆明市',
  asset_category: 'kangyang',
  business_format: 'seasonal_stay',
  holder_type: 'enterprise',
};

export default function SpaceAssetsPage() {
  const navigate = useNavigate();
  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState<SpaceAssetCreateInput>(EMPTY_FORM);
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const { data: enums } = useAsync<SpaceAssetEnums | null>(async () => {
    const r = await apiClient.getSpaceAssetEnums<SpaceAssetEnums>();
    return r.isSuccess && r.data ? r.data : null;
  }, []);

  const { data: summary, reload: reloadSummary } = useAsync<SpaceAssetSummary | null>(
    async () => {
      const r = await apiClient.getSpaceAssetSummary<SpaceAssetSummary>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
      return r.data;
    },
    [],
  );

  const {
    data: assets,
    loading,
    error,
    reload,
  } = useAsync<SpaceAsset[] | null>(
    async () => {
      const r = await apiClient.getSpaceAssets<SpaceAsset[]>({
        asset_category: filterCategory || undefined,
        renovation_status: filterStatus || undefined,
        limit: 100,
      });
      if (!r.isSuccess || !r.data) {
        const msg =
          r.status === 503
            ? '空间资产台账未启用（space_asset_ledger_enabled=False）'
            : (r.error ?? `HTTP ${r.status}`);
        throw new Error(msg);
      }
      return r.data;
    },
    [filterCategory, filterStatus],
  );

  // 注意：此处不清空 notice —— 登记/流转成功提示紧接着就会调用本函数刷新，
  // 在此清空会把成功反馈自身抹除（手动「刷新」入口单独清空）。
  const refreshAll = async () => {
    await Promise.all([reload(), reloadSummary()]);
  };

  const handleCreate = async () => {
    if (!form.name.trim() || !form.asset_holder.trim()) {
      setNotice('资产名称与持有方为必填项');
      return;
    }
    setSubmitting(true);
    setNotice(null);
    const r = await apiClient.createSpaceAsset<SpaceAsset>(form);
    setSubmitting(false);
    if (!r.isSuccess) {
      setNotice(`登记失败：${r.error ?? `HTTP ${r.status}`}`);
      return;
    }
    setForm(EMPTY_FORM);
    setFormOpen(false);
    setNotice(`已登记「${r.data?.name}」，智能化就绪度 ${r.data?.smart_readiness_score ?? 0} 分`);
    await refreshAll();
  };

  const handleTransition = async (asset: SpaceAsset, next: string) => {
    setNotice(null);
    const r = await apiClient.transitionSpaceAssetStatus<SpaceAsset>(asset.id, next);
    if (!r.isSuccess) {
      setNotice(`状态流转失败：${r.error ?? `HTTP ${r.status}`}`);
      return;
    }
    setNotice(`「${asset.name}」状态 → ${STATUS_LABEL[next] ?? next}`);
    await refreshAll();
  };

  const nextStatuses = (current: string): string[] => {
    const map: Record<string, string[]> = {
      pending_assessment: ['assessed', 'suspended'],
      assessed: ['in_renovation', 'pending_assessment', 'suspended'],
      in_renovation: ['delivered', 'assessed', 'suspended'],
      delivered: ['operating', 'suspended'],
      operating: ['suspended'],
      suspended: ['pending_assessment', 'assessed'],
    };
    return map[current] ?? [];
  };

  const setField = <K extends keyof SpaceAssetCreateInput>(key: K, value: SpaceAssetCreateInput[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-space-assets-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🏘 空间资产台账</div>
        </div>

        <div className="wb-page-body">
          {/* 轻资产定位声明 */}
          <div className="wb-smart-card" data-testid="wb-space-assets-positioning">
            <div className="wb-smart-card__head">
              <div className="wb-smart-card__room">存量空间资产运营</div>
              <span className="wb-status-chip wb-status-chip--info">
                平台角色：{summary?.platform_role ?? 'service_provider'}
              </span>
            </div>
            <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
              {summary?.note ??
                '轻资产改造服务商：不持有房产、不做物业运营、不做房地产经纪。资产由业主/运营方持有，平台提供改造交付 + 智能运营 + 数据服务。'}
            </div>
          </div>

          {/* 组合汇总 */}
          {summary && (
            <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-space-assets-summary">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">资产组合汇总</div>
                <span className="wb-status-chip wb-status-chip--success">
                  共 {summary.total_assets} 处
                </span>
              </div>
              <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                总建筑面积 {summary.total_area_sqm} ㎡ · 平均智能化就绪度{' '}
                {summary.avg_smart_readiness} 分 · 已就绪 {summary.smart_ready_count} 处
              </div>
              {summary.total_assets > 0 && (
                <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                  按类别：
                  {Object.entries(summary.by_category).map(([k, v]) => (
                    <span key={k} className="wb-status-chip wb-status-chip--muted" style={{ marginLeft: 4 }}>
                      {CATEGORY_LABEL[k] ?? k} {v}
                    </span>
                  ))}
                </div>
              )}
              {summary.total_assets > 0 && (
                <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                  按状态：
                  {Object.entries(summary.by_status).map(([k, v]) => (
                    <span key={k} className="wb-status-chip wb-status-chip--info" style={{ marginLeft: 4 }}>
                      {STATUS_LABEL[k] ?? k} {v}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 筛选 + 登记入口 */}
          <div className="wb-section-label" style={{ marginTop: 12 }}>
            台账明细
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select
              className="wb-input wb-input--sm"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              aria-label="按类别筛选"
              data-testid="wb-space-assets-filter-category"
            >
              <option value="">全部类别</option>
              {(enums?.asset_categories ?? Object.keys(CATEGORY_LABEL)).map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c] ?? c}
                </option>
              ))}
            </select>
            <select
              className="wb-input wb-input--sm"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              aria-label="按状态筛选"
              data-testid="wb-space-assets-filter-status"
            >
              <option value="">全部状态</option>
              {(enums?.renovation_statuses ?? Object.keys(STATUS_LABEL)).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s] ?? s}
                </option>
              ))}
            </select>
            <button
              className="wb-btn wb-btn--sm"
              type="button"
              onClick={() => setFormOpen((v) => !v)}
              data-testid="wb-space-assets-toggle-form"
            >
              {formOpen ? '收起登记' : '+ 登记资产'}
            </button>
            <button
              className="wb-btn wb-btn--sm wb-btn--ghost"
              type="button"
              onClick={() => {
                setNotice(null);
                refreshAll();
              }}
            >
              刷新
            </button>
          </div>

          {notice && (
            <div className="wb-smart-card__meta" style={{ marginTop: 8 }} data-testid="wb-space-assets-notice">
              {notice}
            </div>
          )}

          {/* 登记表单 */}
          {formOpen && (
            <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-space-assets-form">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">登记存量空间资产</div>
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-name">资产名称 *</label>
                <input
                  id="sa-name"
                  className="wb-input"
                  value={form.name}
                  onChange={(e) => setField('name', e.target.value)}
                  placeholder="如：大理·苍山节气旅居小院 A"
                />
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-holder">
                  资产持有方 *（不得为平台自身）
                </label>
                <input
                  id="sa-holder"
                  className="wb-input"
                  value={form.asset_holder}
                  onChange={(e) => setField('asset_holder', e.target.value)}
                  placeholder="如：大理某文旅集团有限公司"
                />
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-city">所在城市</label>
                <input
                  id="sa-city"
                  className="wb-input"
                  value={form.city ?? ''}
                  onChange={(e) => setField('city', e.target.value)}
                />
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-category">资产类别</label>
                <select
                  id="sa-category"
                  className="wb-input"
                  value={form.asset_category ?? 'kangyang'}
                  onChange={(e) => setField('asset_category', e.target.value)}
                >
                  {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-format">
                  业态（对齐索克生活 lodge 口径）
                </label>
                <select
                  id="sa-format"
                  className="wb-input"
                  value={form.business_format ?? 'other'}
                  onChange={(e) => setField('business_format', e.target.value)}
                >
                  {Object.entries(FORMAT_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-holder-type">持有方类型</label>
                <select
                  id="sa-holder-type"
                  className="wb-input"
                  value={form.holder_type ?? 'enterprise'}
                  onChange={(e) => setField('holder_type', e.target.value)}
                >
                  {Object.entries(HOLDER_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-area">建筑面积（㎡）</label>
                <input
                  id="sa-area"
                  className="wb-input wb-input--num"
                  type="number"
                  min={0}
                  value={form.building_area_sqm ?? ''}
                  onChange={(e) =>
                    setField('building_area_sqm', e.target.value === '' ? undefined : Number(e.target.value))
                  }
                />
              </div>
              <div className="wb-field">
                <label className="wb-field__label" htmlFor="sa-notes">备注</label>
                <input
                  id="sa-notes"
                  className="wb-input"
                  value={form.notes ?? ''}
                  onChange={(e) => setField('notes', e.target.value)}
                />
              </div>
              <button
                className="wb-btn"
                type="button"
                onClick={handleCreate}
                disabled={submitting}
                data-testid="wb-space-assets-submit"
              >
                {submitting ? '登记中…' : '确认登记'}
              </button>
            </div>
          )}

          {/* 列表 */}
          {loading && (
            <div className="wb-state" data-testid="wb-space-assets-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载台账…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-space-assets-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-btn wb-btn--sm" onClick={reload} type="button">
                重试
              </button>
            </div>
          )}

          {assets && !loading && assets.length === 0 && (
            <div className="wb-state" data-testid="wb-space-assets-empty">
              <div className="wb-state__icon">🏘</div>
              <div>台账暂无资产记录，点击「+ 登记资产」录入第一处存量空间</div>
            </div>
          )}

          {assets && assets.length > 0 && (
            <div className="table-wrap" style={{ marginTop: 8 }}>
              <table className="wb-table" data-testid="wb-space-assets-table">
                <thead>
                  <tr>
                    <th>资产名称</th>
                    <th>类别 / 业态</th>
                    <th>城市</th>
                    <th>持有方</th>
                    <th>改造状态</th>
                    <th>就绪度</th>
                    <th>流转</th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((a) => (
                    <tr key={a.id} data-testid={`wb-space-asset-row--${a.id}`}>
                      <td>{a.name}</td>
                      <td>
                        {CATEGORY_LABEL[a.asset_category] ?? a.asset_category} /{' '}
                        {FORMAT_LABEL[a.business_format] ?? a.business_format}
                      </td>
                      <td>{a.city}</td>
                      <td>
                        {a.asset_holder}
                        <div className="wb-smart-card__meta">
                          {HOLDER_LABEL[a.holder_type] ?? a.holder_type}
                        </div>
                      </td>
                      <td>
                        <span className={`wb-status-chip ${STATUS_TONE[a.renovation_status] ?? 'wb-status-chip--muted'}`}>
                          {STATUS_LABEL[a.renovation_status] ?? a.renovation_status}
                        </span>
                      </td>
                      <td>
                        {a.smart_readiness_score}
                        {a.smart_ready && (
                          <span className="wb-status-chip wb-status-chip--success" style={{ marginLeft: 4 }}>
                            就绪
                          </span>
                        )}
                      </td>
                      <td>
                        {nextStatuses(a.renovation_status).map((s) => (
                          <button
                            key={s}
                            className="wb-btn wb-btn--sm wb-btn--ghost"
                            style={{ marginRight: 4 }}
                            type="button"
                            onClick={() => handleTransition(a, s)}
                          >
                            → {STATUS_LABEL[s] ?? s}
                          </button>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
