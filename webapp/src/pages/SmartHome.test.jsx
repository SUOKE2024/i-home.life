import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SmartHomePage from './SmartHome'

/**
 * SmartHomePage 单测（webapp 业主端，智能家居生态全链路接入契约）
 *
 * 覆盖后端权威契约（app/api/smart_home.py + app/schemas/smart_home.py）：
 *   1. 新建方案走 POST /api/smart-home/schemes（不存在 POST /schemes/project/{id}），
 *      体含 project_id + room_name，且不得出现后端没有的 scheme_name/description
 *   2. 方案列表走 GET /api/smart-home/schemes/project/{project_id}
 *   3. 后端错误（422/500）须透出 detail，不得伪造成功或空数据
 *
 * 本文件不 mock ../lib/api，直接打桩全局 fetch，以便真实断言请求路径与方法。
 */

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }))

vi.mock('../lib/store', () => ({ useApp: () => ({ toast }) }))

const PROJECT = { id: 'p1', name: '演示项目·昆明' }

const SCHEME = {
  id: 's1',
  project_id: 'p1',
  room_name: '客厅',
  room_type: 'living_room',
  protocol: 'zigbee',
  hub_brand: 'xiaomi',
  device_count: 3,
  total_price: 1280,
  status: 'active',
  notes: '全屋灯光联动',
  created_at: '2026-09-20T10:00:00',
  updated_at: '2026-09-20T10:00:00',
}

const originalFetch = globalThis.fetch

/** request() 只消费 ok/status/json 三个字段 */
const jsonRes = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

/**
 * 打桩 fetch 并记录调用：{ url, method, body(已解析) }。
 * overrides 可覆盖默认路由（如模拟 422/500）。
 */
function installFetch(overrides = {}) {
  const calls = []
  const routes = {
    '/api/projects': () => jsonRes(200, [PROJECT]),
    '/api/smart-home/schemes/project/p1': () => jsonRes(200, [SCHEME]),
    '/api/smart-home/schemes': () => jsonRes(201, { ...SCHEME, id: 's2', room_name: '主卧' }),
    ...overrides,
  }
  globalThis.fetch = vi.fn(async (url, options = {}) => {
    calls.push({
      url,
      method: options.method || 'GET',
      body: options.body ? JSON.parse(options.body) : undefined,
    })
    const handler = routes[url]
    if (!handler) throw new Error(`未打桩的请求：${options.method || 'GET'} ${url}`)
    return handler(options)
  })
  return calls
}

const listCalls = (calls) => calls.filter((c) => c.url === '/api/smart-home/schemes/project/p1')
const postCalls = (calls) => calls.filter((c) => c.method === 'POST')

/** 渲染 → 选中项目 → 等待方案列表请求发出 */
async function renderWithProject(calls) {
  render(<SmartHomePage />)
  fireEvent.change(await screen.findByTestId('smart-home-project-select'), {
    target: { value: 'p1' },
  })
  await waitFor(() => expect(listCalls(calls)).toHaveLength(1))
  return calls
}

beforeEach(() => {
  globalThis.fetch = vi.fn(async () => {
    throw new Error('测试未安装 fetch 打桩')
  })
})

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.clearAllMocks()
})

describe('智能家居方案 — 新建方案请求契约', () => {
  it('POST /api/smart-home/schemes，体含 project_id + room_name，不含 scheme_name/description', async () => {
    const calls = installFetch()
    await renderWithProject(calls)

    fireEvent.click(screen.getByTestId('smart-home-toggle-form'))
    fireEvent.change(screen.getByTestId('smart-home-room-name'), { target: { value: '主卧' } })
    fireEvent.change(screen.getByTestId('smart-home-room-type'), { target: { value: 'bedroom' } })
    fireEvent.change(screen.getByTestId('smart-home-notes'), { target: { value: '床头调光' } })
    fireEvent.click(screen.getByTestId('smart-home-scheme-submit'))

    await waitFor(() => expect(postCalls(calls)).toHaveLength(1))
    const post = postCalls(calls)[0]
    expect(post.url).toBe('/api/smart-home/schemes')
    expect(post.body).toEqual({
      project_id: 'p1',
      room_name: '主卧',
      room_type: 'bedroom',
      notes: '床头调光',
    })
    // 后端 SmartHomeSchemeCreate 无这两个字段（原实现会 405 + 语义错位）
    expect(Object.keys(post.body)).not.toContain('scheme_name')
    expect(Object.keys(post.body)).not.toContain('description')
    // 生态由后端按项目已配置凭据自动解析，前端不得硬编码 ecosystem
    expect(Object.keys(post.body)).not.toContain('ecosystem')
    // 不得再打到不存在的 POST /schemes/project/{id}
    expect(calls.filter((c) => c.method === 'POST' && c.url.includes('/project/'))).toHaveLength(0)
  })

  it('创建成功后刷新列表并提示（不静默）', async () => {
    const calls = installFetch()
    await renderWithProject(calls)

    fireEvent.click(screen.getByTestId('smart-home-toggle-form'))
    fireEvent.change(screen.getByTestId('smart-home-room-name'), { target: { value: '主卧' } })
    fireEvent.click(screen.getByTestId('smart-home-scheme-submit'))

    await waitFor(() => expect(toast).toHaveBeenCalledWith('已创建「主卧」智能方案', 'success'))
    // 初始 1 次 + 创建后刷新 1 次
    await waitFor(() => expect(listCalls(calls)).toHaveLength(2))
    // 表单关闭并复位
    expect(screen.queryByTestId('smart-home-room-name')).toBeNull()
  })

  it('房间名称为空 → 拦截提交并提示，不发请求', async () => {
    const calls = installFetch()
    await renderWithProject(calls)

    fireEvent.click(screen.getByTestId('smart-home-toggle-form'))
    fireEvent.click(screen.getByTestId('smart-home-scheme-submit'))

    expect(toast).toHaveBeenCalledWith('请填写房间名称', 'error')
    expect(postCalls(calls)).toHaveLength(0)
  })

  it('房间类型下拉取值 = 后端受限枚举（多一个即写库约束错误，少一个则能力缺失）', async () => {
    const calls = installFetch()
    await renderWithProject(calls)

    fireEvent.click(screen.getByTestId('smart-home-toggle-form'))
    const options = Array.from(screen.getByTestId('smart-home-room-type').options).map((o) => o.value)
    // 对齐 app/models/smart_home.py:chk_smart_home_scheme_room_type
    expect(options).toEqual([
      'living_room',
      'bedroom',
      'kitchen',
      'bathroom',
      'entrance',
      'study',
    ])
  })
})

describe('智能家居方案 — 列表读取契约', () => {
  it('按项目走 GET /schemes/project/{id}，渲染 room_name/notes（不再依赖 scheme_name/description）', async () => {
    const calls = installFetch()
    await renderWithProject(calls)

    await screen.findByText('全屋灯光联动')
    expect(listCalls(calls)[0].method).toBe('GET')
    expect(screen.getByText('房间名称')).toBeTruthy()
    expect(screen.getByText('备注')).toBeTruthy()

    const row = screen.getByTestId('smart-home-scheme-row--s1')
    expect(row.textContent).toContain('客厅')
    expect(row.textContent).toContain('3')
    expect(row.textContent).toContain('启用中')
    expect(row.textContent).toContain('全屋灯光联动')
    // 未选中项目时不发方案请求
    expect(calls.filter((c) => c.url.startsWith('/api/smart-home'))).toHaveLength(1)
  })
})

describe('智能家居方案 — 诚实降级', () => {
  it('创建返回 422 → toast 透出 detail，不伪造成功、表单保持打开', async () => {
    const calls = installFetch({
      '/api/smart-home/schemes': () =>
        jsonRes(422, {
          detail: [{ type: 'missing', loc: ['body', 'room_name'], msg: 'Field required' }],
        }),
    })
    await renderWithProject(calls)

    fireEvent.click(screen.getByTestId('smart-home-toggle-form'))
    fireEvent.change(screen.getByTestId('smart-home-room-name'), { target: { value: '主卧' } })
    fireEvent.click(screen.getByTestId('smart-home-scheme-submit'))

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.stringContaining('room_name: Field required'),
        'error',
      ),
    )
    expect(toast).not.toHaveBeenCalledWith(expect.stringContaining('已创建'), 'success')
    expect(screen.getByTestId('smart-home-scheme-submit')).toBeTruthy()
    expect(listCalls(calls)).toHaveLength(1) // 未误刷新
  })

  it('列表 500 → 展示错误（含 detail）而非空态/伪造数据', async () => {
    const calls = installFetch({
      '/api/smart-home/schemes/project/p1': () => jsonRes(500, { detail: '方案列表服务异常' }),
    })
    render(<SmartHomePage />)
    fireEvent.change(await screen.findByTestId('smart-home-project-select'), {
      target: { value: 'p1' },
    })

    await screen.findByText('方案列表服务异常')
    expect(screen.queryByText('该项目暂无智能家居方案')).toBeNull()
    expect(screen.getByRole('button', { name: /重试/ })).toBeTruthy()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0)
  })
})
