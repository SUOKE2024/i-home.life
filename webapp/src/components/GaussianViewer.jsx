import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { paintDeviceSprite } from './PanoramaViewer'

/**
 * GaussianViewer — 3DGS 漫游查看器（M3 组件基石，2026-08-12）
 *
 * v1.15.14 双轨渲染（Three.js r186 原生高斯泼溅落地）：
 * - 轨道一（优先）：WebGPU 可用 → Three.js 原生 GaussianSplat + WebGPURenderer
 *   （免 4.9MB Spark 依赖，GPU 计数排序 + SH1-SH3 视角相关颜色，按扩展名选
 *   SPZLoader / GaussianSplatPLYLoader / SPLATLoader / KSPLATLoader）
 * - 轨道二（回退）：无 WebGPU → 现有 @sparkjsdev/spark（WebGL2 GPU 排序，
 *   覆盖低端移动设备）
 * - 兜底：无 WebGL2 / 两条轨道加载失败 / 资源超时 → onFallback()（贴图全景）
 *   延续项目 4 级降级链（WebGPU → WebGL2/Spark → 贴图全景 → 静态图）
 * - 设备锚点叠加：复用 P0 热点 yaw/pitch 球面坐标换算（THREE.Sprite）
 * - 按需渲染省电路径（静止停帧）+ 拖拽环视 / 滚轮缩放
 *
 * v1.17.1 移动端交互补齐（2026-09-22，评估报告 P1-2）：
 * - 双指捏合缩放（此前仅滚轮 → 触屏设备无任何缩放手段）
 * - 陀螺仪环视（DeviceOrientation，需用户显式开启；iOS 需 requestPermission）
 * - 纯函数 clampFov / fovFromPinch / orientationToRotation 导出供单测直接断言
 */
const MIN_FOV = 30
const MAX_FOV = 110

/** FOV 夹取到 [30°, 110°]（与滚轮缩放同一区间，防畸变/穿模）。 */
export const clampFov = (fov) => Math.max(MIN_FOV, Math.min(MAX_FOV, fov))

/**
 * 双指捏合 → FOV 换算（张开=拉近=FOV 变小，捏合=拉远=FOV 变大）。
 * 用手势起始距离做基准，避免逐帧累积误差；非法距离回退起始 FOV。
 */
export const fovFromPinch = (startFov, startDist, currentDist) => {
  if (!startDist || !currentDist || startDist <= 0 || currentDist <= 0) {
    return clampFov(startFov)
  }
  return clampFov(startFov * (startDist / currentDist))
}

/**
 * 设备姿态 → 相机旋转增量（相对式：由调用方减去开启时的基准姿态，
 * 使开启陀螺仪的瞬间视角不跳变）。
 * alpha 为罗盘角（度，逆时针为正）→ yaw 取反使转动方向与真实一致；
 * beta 为前后倾角，夹取 ±90° 防翻转。
 */
export const orientationToRotation = ({ alpha = 0, beta = 0 } = {}) => ({
  yaw: (-alpha * Math.PI) / 180,
  pitch: (Math.max(-90, Math.min(90, beta)) * Math.PI) / 180,
})

const isLowEndDevice = () => {
  if (typeof navigator === 'undefined') return false
  const cores = navigator.hardwareConcurrency || 8
  const mem = navigator.deviceMemory || 8
  const mobile = /Android|iPhone|iPad|Mobi/i.test(navigator.userAgent || '')
  return mobile || cores <= 4 || mem <= 4
}

const supportsWebGL2 = () => {
  if (typeof window === 'undefined') return false
  try {
    const c = document.createElement('canvas')
    return !!c.getContext('webgl2')
  } catch {
    return false
  }
}

// WebGPU 检测（异步：navigator.gpu 存在且能拿到 adapter）
const supportsWebGPU = async () => {
  if (typeof navigator === 'undefined' || !navigator.gpu) return false
  try {
    const adapter = await navigator.gpu.requestAdapter()
    return !!adapter
  } catch {
    return false
  }
}

// 加载原生 splat 对象（返回可直接 scene.add 的对象）：
// - .spz/.ply/.splat/.ksplat → BufferGeometry → new GaussianSplat（直接返回）
// - .glb/.gltf → GLTFLoader + KHR_gaussian_splatting 扩展 → 返回 gltf.scene
//   （对接 LCC2 生态的 glTF 导出，P2 落地）
const loadNativeSplat = async (url) => {
  const clean = url.split('?')[0] || ''
  const ext = (clean.split('.').pop() || '').toLowerCase()
  const { GaussianSplat } = await import('three/addons/objects/GaussianSplat.js')

  if (ext === 'glb' || ext === 'gltf') {
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js')
    const { GLTFGaussianSplatLoaderExtension } = await import('three/addons/loaders/GLTFGaussianSplatLoaderExtension.js')
    const loader = new GLTFLoader()
    loader.register((parser) => new GLTFGaussianSplatLoaderExtension(parser))
    const gltf = await loader.loadAsync(url)
    return gltf.scene
  }

  let geometry
  if (ext === 'ply') {
    const { GaussianSplatPLYLoader } = await import('three/addons/loaders/GaussianSplatPLYLoader.js')
    geometry = await new GaussianSplatPLYLoader().loadAsync(url)
  } else if (ext === 'splat') {
    const { SPLATLoader } = await import('three/addons/loaders/SPLATLoader.js')
    geometry = await new SPLATLoader().loadAsync(url)
  } else if (ext === 'ksplat') {
    const { KSPLATLoader } = await import('three/addons/loaders/KSPLATLoader.js')
    geometry = await new KSPLATLoader().loadAsync(url)
  } else {
    const { SPZLoader } = await import('three/addons/loaders/SPZLoader.js')
    geometry = await new SPZLoader().loadAsync(url)
  }
  return new GaussianSplat(geometry)
}

const LOAD_TIMEOUT_MS = 20_000 // Splat 加载超时（无 onError 事件，超时兜底降级）

export default function GaussianViewer({
  splatUrl, devices = [], hotspots = [], initialView, onDeviceClick, onHotspotClick, onFallback,
}) {
  const mountRef = useRef(null)
  const devicesRef = useRef(devices)
  const deviceSpritesRef = useRef([])
  const [status, setStatus] = useState('loading') // loading / ready / error
  // 陀螺仪环视（需用户显式开启；iOS 13+ 需 requestPermission，拒绝则诚实保持关闭）
  const gyroEnabledRef = useRef(false)
  const [gyroOn, setGyroOn] = useState(false)
  const [gyroSupported] = useState(
    () => typeof window !== 'undefined' && 'DeviceOrientationEvent' in window,
  )
  const toggleGyro = async () => {
    if (gyroEnabledRef.current) {
      gyroEnabledRef.current = false
      setGyroOn(false)
      return
    }
    try {
      const DOE = typeof window !== 'undefined' ? window.DeviceOrientationEvent : null
      if (DOE && typeof DOE.requestPermission === 'function') {
        const granted = await DOE.requestPermission()
        if (granted !== 'granted') return // 用户拒绝 → 不开启，不伪称已开启
      }
      gyroEnabledRef.current = true
      setGyroOn(true)
    } catch {
      // 不支持/权限异常 → 保持关闭（诚实降级）
      gyroEnabledRef.current = false
      setGyroOn(false)
    }
  }
  useEffect(() => { devicesRef.current = devices }, [devices])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    if (!supportsWebGL2()) {
      setStatus('error')
      onFallback?.()
      return undefined
    }
    const lowEnd = isLowEndDevice()

    let disposed = false
    let raf = 0
    let idleTimer = null
    let needsRender = true
    let fallbackTimer = null
    let renderer = null
    let splatObj = null
    let spark = null
    const cleanupFns = []

    const width = mount.clientWidth || 640
    const height = mount.clientHeight || 360
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.01, 500)
    camera.position.set(0, 0, 0)

    // 按需渲染：静止 600ms 停帧（低配省电）
    const scheduleRender = () => {
      needsRender = true
      if (!raf) raf = requestAnimationFrame(loop)
      clearTimeout(idleTimer)
      idleTimer = setTimeout(() => { needsRender = false }, 600)
    }
    const loop = () => {
      if (needsRender && renderer) renderer.render(scene, camera)
      raf = needsRender ? requestAnimationFrame(loop) : 0
    }

    // 场景热点 Sprite（房间跳转，复用 P0 热点 yaw/pitch 换算）
    const hotSprites = []
    hotspots.forEach((hs) => {
      const canvas = document.createElement('canvas')
      canvas.width = 64
      canvas.height = 64
      const ctx = canvas.getContext('2d')
      ctx.beginPath()
      ctx.arc(32, 32, 26, 0, 2 * Math.PI)
      ctx.fillStyle = 'rgba(220, 80, 60, 0.9)'
      ctx.fill()
      ctx.lineWidth = 3
      ctx.strokeStyle = '#fff'
      ctx.stroke()
      ctx.font = 'bold 22px sans-serif'
      ctx.fillStyle = '#fff'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('★', 32, 32)
      const tex = new THREE.CanvasTexture(canvas)
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: tex, depthTest: false }),
      )
      const yawRad = ((hs.position?.yaw ?? 0) * Math.PI) / 180
      const pitchRad = ((hs.position?.pitch ?? 0) * Math.PI) / 180
      sprite.position.setFromSphericalCoords(4, Math.PI / 2 - pitchRad, Math.PI - yawRad)
      sprite.scale.set(0.5, 0.5, 1)
      scene.add(sprite)
      hotSprites.push(sprite)
    })

    // 设备锚点 Sprite（复用 P0 坐标换算：yaw=0 → -z 正前方，顺时针为正）
    const deviceSprites = []
    devicesRef.current.forEach((d) => {
      const canvas = document.createElement('canvas')
      canvas.width = 64
      canvas.height = 64
      paintDeviceSprite(canvas, d)
      const tex = new THREE.CanvasTexture(canvas)
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: tex, depthTest: false }),
      )
      const yawRad = ((d.yaw ?? 0) * Math.PI) / 180
      const pitchRad = ((d.pitch ?? 0) * Math.PI) / 180
      sprite.position.setFromSphericalCoords(4, Math.PI / 2 - pitchRad, Math.PI - yawRad)
      sprite.scale.set(0.5, 0.5, 1)
      scene.add(sprite)
      deviceSprites.push(sprite)
    })
    deviceSpritesRef.current = deviceSprites

    // 设备状态刷新（轮询/WS 更新时仅重绘颜色）
    const refreshSprites = () => {
      deviceSpritesRef.current.forEach((s, i) => {
        const d = devicesRef.current[i]
        if (!d || !s.material.map?.image) return
        paintDeviceSprite(s.material.map.image, d)
        s.material.map.needsUpdate = true
      })
      scheduleRender()
    }
    refreshSprites()

    // 交互绑定（两条轨道共享）：单指拖拽环视 + 双指捏合缩放 + 滚轮缩放 + 点击热点/设备
    const bindInteraction = (el) => {
      let dragging = false
      let lastX = 0
      let lastY = 0
      let dragYaw = 0
      let dragPitch = 0
      // 活动指针表（多指手势判定）：size===1 拖拽环视，size>=2 捏合缩放
      const pointers = new Map()
      let pinchStartDist = 0
      let pinchStartFov = camera.fov
      const pinchDistance = () => {
        const pts = [...pointers.values()]
        if (pts.length < 2) return 0
        return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
      }
      const onDown = (e) => {
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
        if (pointers.size === 1) {
          dragging = true
          lastX = e.clientX
          lastY = e.clientY
        } else if (pointers.size === 2) {
          // 进入捏合：停用拖拽，记录手势基准（FOV 与距离）
          dragging = false
          pinchStartDist = pinchDistance()
          pinchStartFov = camera.fov
        }
        scheduleRender()
      }
      const onMove = (e) => {
        if (!pointers.has(e.pointerId)) return
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
        if (pointers.size >= 2) {
          // 双指捏合缩放（触屏设备唯一的缩放手段）
          const dist = pinchDistance()
          if (pinchStartDist > 0 && dist > 0) {
            camera.fov = fovFromPinch(pinchStartFov, pinchStartDist, dist)
            camera.updateProjectionMatrix()
            scheduleRender()
          }
          return
        }
        if (!dragging) return
        const dx = e.clientX - lastX
        const dy = e.clientY - lastY
        lastX = e.clientX
        lastY = e.clientY
        dragYaw += dx * 0.005
        dragPitch += dy * 0.005
        dragPitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, dragPitch))
        camera.rotation.order = 'YXZ'
        camera.rotation.y = -dragYaw + ((initialView?.heading ?? 0) * Math.PI) / 180
        camera.rotation.x = dragPitch + ((initialView?.pitch ?? 0) * Math.PI) / 180
        scheduleRender()
      }
      const onUp = (e) => {
        pointers.delete(e.pointerId)
        if (pointers.size < 2) pinchStartDist = 0
        if (pointers.size === 1) {
          // 捏合结束仍有一指在屏 → 以该指针为基准恢复拖拽环视
          // （否则必须全部抬指才能再环视，双指缩放后视角操作会「死」住）
          const [p] = [...pointers.values()]
          dragging = true
          lastX = p.x
          lastY = p.y
        } else if (pointers.size === 0) {
          dragging = false
        }
      }
      const onWheel = (e) => {
        e.preventDefault()
        camera.fov = clampFov(camera.fov + e.deltaY * 0.05)
        camera.updateProjectionMatrix()
        scheduleRender()
      }
      const raycaster = new THREE.Raycaster()
      const onClick = (e) => {
        const rect = el.getBoundingClientRect()
        const ndc = new THREE.Vector2(
          ((e.clientX - rect.left) / rect.width) * 2 - 1,
          -((e.clientY - rect.top) / rect.height) * 2 + 1,
        )
        raycaster.setFromCamera(ndc, camera)
        const hitAll = raycaster.intersectObjects([...hotSprites, ...deviceSprites])
        if (hitAll.length === 0) return
        const obj = hitAll[0].object
        const hsIdx = hotSprites.indexOf(obj)
        if (hsIdx >= 0) {
          if (onHotspotClick) onHotspotClick(hotspots[hsIdx])
          return
        }
        const idx = deviceSprites.indexOf(obj)
        if (idx >= 0 && onDeviceClick) onDeviceClick(devicesRef.current[idx])
      }
      el.addEventListener('pointerdown', onDown)
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
      el.addEventListener('wheel', onWheel, { passive: false })
      el.addEventListener('click', onClick)
      el.style.cursor = 'grab'
      el.style.touchAction = 'none'
      return () => {
        el.removeEventListener('pointerdown', onDown)
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
        el.removeEventListener('wheel', onWheel)
        el.removeEventListener('click', onClick)
      }
    }

    // 陀螺仪环视（相对式：以开启瞬间姿态为基准，避免开启时视角跳变）
    // 关闭状态直接 return 并清空基准 → 重新开启自动重新取基准
    let gyroBase = null
    const onDeviceOrientation = (e) => {
      if (!gyroEnabledRef.current) {
        gyroBase = null
        return
      }
      const { yaw, pitch } = orientationToRotation({ alpha: e.alpha ?? 0, beta: e.beta ?? 0 })
      if (!gyroBase) gyroBase = { yaw, pitch }
      const limit = Math.PI / 2
      camera.rotation.order = 'YXZ'
      camera.rotation.y =
        -(yaw - gyroBase.yaw) + ((initialView?.heading ?? 0) * Math.PI) / 180
      camera.rotation.x = Math.max(
        -limit,
        Math.min(limit, pitch - gyroBase.pitch + ((initialView?.pitch ?? 0) * Math.PI) / 180),
      )
      scheduleRender()
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('deviceorientation', onDeviceOrientation)
      cleanupFns.push(() => window.removeEventListener('deviceorientation', onDeviceOrientation))
    }

    // 尺寸自适应 + 初始渲染（两条轨道共享）
    const finalizeRenderer = (r) => {
      renderer = r
      const el = r.domElement
      cleanupFns.push(bindInteraction(el))
      const resize = () => {
        const w = mount.clientWidth || width
        const h = mount.clientHeight || height
        camera.aspect = w / h
        camera.updateProjectionMatrix()
        r.setSize(w, h)
        scheduleRender()
      }
      resize()
      const ro = new ResizeObserver(resize)
      ro.observe(mount)
      cleanupFns.push(() => ro.disconnect())
      scheduleRender()
    }

    // 轨道一：Three.js 原生 GaussianSplat（WebGPU）
    const setupNative = async () => {
      const { WebGPURenderer } = await import('three/webgpu')
      const r = new WebGPURenderer({
        antialias: !lowEnd,
        powerPreference: 'low-power',
      })
      await r.init()
      if (disposed) { r.dispose(); return }
      r.setSize(width, height)
      r.setPixelRatio(lowEnd ? 1 : Math.min(window.devicePixelRatio, 2))
      mount.appendChild(r.domElement)
      finalizeRenderer(r)

      const splat = await loadNativeSplat(splatUrl)
      if (disposed) return
      scene.add(splat)
      splatObj = splat
      clearTimeout(fallbackTimer)
      setStatus('ready')
      scheduleRender()
    }

    // 轨道二：Spark（WebGL2，动态导入 5MB+ 模块，低端设备/失败不拖慢首屏）
    const setupSpark = () => {
      const r = new THREE.WebGLRenderer({
        antialias: !lowEnd,
        powerPreference: 'low-power',
      })
      r.setSize(width, height)
      r.setPixelRatio(lowEnd ? 1 : Math.min(window.devicePixelRatio, 2))
      mount.appendChild(r.domElement)
      finalizeRenderer(r)

      return import('@sparkjsdev/spark')
        .then(({ SparkRenderer, SplatMesh }) => {
          if (disposed) return
          spark = new SparkRenderer({ renderer: r })
          scene.add(spark)
          const splat = new SplatMesh({
            url: splatUrl,
            onProgress: () => scheduleRender(),
            onLoad: () => {
              if (disposed) return
              clearTimeout(fallbackTimer)
              setStatus('ready')
              scheduleRender()
            },
          })
          scene.add(splat)
          splatObj = splat
          scheduleRender()
        })
    }

    // 双轨分流：WebGPU 原生优先，无 WebGPU 回退 Spark
    ;(async () => {
      let useNative = false
      try {
        useNative = await supportsWebGPU()
      } catch {
        useNative = false
      }
      if (disposed) return
      try {
        if (useNative) {
          await setupNative()
        } else {
          await setupSpark()
        }
      } catch (e) {
        console.warn('[GaussianViewer] 3DGS 渲染失败，降级全景:', e)
        setStatus('error')
        onFallback?.()
      }
    })()

    // 加载超时兜底（加载器无 onError 事件）
    fallbackTimer = setTimeout(() => {
      if (disposed) return
      console.warn('[GaussianViewer] 3DGS 资源加载超时，降级全景')
      setStatus('error')
      onFallback?.()
    }, LOAD_TIMEOUT_MS)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      clearTimeout(idleTimer)
      clearTimeout(fallbackTimer)
      cleanupFns.forEach((fn) => fn())
      hotSprites.forEach((s) => s.material.map?.dispose())
      deviceSprites.forEach((s) => s.material.map?.dispose())
      deviceSpritesRef.current = []
      if (splatObj) {
        splatObj.dispose?.()
        scene.remove(splatObj)
      }
      if (spark) {
        scene.remove(spark)
        spark.dispose?.()
      }
      if (renderer) {
        renderer.dispose()
        if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [splatUrl])

  // 设备状态/激活变化 → 重绘 Sprite 颜色（不重建场景）
  useEffect(() => {
    const sprites = deviceSpritesRef.current
    const list = devicesRef.current
    sprites.forEach((s, i) => {
      const d = list[i]
      if (!d || !s.material.map?.image) return
      paintDeviceSprite(s.material.map.image, d)
      s.material.map.needsUpdate = true
    })
  }, [devices])

  return (
    <div
      data-gs-status={status}
      style={{ position: 'relative', width: '100%', height: '100%' }}
    >
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      {gyroSupported && status === 'ready' && (
        <button
          type="button"
          data-gyro-toggle={gyroOn ? 'on' : 'off'}
          onClick={toggleGyro}
          title={gyroOn ? '关闭陀螺仪环视' : '开启陀螺仪环视'}
          style={{
            position: 'absolute', top: 8, right: 8, zIndex: 2,
            padding: '4px 10px', fontSize: 12, lineHeight: '18px',
            borderRadius: 12, cursor: 'pointer',
            border: '1px solid rgba(255,255,255,0.35)',
            background: gyroOn ? 'rgba(52,199,89,0.85)' : 'rgba(10,12,16,0.55)',
            color: '#fff',
          }}
        >
          {gyroOn ? '陀螺仪已开' : '陀螺仪环视'}
        </button>
      )}
      {status === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: 'rgba(255,255,255,0.75)', fontSize: 13,
          background: 'rgba(10,12,16,0.35)', pointerEvents: 'none',
        }}
        >
          3D 场景加载中…
        </div>
      )}
    </div>
  )
}
