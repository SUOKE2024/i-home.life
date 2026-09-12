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
 */
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

// 按扩展名选 Three.js 原生加载器（均返回 BufferGeometry，直接 new GaussianSplat）
const pickNativeLoader = async (url) => {
  const clean = url.split('?')[0] || ''
  const ext = (clean.split('.').pop() || '').toLowerCase()
  if (ext === 'ply') {
    const { GaussianSplatPLYLoader } = await import('three/addons/loaders/GaussianSplatPLYLoader.js')
    return new GaussianSplatPLYLoader()
  }
  if (ext === 'splat') {
    const { SPLATLoader } = await import('three/addons/loaders/SPLATLoader.js')
    return new SPLATLoader()
  }
  if (ext === 'ksplat') {
    const { KSPLATLoader } = await import('three/addons/loaders/KSPLATLoader.js')
    return new KSPLATLoader()
  }
  const { SPZLoader } = await import('three/addons/loaders/SPZLoader.js')
  return new SPZLoader()
}

const LOAD_TIMEOUT_MS = 20_000 // Splat 加载超时（无 onError 事件，超时兜底降级）

export default function GaussianViewer({
  splatUrl, devices = [], hotspots = [], initialView, onDeviceClick, onHotspotClick, onFallback,
}) {
  const mountRef = useRef(null)
  const devicesRef = useRef(devices)
  const deviceSpritesRef = useRef([])
  const [status, setStatus] = useState('loading') // loading / ready / error
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

    // 交互绑定（两条轨道共享）：拖拽环视 + 滚轮缩放 + 点击热点/设备
    const bindInteraction = (el) => {
      let dragging = false
      let lastX = 0
      let lastY = 0
      let dragYaw = 0
      let dragPitch = 0
      const onDown = (e) => {
        dragging = true
        lastX = e.clientX
        lastY = e.clientY
        scheduleRender()
      }
      const onMove = (e) => {
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
      const onUp = () => { dragging = false }
      const onWheel = (e) => {
        e.preventDefault()
        camera.fov = Math.max(30, Math.min(110, camera.fov + e.deltaY * 0.05))
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

      const loader = await pickNativeLoader(splatUrl)
      const { GaussianSplat } = await import('three/addons/objects/GaussianSplat.js')
      const geometry = await loader.loadAsync(splatUrl)
      if (disposed) return
      const splat = new GaussianSplat(geometry)
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
