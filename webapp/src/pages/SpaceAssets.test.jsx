import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SpaceAssetsPage from './SpaceAssets'
import {
  getSpaceAssets,
  getSpaceAssetSummary,
  getSpaceAssetEnums,
  createSpaceAsset,
  transitionSpaceAssetStatus,
} from '../lib/api'

/**
 * SpaceAssetsPage 单测（webapp 业主端，Phase 3 存量空间资产化）
 *
 * 覆盖两条红线与一条状态机契约：
 *   1. 轻资产定位声明（platform_role 恒为 service_provider，不持有房产）
 *   2. 改造状态机不可跳跃 —— assessed 行不得出现「运营中」流转按钮
 *   3. 台账未启用（503）诚实报错，不回退空态伪装「无数据」
 */

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }))

vi.mock('../lib/store', () => ({ useApp: () => ({ toast }) }))
vi.mock('../lib/api', () => ({
  getSpaceAssets: vi.fn(),
  getSpaceAssetSummary: vi.fn(),
  getSpaceAssetEnums: vi.fn(),
  createSpaceAsset: vi.fn(),
  transitionSpaceAssetStatus: vi.fn(),
}))

const ASSETS = [
  {
    id: 'a1',
    name: '大理·苍山节气旅居小院 A',
    city: '大理白族自治州',
    asset_category: 'travel_residence',
    business_format: 'seasonal_stay',
    asset_holder: '大理某文旅集团有限公司',
    holder_type: 'enterprise',
    renovation_status: 'assessed',
    smart_ready: false,
    smart_readiness_score: 45,
  },
  {
    id: 'a2',
    name: '昆明·滇池康养研学中心',
    city: '昆明市',
    asset_category: 'kangyang',
    business_format: 'kangyang_study',
    asset_holder: '云南某康养产业有限公司',
    holder_type: 'enterprise',
    renovation_status: 'operating',
    smart_ready: true,
    smart_readiness_score: 78,
  },
]

beforeEach(() => {
  getSpaceAssets.mockResolvedValue({ isSuccess: true, status: 200, data: ASSETS })
  getSpaceAssetSummary.mockResolvedValue({
    isSuccess: true,
    status: 200,
    data: {
      total_assets: 2,
      total_area_sqm: 420,
      avg_smart_readiness: 61.5,
      smart_ready_count: 1,
      platform_role: 'service_provider',
      note: null,
    },
  })
  getSpaceAssetEnums.mockResolvedValue({
    isSuccess: true,
    status: 200,
    data: { asset_categories: ['kangyang', 'elderly_housing'], renovation_statuses: ['assessed'] },
  })
  transitionSpaceAssetStatus.mockResolvedValue({
    isSuccess: true,
    status: 200,
    data: { ...ASSETS[0], renovation_status: 'in_renovation' },
  })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('空间资产台账 — 轻资产定位与汇总', () => {
  it('展示轻资产定位声明（service_provider）+ 资产组合汇总', async () => {
    render(<SpaceAssetsPage />)

    await screen.findByText('大理·苍山节气旅居小院 A')

    expect(screen.getByText(/不持有房产/)).toBeTruthy()
    expect(screen.getByText(/不做物业运营/)).toBeTruthy()
    expect(screen.getByText('平台角色：service_provider')).toBeTruthy()

    expect(screen.getByText('资产总数')).toBeTruthy()
    expect(screen.getByText('总建筑面积（㎡）')).toBeTruthy()
    expect(screen.getByText('平均智能化就绪度')).toBeTruthy()
  })
})

describe('空间资产台账 — 改造状态机不可跳跃', () => {
  it('assessed 行流转按钮不含「运营中」，operating 行仅可暂停', async () => {
    render(<SpaceAssetsPage />)
    await screen.findByText('大理·苍山节气旅居小院 A')

    const assessedRow = screen.getByTestId('space-asset-row--a1')
    const actions = Array.from(assessedRow.querySelectorAll('button')).map((b) => b.textContent)
    expect(actions).toEqual(['→ 改造中', '→ 待评估', '→ 暂停'])
    expect(assessedRow.textContent).not.toContain('运营中')

    const operatingRow = screen.getByTestId('space-asset-row--a2')
    expect(Array.from(operatingRow.querySelectorAll('button')).map((b) => b.textContent)).toEqual([
      '→ 暂停',
    ])
    expect(operatingRow.textContent).toContain('运营中')
  })

  it('流转请求 → 调用 state 端点并提示结果、刷新台账', async () => {
    render(<SpaceAssetsPage />)
    await screen.findByText('大理·苍山节气旅居小院 A')

    const row = screen.getByTestId('space-asset-row--a1')
    fireEvent.click(within(row).getByText('→ 改造中'))

    await waitFor(() =>
      expect(transitionSpaceAssetStatus).toHaveBeenCalledWith('a1', 'in_renovation'),
    )
    expect(toast).toHaveBeenCalledWith(expect.stringContaining('状态 → 改造中'), 'success')
    // 初始 1 次 + 流转后刷新 1 次
    expect(getSpaceAssets).toHaveBeenCalledTimes(2)
  })
})

describe('空间资产台账 — 诚实降级', () => {
  it('台账未启用（503）→ 明示错误，不回退空态伪装有数据', async () => {
    getSpaceAssets.mockResolvedValue({
      isSuccess: false,
      status: 503,
      error: '空间资产台账未启用（space_asset_ledger_enabled=False）',
    })

    render(<SpaceAssetsPage />)

    await screen.findByText(/space_asset_ledger_enabled=False/)
    expect(screen.queryByText(/台账暂无资产记录/)).toBeNull()
  })

  it('登记必填校验：名称/持有方为空 → 拦截提交且不发请求', async () => {
    render(<SpaceAssetsPage />)
    await screen.findByText('大理·苍山节气旅居小院 A')

    fireEvent.click(screen.getByTestId('space-assets-toggle-form'))
    fireEvent.click(screen.getByText('确认登记'))

    expect(toast).toHaveBeenCalledWith('资产名称与持有方为必填项', 'error')
    expect(createSpaceAsset).not.toHaveBeenCalled()
  })
})
