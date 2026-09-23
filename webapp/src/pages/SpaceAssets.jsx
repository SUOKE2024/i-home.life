/**
 * SpaceAssetsPage — 空间资产台账（Phase 3 存量空间资产化，webapp 业主端）
 *
 * 对齐 console-src/src/pages/SpaceAssetsPage.tsx，面向业主/合作方提供
 * 自有存量空间（康养 / 疗愈 / 旅居 / 文旅 / 适老住宅）的台账登记与改造状态查看。
 *
 * 轻资产红线（CLAUDE.md 商业模式约束）：platform_role 恒为 service_provider，
 * 平台不持有房产、不做物业运营、不做房地产经纪；持有方字段不接受平台自填。
 * 改造状态机不可跳跃：assessed → operating 非法（须经 in_renovation → delivered）。
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Home, Plus, X } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { useApp } from '../lib/store'
import {
  getSpaceAssetEnums,
  getSpaceAssetSummary,
  getSpaceAssets,
  createSpaceAsset,
  transitionSpaceAssetStatus,
} from '../lib/api'

const CATEGORY_LABEL = {
  kangyang: '康养',
  healing: '疗愈',
  travel_residence: '旅居',
  cultural_tourism: '文旅',
  elderly_housing: '适老住宅',
}

const FORMAT_LABEL = {
  herb_food_courtyard: '药膳小院',
  forest_herbal_bath: '森林药浴',
  kangyang_study: '康养研学',
  seasonal_stay: '节气旅居',
  wellness_resort: '疗愈度假',
  cultural_site: '文旅点位',
  elderly_home: '适老住宅',
  other: '其他',
}

const STATUS_MAP = {
  pending_assessment: { tone: 'gray', label: '待评估' },
  assessed: { tone: 'sky', label: '已评估' },
  in_renovation: { tone: 'amber', label: '改造中' },
  delivered: { tone: 'green', label: '已交付' },
  operating: { tone: 'green', label: '运营中' },
  suspended: { tone: 'red', label: '暂停' },
}

const HOLDER_LABEL = {
  private: '个人业主',
  enterprise: '企业',
  collective: '集体',
  government: '政府/平台公司',
}

/* 改造状态机（对齐 app/services/space_asset_service.py _STATUS_TRANSITIONS）：
   assessed 不可直达 operating，必须经 in_renovation → delivered */
const NEXT_STATUSES = {
  pending_assessment: ['assessed', 'suspended'],
  assessed: ['in_renovation', 'pending_assessment', 'suspended'],
  in_renovation: ['delivered', 'assessed', 'suspended'],
  delivered: ['operating', 'suspended'],
  operating: ['suspended'],
  suspended: ['pending_assessment', 'assessed'],
}

const EMPTY_FORM = {
  name: '',
  asset_holder: '',
  city: '昆明市',
  asset_category: 'kangyang',
  business_format: 'seasonal_stay',
  holder_type: 'enterprise',
}

export default function SpaceAssetsPage() {
  const { toast } = useApp()
  const [enums, setEnums] = useState(null)
  const [summary, setSummary] = useState(null)
  const [assets, setAssets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterCategory, setFilterCategory] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const r = await getSpaceAssets({
      asset_category: filterCategory || undefined,
      renovation_status: filterStatus || undefined,
      limit: 100,
    })
    setLoading(false)
    if (!r.isSuccess) {
      setError(
        r.status === 503
          ? r.error || '空间资产台账未启用（space_asset_ledger_enabled=False）'
          : r.error || '台账加载失败',
      )
      return
    }
    setAssets(r.data || [])
    // 汇总与枚举为辅助信息，失败不影响台账主体（不伪装数据，仅不展示）
    const [s, e] = await Promise.all([getSpaceAssetSummary(), getSpaceAssetEnums()])
    if (s.isSuccess) setSummary(s.data || null)
    if (e.isSuccess) setEnums(e.data || null)
  }, [filterCategory, filterStatus])

  useEffect(() => {
    load()
  }, [load])

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!form.name.trim() || !form.asset_holder.trim()) {
      toast('资产名称与持有方为必填项', 'error')
      return
    }
    setSubmitting(true)
    const r = await createSpaceAsset({
      ...form,
      name: form.name.trim(),
      asset_holder: form.asset_holder.trim(),
      building_area_sqm: form.building_area_sqm ? Number(form.building_area_sqm) : undefined,
    })
    setSubmitting(false)
    if (!r.isSuccess) {
      toast(`登记失败：${r.error || '请重试'}`, 'error')
      return
    }
    toast(`已登记「${r.data?.name}」，智能化就绪度 ${r.data?.smart_readiness_score ?? 0} 分`, 'success')
    setForm(EMPTY_FORM)
    setFormOpen(false)
    load()
  }

  const transition = async (asset, next) => {
    const r = await transitionSpaceAssetStatus(asset.id, next)
    if (!r.isSuccess) {
      toast(`状态流转失败：${r.error || '请重试'}`, 'error')
      return
    }
    toast(`「${asset.name}」状态 → ${STATUS_MAP[next]?.label || next}`, 'success')
    load()
  }

  let body
  if (loading) {
    body = <Spinner label="台账加载中…" />
  } else if (error) {
    body = <ErrorBox message={error} onRetry={load} />
  } else if ((assets || []).length === 0) {
    body = (
      <Empty
        icon="🏘"
        message="台账暂无资产记录"
        description="点击「登记资产」录入第一处存量空间"
        actionLabel="登记资产"
        onAction={() => setFormOpen(true)}
      />
    )
  } else {
    body = (
      <div className="table-wrap">
        <table className="table">
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
            {(assets || []).map((a) => {
              const st = STATUS_MAP[a.renovation_status] || {
                tone: 'gray',
                label: a.renovation_status,
              }
              return (
                <tr key={a.id} data-testid={`space-asset-row--${a.id}`}>
                  <td>{a.name}</td>
                  <td>
                    {CATEGORY_LABEL[a.asset_category] || a.asset_category} /{' '}
                    {FORMAT_LABEL[a.business_format] || a.business_format}
                  </td>
                  <td className="dim">{a.city}</td>
                  <td>
                    {a.asset_holder}
                    <div className="dim" style={{ fontSize: 12 }}>
                      {HOLDER_LABEL[a.holder_type] || a.holder_type}
                    </div>
                  </td>
                  <td>
                    <Badge tone={st.tone}>{st.label}</Badge>
                  </td>
                  <td className="num">
                    {a.smart_readiness_score}
                    {a.smart_ready && (
                      <Badge tone="green">
                        <span style={{ marginLeft: 4 }}>就绪</span>
                      </Badge>
                    )}
                  </td>
                  <td>
                    {(NEXT_STATUSES[a.renovation_status] || []).map((s) => (
                      <button
                        key={s}
                        className="btn btn--ghost"
                        style={{ marginRight: 4 }}
                        type="button"
                        onClick={() => transition(a, s)}
                      >
                        → {STATUS_MAP[s]?.label || s}
                      </button>
                    ))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div>
      <div className="page-head">
        <h2>空间资产台账</h2>
        <div className="desc">
          云南区域存量空间（康养 / 疗愈 / 旅居 / 文旅 / 适老住宅）评估 → 改造 → 交付 → 运营全周期台账
        </div>
      </div>

      {/* 轻资产定位声明 */}
      <Card
        title="存量空间资产运营"
        sub={`平台角色：${summary?.platform_role || 'service_provider'}`}
        icon={<Home size={16} className="ico" />}
        style={{ marginBottom: 14 }}
      >
        <div className="dim" style={{ fontSize: 12.5 }}>
          {summary?.note ||
            '轻资产改造服务商：不持有房产、不做物业运营、不做房地产经纪。资产由业主/运营方持有，平台提供改造交付 + 智能运营 + 数据服务。'}
        </div>
      </Card>

      {summary && (
        <div className="stat-grid">
          <Stat label="资产总数" value={summary.total_assets} />
          <Stat label="总建筑面积（㎡）" value={summary.total_area_sqm} />
          <Stat label="平均智能化就绪度" value={summary.avg_smart_readiness} tone="sky" />
          <Stat label="已就绪" value={summary.smart_ready_count} tone="green" />
        </div>
      )}

      <div className="toolbar">
        <select
          className="select"
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          aria-label="按类别筛选"
          data-testid="space-assets-filter-category"
        >
          <option value="">全部类别</option>
          {(enums?.asset_categories || Object.keys(CATEGORY_LABEL)).map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c] || c}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          aria-label="按状态筛选"
          data-testid="space-assets-filter-status"
        >
          <option value="">全部状态</option>
          {(enums?.renovation_statuses || Object.keys(STATUS_MAP)).map((s) => (
            <option key={s} value={s}>
              {STATUS_MAP[s]?.label || s}
            </option>
          ))}
        </select>
        <button
          className={formOpen ? 'btn btn--ghost' : 'btn btn--primary'}
          type="button"
          onClick={() => setFormOpen(!formOpen)}
          data-testid="space-assets-toggle-form"
        >
          {formOpen ? <X size={15} /> : <Plus size={15} />}
          {formOpen ? '取消' : '登记资产'}
        </button>
      </div>

      {/* 登记表单（轻资产：持有方不得为平台自身） */}
      {formOpen && (
        <Card
          title="登记存量空间资产"
          sub="资产持有方不得为平台自身（轻资产服务商定位）"
          icon={<Home size={16} className="ico" />}
          style={{ marginBottom: 14 }}
        >
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field">
              <label htmlFor="sa-name">资产名称 *</label>
              <input
                id="sa-name"
                className="input"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                placeholder="如：大理·苍山节气旅居小院 A"
                maxLength={100}
              />
            </div>
            <div className="field">
              <label htmlFor="sa-holder">资产持有方 *（不得为平台自身）</label>
              <input
                id="sa-holder"
                className="input"
                value={form.asset_holder}
                onChange={(e) => setField('asset_holder', e.target.value)}
                placeholder="如：大理某文旅集团有限公司"
                maxLength={100}
              />
            </div>
            <div className="field">
              <label htmlFor="sa-city">所在城市</label>
              <input
                id="sa-city"
                className="input"
                value={form.city}
                onChange={(e) => setField('city', e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="sa-category">资产类别</label>
              <select
                id="sa-category"
                className="select"
                value={form.asset_category}
                onChange={(e) => setField('asset_category', e.target.value)}
              >
                {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sa-format">业态（对齐索克生活 lodge 口径）</label>
              <select
                id="sa-format"
                className="select"
                value={form.business_format}
                onChange={(e) => setField('business_format', e.target.value)}
              >
                {Object.entries(FORMAT_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sa-holder-type">持有方类型</label>
              <select
                id="sa-holder-type"
                className="select"
                value={form.holder_type}
                onChange={(e) => setField('holder_type', e.target.value)}
              >
                {Object.entries(HOLDER_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sa-area">建筑面积（㎡）</label>
              <input
                id="sa-area"
                className="input"
                type="number"
                min="0"
                value={form.building_area_sqm ?? ''}
                onChange={(e) =>
                  setField('building_area_sqm', e.target.value === '' ? '' : Number(e.target.value))
                }
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn--primary" type="submit" disabled={submitting}>
                {submitting ? '登记中…' : '确认登记'}
              </button>
              <button className="btn btn--ghost" type="button" onClick={() => setFormOpen(false)}>
                取消
              </button>
            </div>
          </form>
        </Card>
      )}

      {body}
    </div>
  )
}