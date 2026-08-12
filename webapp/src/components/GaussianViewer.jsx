import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { paintDeviceSprite } from './PanoramaViewer'

/**
 * GaussianViewer — Spark 3DGS 漫游查看器（M3 组件基石，2026-08-12）
 *
 * - SparkRenderer + SplatMesh 渲染 .spz/.ply（@sparkjsdev/spark，WebGL2）
 * - 双轨降级：无 WebGL2 / Spark 加载失败 / 资源超时 → onFallback()
 *   （调用方回退 PanoramaViewer 贴图全景，延续 4 级降级链）
 * - 设备锚点叠加：复用 P0 热点 yaw/pitch 球面坐标换算（THREE.Sprite，
 *   在线绿 / 离线灰 / 激活橙，onDeviceClick 回调）
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

const LOAD_TIMEOUT_MS = 20_000 // SplatMesh 加载超时（无 onError 事件，超时兜底降级）

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
    let spark = null
    let splat = null

    const width = mount.clientWidth || 640
    const height = mount.clientHeight || 360
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.01, 500)
    camera.position.set(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({
      antialias: !lowEnd,
      powerPreference: 'low-power',
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(lowEnd ? 1 : Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    // 按需渲染：静止 600ms 停帧（低配省电）
    const scheduleRender = () => {
      needsRender = true
      if (!raf) raf = requestAnimationFrame(loop)
      clearTimeout(idleTimer)
      idleTimer = setTimeout(() => { needsRender = false }, 600)
    }
    const loop = () => {
      if (needsRender) renderer.render(scene, camera)
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

    // Spark 加载（动态导入，按需加载 5MB+ 模块，低端设备/失败不拖慢首屏）
    import('@sparkjsdev/spark')
      .then(({ SparkRenderer, SplatMesh }) => {
        if (disposed) return
        spark = new SparkRenderer({ renderer })
        scene.add(spark)
        splat = new SplatMesh({
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
        scheduleRender()
      })
      .catch((e) => {
        console.warn('[GaussianViewer] Spark 加载失败，降级全景:', e)
        setStatus('error')
        onFallback?.()
      })

    // 加载超时兜底（SplatMesh 无 onError 事件）
    fallbackTimer = setTimeout(() => {
      if (disposed) return
      console.warn('[GaussianViewer] 3DGS 资源加载超时，降级全景')
      setStatus('error')
      onFallback?.()
    }, LOAD_TIMEOUT_MS)

    // 交互：拖拽环视 + 滚轮缩放
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
      const rect = renderer.domElement.getBoundingClientRect()
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

    const el = renderer.domElement
    el.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('click', onClick)
    el.style.cursor = 'grab'
    el.style.touchAction = 'none'

    const resize = () => {
      const w = mount.clientWidth || width
      const h = mount.clientHeight || height
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
      scheduleRender()
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(mount)

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

    scheduleRender()

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      clearTimeout(idleTimer)
      clearTimeout(fallbackTimer)
      ro.disconnect()
      el.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('click', onClick)
      hotSprites.forEach((s) => s.material.map?.dispose())
      deviceSprites.forEach((s) => s.material.map?.dispose())
      deviceSpritesRef.current = []
      splat?.dispose?.()
      scene.remove(splat)
      if (spark) {
        scene.remove(spark)
        spark.dispose?.()
      }
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
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
