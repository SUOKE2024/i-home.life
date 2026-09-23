import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ElderlyPackagesPage from './ElderlyPackages'
import { getQuickInstallPackages, precheckElderlySubsidy } from '../lib/api'

/**
 * ElderlyPackagesPage 单测（webapp 业主端，v1.17.0 政策适老化供给）
 *
 * 覆盖 CLAUDE.md「适老改造政策落地」红线：
 *   1. 仅渲染 elderly_theme=true 的适老套餐（非适老套餐不得误标为适老）
 *   2. 补贴预估按钮与结果必须标注「非资格认定」，warnings/disclaimer 原样展示
 *   3. 套餐目录不可用（503）→ 诚实报错，不伪造套餐
 */

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }))

vi.mock('../lib/store', () => ({ useApp: () => ({ toast }) }))
vi.mock('../lib/api', () => ({
  getQuickInstallPackages: vi.fn(),
  precheckElderlySubsidy: vi.fn(),
}))

const ELDERLY_PACKAGE = {
  package_code: 'PKG-ELDERLY-BATH',
  name: '适老卫浴改造（48h）',
  duration_hours: 48,
  fixed_price: 16800,
  dry_construction: true,
  zero_relocation: true,
  inclusions: ['坐便器旁扶手', '湿区防滑处理'],
  warranty: '整包 2 年质保',
  elderly_theme: true,
  target_occupant: ['elderly_living', 'nursing'],
  accessibility_standard: 'GB 50763-2012',
  subsidy_category: 'fall_prevention',
  elderly_design: { 尺寸适配: '门洞净宽 ≥ 800mm' },
}

const PLAIN_PACKAGE = {
  package_code: 'PKG-48H-KITCHEN',
  name: '48h 厨房快装',
  duration_hours: 48,
  fixed_price: 19800,
  dry_construction: true,
  zero_relocation: true,
  inclusions: ['干法橱柜定制'],
  warranty: '整包 2 年质保',
}

const PRECHECK = {
  policy_profile: 'national_baseline',
  policy_version: '2026-09-national-baseline',
  region: '昆明市',
  is_estimate: true,
  subsidy_rate: 0.15,
  max_subsidy_per_unit: null,
  source: '2026 年消费品以旧换新适老化补贴（公开报道口径）',
  disclaimer: '本结果为估算值，非补贴资格认定，实际以当地政策与主管部门核定为准。',
  items: [
    {
      name: '适老卫浴改造（48h）',
      category_label: '防跌倒安全防护',
      eligible: true,
      subsidy_amount: 2520,
      reason: null,
    },
  ],
  total_price: 16800,
  total_subsidy: 2520,
  net_payable: 14280,
  warnings: [
    '未接入 昆明市 官方补贴目录（本平台不内置地方细则）',
    '老年人年龄/失能等级等个人资格不参与本确定性判定',
  ],
}

beforeEach(() => {
  getQuickInstallPackages.mockResolvedValue({
    isSuccess: true,
    status: 200,
    data: [ELDERLY_PACKAGE, PLAIN_PACKAGE],
  })
  precheckElderlySubsidy.mockResolvedValue({ isSuccess: true, status: 200, data: PRECHECK })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('适老改造套餐 — 目录', () => {
  it('只渲染 elderly_theme=true 的套餐，非适老套餐不误标', async () => {
    render(<ElderlyPackagesPage />)

    await screen.findByText('适老卫浴改造（48h）')
    expect(screen.queryByText('48h 厨房快装')).toBeNull()
    // 适老元数据：无障碍标准 + 适老设计维度
    expect(screen.getByText(/GB 50763-2012/)).toBeTruthy()
    expect(screen.getByText(/尺寸适配/)).toBeTruthy()
  })

  it('目录不可用（503）→ 诚实报错，不伪造套餐', async () => {
    getQuickInstallPackages.mockResolvedValue({
      isSuccess: false,
      status: 503,
      error: '该功能未启用',
    })

    render(<ElderlyPackagesPage />)

    await screen.findByText(/partial_renovation 相关功能未启用/)
    expect(screen.queryByText('适老卫浴改造（48h）')).toBeNull()
  })
})

describe('适老改造套餐 — 补贴资格预检', () => {
  it('按钮与结果均标注「非资格认定」，warnings/disclaimer 原样展示', async () => {
    render(<ElderlyPackagesPage />)
    await screen.findByText('适老卫浴改造（48h）')

    const btn = screen.getByTestId('elderly-package-precheck--PKG-ELDERLY-BATH')
    expect(btn.textContent).toContain('非资格认定')

    fireEvent.change(screen.getByTestId('elderly-subsidy-region-input'), {
      target: { value: '昆明市' },
    })
    fireEvent.click(btn)

    await screen.findByText(/预估补贴/)
    const result = screen.getByTestId('elderly-package-subsidy--PKG-ELDERLY-BATH')
    expect(result.textContent).toContain('预估落地价')
    expect(result.textContent).toContain('非资格认定')
    expect(result.textContent).toContain('防跌倒安全防护')
    expect(result.textContent).toContain('官方补贴目录')
    expect(result.textContent).toContain('个人资格')
    expect(result.textContent).toContain('本结果为估算值，非补贴资格认定')

    await waitFor(() =>
      expect(precheckElderlySubsidy).toHaveBeenCalledWith({
        package_code: 'PKG-ELDERLY-BATH',
        region: '昆明市',
      }),
    )
  })

  it('预检不可用 → toast 报错，不展示预估结果', async () => {
    precheckElderlySubsidy.mockResolvedValue({
      isSuccess: false,
      status: 404,
      error: '该功能未启用',
    })

    render(<ElderlyPackagesPage />)
    await screen.findByText('适老卫浴改造（48h）')

    fireEvent.click(screen.getByTestId('elderly-package-precheck--PKG-ELDERLY-BATH'))

    await waitFor(() => expect(toast).toHaveBeenCalledWith('该功能未启用', 'error'))
    expect(screen.queryByTestId('elderly-package-subsidy--PKG-ELDERLY-BATH')).toBeNull()
  })
})