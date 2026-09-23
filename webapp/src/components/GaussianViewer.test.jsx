import React from 'react'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import GaussianViewer, {
  clampFov,
  fovFromPinch,
  orientationToRotation,
} from './GaussianViewer'

/**
 * GaussianViewer 交互单测（2026-09-22，评估报告 P1-2 / X3）
 *
 * 覆盖移动端交互补齐项：
 * - 双指捏合缩放（此前仅滚轮 → 触屏无任何缩放手段）
 * - 陀螺仪环视（DeviceOrientation；iOS requestPermission 拒绝/异常须诚实降级）
 *
 * 3DGS 渲染依赖 WebGL2/WebGPU（jsdom 无实现），故整体打桩 three 与
 * @sparkjsdev/spark，仅保留交互逻辑可观测的 API 面（相机 fov/rotation、
 * 投影矩阵更新次数、渲染器实例）。
 */

// ── three / spark 打桩 ──
// 状态挂 globalThis：vi.mock 工厂会被提升到 import 之前执行，无法引用模块级变量
vi.mock('three', () => {
  const state = (globalThis.__gs3d ||= { cameras: [], renderers: [], sprites: [], splats: [] })

  class Object3D {
    constructor() {
      this.children = []
      this.position = { set: () => {}, setFromSphericalCoords: () => {} }
      this.scale = { set: () => {} }
    }

    add(obj) { this.children.push(obj) }

    remove(obj) {
      const i = this.children.indexOf(obj)
      if (i >= 0) this.children.splice(i, 1)
    }
  }

  class Scene extends Object3D {}

  class SpriteMaterial {
    constructor(opts) { this.map = opts?.map }
  }

  class CanvasTexture {
    constructor(image) { this.image = image; this.needsUpdate = false }

    dispose() { this.disposed = true }
  }

  class Sprite extends Object3D {
    constructor(material) { super(); this.material = material; state.sprites.push(this) }
  }

  class PerspectiveCamera {
    constructor(fov, aspect) {
      this.fov = fov
      this.aspect = aspect
      this.rotation = { order: 'XYZ', x: 0, y: 0, z: 0 }
      this.position = { set: () => {}, setFromSphericalCoords: () => {} }
      this.projectionUpdateCount = 0
      state.cameras.push(this)
    }

    updateProjectionMatrix() { this.projectionUpdateCount += 1 }
  }

  class WebGLRenderer {
    constructor() {
      this.domElement = document.createElement('canvas')
      this.renderCount = 0
      state.renderers.push(this)
    }

    setSize() {}

    setPixelRatio() {}

    render() { this.renderCount += 1 }

    dispose() { this.disposed = true }
  }

  class Raycaster {
    setFromCamera() {}

    intersectObjects() { return [] }
  }

  class Vector2 {
    constructor(x, y) { this.x = x; this.y = y }
  }

  return {
    Scene, Sprite, SpriteMaterial, CanvasTexture, PerspectiveCamera,
    WebGLRenderer, Raycaster, Vector2,
  }
})

vi.mock('@sparkjsdev/spark', () => {
  const state = (globalThis.__gs3d ||= { cameras: [], renderers: [], sprites: [], splats: [] })

  class SparkRenderer {
    constructor() { this.disposed = false }

    dispose() { this.disposed = true }
  }

  // 构造即回调 onLoad：模拟真实 SplatMesh 加载完成 → 组件置 status=ready
  class SplatMesh {
    constructor(opts) {
      this.url = opts?.url
      state.splats.push(this)
      opts?.onLoad?.()
    }

    dispose() { this.disposed = true }
  }

  return { SparkRenderer, SplatMesh }
})

// ── jsdom 环境补齐 ──
const noop = () => {}
const ctx2dStub = () => ({
  clearRect: noop, beginPath: noop, arc: noop, fill: noop, stroke: noop,
  fillText: noop, save: noop, restore: noop,
})

beforeAll(() => {
  // jsdom 无 canvas 实现：webgl2 返回真值让 supportsWebGL2 通过，2d 返回 no-op 上下文
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    writable: true,
    value: function getContext(type) {
      if (type === '2d') return ctx2dStub()
      if (type === 'webgl2' || type === 'webgl') return { getExtension: () => null }
      return null
    },
  })
  globalThis.ResizeObserver = class {
    observe() {}

    unobserve() {}

    disconnect() {}
  }
})

afterAll(() => {
  delete globalThis.ResizeObserver
})

const state = () => globalThis.__gs3d
const currentCamera = () => state().cameras[state().cameras.length - 1]

/** DeviceOrientationEvent 注入：granted 为 undefined 时模拟桌面浏览器（无 requestPermission） */
const installDOE = (granted) => {
  const Ctor = function DeviceOrientationEvent() {}
  if (granted !== undefined) Ctor.requestPermission = vi.fn(async () => granted)
  Object.defineProperty(window, 'DeviceOrientationEvent', {
    configurable: true, writable: true, value: Ctor,
  })
  return Ctor
}

/** 通用事件派发（jsdom 未实现 PointerEvent，用 Event + 属性注入） */
const fire = (target, type, props = {}) => {
  const ev = new Event(type, { bubbles: true, cancelable: true })
  Object.assign(ev, props)
  target.dispatchEvent(ev)
  return ev
}

const DEFAULT_DEVICES = [
  { id: 'dev-1', type: 'light', name: '客厅灯', status: 'online', yaw: 30, pitch: 5 },
]

/** 渲染并等待 status=ready（Spark 轨道 onLoad 触发）；返回容器与渲染器 canvas */
const renderViewer = async (props = {}) => {
  let utils
  await act(async () => {
    utils = render(<GaussianViewer splatUrl="/demo.spz" devices={DEFAULT_DEVICES} {...props} />)
  })
  await waitFor(() => {
    expect(utils.container.querySelector('[data-gs-status="ready"]')).toBeTruthy()
  })
  return { ...utils, canvas: utils.container.querySelector('canvas') }
}

beforeEach(() => {
  state().cameras.length = 0
  state().renderers.length = 0
  state().sprites.length = 0
  state().splats.length = 0
  installDOE(undefined) // 默认无设备姿态支持，需要时由用例显式注入
})

afterEach(() => {
  cleanup()
  delete window.DeviceOrientationEvent
})

// ── 纯函数（FOV 换算 / 姿态换算）──

describe('GaussianViewer FOV 纯函数', () => {
  it('clampFov 夹取到 [30°, 110°] 防畸变/穿模', () => {
    expect(clampFov(10)).toBe(30)
    expect(clampFov(200)).toBe(110)
    expect(clampFov(75)).toBe(75)
  })

  it('fovFromPinch：双指张开=拉近（FOV 变小）', () => {
    expect(fovFromPinch(75, 100, 200)).toBeCloseTo(37.5)
  })

  it('fovFromPinch：双指捏合=拉远（FOV 变大）且超上限夹取', () => {
    expect(fovFromPinch(75, 200, 100)).toBe(110) // 理论 150 → 夹取 110
  })

  it('fovFromPinch：非法距离回退起始 FOV（不跳变、不 NaN）', () => {
    expect(fovFromPinch(75, 0, 100)).toBe(75)
    expect(fovFromPinch(75, 100, 0)).toBe(75)
    expect(fovFromPinch(75, -1, 100)).toBe(75)
  })

  it('orientationToRotation：alpha→yaw 取反，beta 夹取 ±90°', () => {
    expect(orientationToRotation({ alpha: 90, beta: 0 }).yaw).toBeCloseTo(-Math.PI / 2)
    expect(orientationToRotation({ alpha: 0, beta: 100 }).pitch).toBeCloseTo(Math.PI / 2)
    expect(orientationToRotation({ alpha: 0, beta: -100 }).pitch).toBeCloseTo(-Math.PI / 2)
    // 缺省参数不抛错（部分浏览器 alpha/beta 为 null）
    expect(orientationToRotation().yaw).toBeCloseTo(0)
    expect(orientationToRotation({ alpha: null, beta: null }).pitch).toBe(0)
  })
})

// ── 双指捏合缩放（DOM 手势）──

describe('GaussianViewer 双指捏合缩放', () => {
  it('两指张开 → FOV 变小（拉近）并更新投影矩阵', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()
    expect(camera.fov).toBe(75) // PerspectiveCamera 初始 FOV

    await act(async () => {
      fire(canvas, 'pointerdown', { pointerId: 1, clientX: 0, clientY: 0 })
      fire(canvas, 'pointerdown', { pointerId: 2, clientX: 100, clientY: 0 })
      fire(window, 'pointermove', { pointerId: 2, clientX: 200, clientY: 0 })
    })

    expect(camera.fov).toBeCloseTo(37.5) // 75 × (100/200)
    expect(camera.projectionUpdateCount).toBeGreaterThan(0)
  })

  it('两指捏合 → FOV 变大（拉远），超上限夹取 110', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()

    await act(async () => {
      fire(canvas, 'pointerdown', { pointerId: 1, clientX: 0, clientY: 0 })
      fire(canvas, 'pointerdown', { pointerId: 2, clientX: 200, clientY: 0 })
      fire(window, 'pointermove', { pointerId: 2, clientX: 50, clientY: 0 })
    })

    expect(camera.fov).toBe(110)
  })

  it('捏合期间拖拽被抑制（双指不会同时改旋转）', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()

    await act(async () => {
      fire(canvas, 'pointerdown', { pointerId: 1, clientX: 0, clientY: 0 })
      fire(canvas, 'pointerdown', { pointerId: 2, clientX: 100, clientY: 0 })
      fire(window, 'pointermove', { pointerId: 1, clientX: 40, clientY: 30 })
    })

    expect(camera.rotation.y).toBe(0)
    expect(camera.rotation.x).toBe(0)
    expect(camera.fov).not.toBe(75) // 捏合生效
  })

  it('捏合后抬起一指 → 以剩余指针为基准恢复拖拽环视', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()

    await act(async () => {
      fire(canvas, 'pointerdown', { pointerId: 1, clientX: 0, clientY: 0 })
      fire(canvas, 'pointerdown', { pointerId: 2, clientX: 100, clientY: 0 })
      fire(window, 'pointermove', { pointerId: 2, clientX: 200, clientY: 0 })
      fire(window, 'pointerup', { pointerId: 2, clientX: 200, clientY: 0 })
    })

    const fovAfterPinch = camera.fov
    await act(async () => {
      fire(window, 'pointermove', { pointerId: 1, clientX: 10, clientY: 0 })
    })

    expect(camera.rotation.y).toBeCloseTo(-0.05) // 10px × 0.005，无跳变
    expect(camera.fov).toBeCloseTo(fovAfterPinch) // 单指不再改 FOV
  })

  it('单指拖拽环视不受捏合逻辑影响（回归）', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()

    await act(async () => {
      fire(canvas, 'pointerdown', { pointerId: 7, clientX: 0, clientY: 0 })
      fire(window, 'pointermove', { pointerId: 7, clientX: 20, clientY: 10 })
    })

    expect(camera.fov).toBe(75)
    expect(camera.rotation.y).toBeCloseTo(-0.1)
    expect(camera.rotation.x).toBeCloseTo(0.05)
    expect(camera.rotation.order).toBe('YXZ')
  })

  it('滚轮缩放与捏合共用同一 FOV 区间（夹取一致）', async () => {
    const { canvas } = await renderViewer()
    const camera = currentCamera()

    await act(async () => { fire(canvas, 'wheel', { deltaY: -2000 }) })
    expect(camera.fov).toBe(30) // 负 deltaY 拉近 → 下限夹取

    await act(async () => { fire(canvas, 'wheel', { deltaY: 4000 }) })
    expect(camera.fov).toBe(110) // 上限夹取
  })
})

// ── 陀螺仪环视 ──

describe('GaussianViewer 陀螺仪环视', () => {
  it('设备不支持 DeviceOrientationEvent → 不渲染开关（诚实降级）', async () => {
    delete window.DeviceOrientationEvent
    const { container } = await renderViewer()
    expect(container.querySelector('[data-gyro-toggle]')).toBeNull()
  })

  it('支持时渲染开关且默认关闭', async () => {
    installDOE(undefined)
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')
    expect(btn).toBeTruthy()
    expect(btn.getAttribute('data-gyro-toggle')).toBe('off')
  })

  it('桌面浏览器（无 requestPermission）点击直接开启并驱动相机旋转', async () => {
    installDOE(undefined)
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    expect(btn.getAttribute('data-gyro-toggle')).toBe('on')

    const camera = currentCamera()
    // 第一帧取基准 → 视角不跳变
    await act(async () => { fire(window, 'deviceorientation', { alpha: 0, beta: 0 }) })
    expect(camera.rotation.y).toBeCloseTo(0)
    expect(camera.rotation.x).toBeCloseTo(0)

    await act(async () => { fire(window, 'deviceorientation', { alpha: 90, beta: 0 }) })
    expect(camera.rotation.y).toBeCloseTo(Math.PI / 2)
  })

  it('开启瞬间以当前姿态为基准（视角不跳变）', async () => {
    installDOE('granted')
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    const camera = currentCamera()

    // 首帧姿态 α=180/β=30 作为基准 → 相机保持在 initialView（默认 0）
    await act(async () => { fire(window, 'deviceorientation', { alpha: 180, beta: 30 }) })
    expect(camera.rotation.y).toBeCloseTo(0)
    expect(camera.rotation.x).toBeCloseTo(0)

    // 相对基准转动 90° → 旋转量恰为 90°，而非绝对 180°
    await act(async () => { fire(window, 'deviceorientation', { alpha: 270, beta: 30 }) })
    expect(camera.rotation.y).toBeCloseTo(Math.PI / 2)
  })

  it('iOS requestPermission 拒绝 → 保持关闭且不响应姿态事件', async () => {
    const Ctor = installDOE('denied')
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })

    expect(Ctor.requestPermission).toHaveBeenCalledTimes(1)
    expect(btn.getAttribute('data-gyro-toggle')).toBe('off')

    const camera = currentCamera()
    await act(async () => { fire(window, 'deviceorientation', { alpha: 90, beta: 0 }) })
    expect(camera.rotation.y).toBe(0)
  })

  it('requestPermission 抛异常 → 保持关闭（诚实降级不伪称已开启）', async () => {
    const Ctor = installDOE('granted')
    Ctor.requestPermission = vi.fn(async () => { throw new Error('not allowed in iframe') })
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    expect(btn.getAttribute('data-gyro-toggle')).toBe('off')
  })

  it('关闭后不再响应姿态事件（重新开启重新取基准）', async () => {
    installDOE(undefined)
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    await act(async () => { fire(window, 'deviceorientation', { alpha: 0, beta: 0 }) })
    await act(async () => { fire(window, 'deviceorientation', { alpha: 45, beta: 0 }) })
    const camera = currentCamera()
    const yawWhileOn = camera.rotation.y

    await act(async () => { btn.click() }) // 关闭
    expect(btn.getAttribute('data-gyro-toggle')).toBe('off')

    await act(async () => { fire(window, 'deviceorientation', { alpha: 180, beta: 0 }) })
    expect(camera.rotation.y).toBeCloseTo(yawWhileOn) // 关闭后姿态事件不再生效
  })

  it('陀螺仪姿态与 initialView 叠加（基准偏移不丢失初始视角）', async () => {
    installDOE(undefined)
    const { container } = await renderViewer({ initialView: { heading: 90, pitch: 10 } })
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    const camera = currentCamera()

    await act(async () => { fire(window, 'deviceorientation', { alpha: 0, beta: 0 }) })
    expect(camera.rotation.y).toBeCloseTo(Math.PI / 2) // heading 90°
    expect(camera.rotation.x).toBeCloseTo(Math.PI / 18) // pitch 10°

    await act(async () => { fire(window, 'deviceorientation', { alpha: 90, beta: 0 }) })
    expect(camera.rotation.y).toBeCloseTo(Math.PI) // 初始 90° + 陀螺仪 90°
  })

  it('beta 超过 ±90° 被夹取（防相机翻转）', async () => {
    installDOE(undefined)
    const { container } = await renderViewer()
    const btn = container.querySelector('[data-gyro-toggle]')

    await act(async () => { btn.click() })
    const camera = currentCamera()

    await act(async () => { fire(window, 'deviceorientation', { alpha: 0, beta: 0 }) })
    await act(async () => { fire(window, 'deviceorientation', { alpha: 0, beta: 170 }) })
    expect(camera.rotation.x).toBeCloseTo(Math.PI / 2)
  })
})
