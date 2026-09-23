/**
 * ElderlyPackagesPage — 适老改造套餐 + 补贴资格预检（v1.17.0 政策适老化供给）
 *
 * 对齐 console-src/src/pages/ElderlyAdaptationPage.tsx 的「适老套餐」区块，
 * 面向业主端提供可售套餐目录（一口价 + 干法施工 + 0 搬家）与补贴预估。
 *
 * 红线（CLAUDE.md「适老改造政策落地」）：
 *   1. 仅渲染 elderly_theme=true 的适老套餐，非适老套餐不得误标
 *   2. 补贴预估恒为估算值（is_estimate=true），按钮与结果必须标注「非资格认定」
 *   3. 平台不内置地方官方目录，warnings 原样展示（地方口径以主管部门核定为准）
 */
import React, { useCallback, useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { Card, Badge, Spinner, Empty, ErrorBox } from '../components/ui'
import { useApp } from '../lib/store'
import { getQuickInstallPackages, precheckElderlySubsidy } from '../lib/api'

/* 居住类型枚举（对齐 app/services/elderly_adaptation_service.py occupant_type） */
const OCCUPANT_LABELS = {
  elderly_living: '老人独立生活',
  semi_selfcare: '半自理',
  nursing: '失能护理',
  family: '多代同堂',
}

function fmtMoney(v) {
  return `¥${Number(v ?? 0).toLocaleString('zh-CN')}`
}

export default function ElderlyPackagesPage() {
  const { toast } = useApp()
  const [packages, setPackages] = useState([]) // 仅适老套餐
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [region, setRegion] = useState('') // 补贴地区（仅用于标注口径）
  const [precheckingCode, setPrecheckingCode] = useState(null)
  const [prechecks, setPrechecks] = useState({}) // package_code → 预检结果

  const loadPackages = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    const r = await getQuickInstallPackages()
    setLoading(false)
    if (!r.isSuccess) {
      setLoadError(
        r.status === 404 || r.status === 503
          ? `${r.error || '套餐目录不可用'}（partial_renovation 相关功能未启用）`
          : r.error || '套餐目录加载失败',
      )
      return
    }
    // 只展示适老套餐，非适老套餐（如 48h 厨房快装）不误标为适老
    setPackages((r.data || []).filter((p) => p.elderly_theme === true))
  }, [])

  useEffect(() => {
    loadPackages()
  }, [loadPackages])

  /* 补贴预估：确定性估算，非资格认定 */
  const runPrecheck = async (packageCode) => {
    setPrecheckingCode(packageCode)
    const r = await precheckElderlySubsidy({
      package_code: packageCode,
      region: region.trim() || undefined,
    })
    setPrecheckingCode(null)
    if (!r.isSuccess) {
      toast(r.error || '补贴预检不可用（elderly_subsidy_precheck_enabled 可能为 False）', 'error')
      return
    }
    setPrechecks((prev) => ({ ...prev, [packageCode]: r.data }))
  }

  let body
  if (loading) {
    body = <Spinner label="适老套餐加载中…" />
  } else if (loadError) {
    body = <ErrorBox message={loadError} onRetry={loadPackages} />
  } else if (packages.length === 0) {
    body = (
      <Empty
        icon="🧓"
        message="暂无适老改造套餐"
        description="套餐目录为空，或相关功能未启用（partial_renovation_enabled）"
      />
    )
  } else {
    body = packages.map((p) => {
      const pre = prechecks[p.package_code]
      return (
        <Card
          key={p.package_code}
          title={p.name}
          sub={`${p.duration_hours}h 交付 · 一口价 ${fmtMoney(p.fixed_price)}`}
          icon={<ShieldCheck size={16} className="ico" />}
          actions={
            <div style={{ display: 'flex', gap: 6 }}>
              {p.dry_construction && <Badge tone="sky">干法施工</Badge>}
              {p.zero_relocation && <Badge tone="green">0 搬家</Badge>}
            </div>
          }
          style={{ marginBottom: 14 }}
        >
          <div className="dim" style={{ fontSize: 12.5, marginBottom: 8 }}>
            含 {(p.inclusions || []).length} 项
            {p.accessibility_standard ? ` · 无障碍标准 ${p.accessibility_standard}` : ''}
            {p.subsidy_category ? ` · 补贴品类 ${p.subsidy_category}` : ''}
          </div>

          {/* 适老设计维度：只声明适用维度，不为凑齐四维编造能力 */}
          {Object.entries(p.elderly_design || {}).map(([dim, desc]) => (
            <div className="dim" key={dim} style={{ fontSize: 12.5 }}>
              ♿ {dim}：{desc}
            </div>
          ))}

          <div className="dim" style={{ fontSize: 12.5, marginTop: 6 }}>
            适用：
            {(p.target_occupant || []).map((t) => OCCUPANT_LABELS[t] || t).join(' / ') || '—'}
          </div>
          {p.warranty && (
            <div className="dim" style={{ fontSize: 12.5 }}>
              质保：{p.warranty}
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <button
              className="btn btn--primary"
              type="button"
              onClick={() => runPrecheck(p.package_code)}
              disabled={precheckingCode === p.package_code}
              data-testid={`elderly-package-precheck--${p.package_code}`}
            >
              {precheckingCode === p.package_code ? '预检中…' : '💰 补贴预估（非资格认定）'}
            </button>
          </div>

          {pre && (
            <div style={{ marginTop: 10 }} data-testid={`elderly-package-subsidy--${p.package_code}`}>
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
                <span>一口价 {fmtMoney(pre.total_price)}</span>
                <span>预估补贴 {fmtMoney(pre.total_subsidy)}</span>
                <span>预估落地价 {fmtMoney(pre.net_payable)}</span>
                <Badge tone="amber">预估 · 非资格认定</Badge>
              </div>
              {(pre.items || []).map((it, j) => (
                <div className="dim" key={`${it.name}-${j}`} style={{ fontSize: 12.5, marginTop: 4 }}>
                  {it.eligible ? '✅' : '—'} {it.name}（{it.category_label}） · 补贴{' '}
                  {fmtMoney(it.subsidy_amount)}
                  {it.reason ? ` · ${it.reason}` : ''}
                </div>
              ))}
              {/* 诚实标注：地方目录未接入 / 单件上限未知 / 个人资格不参与判定 */}
              {(pre.warnings || []).map((w) => (
                <div className="dim" key={w} style={{ fontSize: 12, marginTop: 4 }}>
                  ⚠ {w}
                </div>
              ))}
              <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>
                {pre.disclaimer}
              </div>
              <div className="dim" style={{ fontSize: 12 }}>
                口径来源：{pre.source}（{pre.policy_version}）
              </div>
            </div>
          )}
        </Card>
      )
    })
  }

  return (
    <div>
      <div className="page-head">
        <h2>适老改造套餐</h2>
        <div className="desc">
          八部门《促进智能家居消费行动方案》政策口径 —— 适老化设计 + 一口价快装（干法施工 · 0 搬家）
        </div>
      </div>

      <div className="toolbar">
        <div className="field" style={{ marginBottom: 0 }}>
          <label htmlFor="elderly-region">补贴地区（选填，仅用于标注口径）</label>
          <input
            id="elderly-region"
            className="input"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="如：昆明市"
            data-testid="elderly-subsidy-region-input"
          />
        </div>
      </div>

      <div className="dim" style={{ fontSize: 12.5, marginBottom: 12 }}>
        ⚠ 补贴预估为平台确定性估算值，非补贴资格认定；平台不内置地方官方补贴目录，实际以当地政策与主管部门核定为准。
      </div>

      {body}
    </div>
  )
}