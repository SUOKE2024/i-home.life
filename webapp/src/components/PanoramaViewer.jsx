import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * PanoramaViewer — Three.js 360° 等距柱状全景查看器
 *
 * - 等距柱状图贴到 SphereGeometry(BackSide)；相机固定看向 -z，拖拽旋转球体实现环视
 * - 滚轮缩放 FOV（30°~110°）
 * - 热点（yaw/pitch 球面坐标，0=正北/顺时针）以 Sprite 渲染，点击回调 onHotspotClick
 * - 设备（devices prop，P0 设备热点联动）：以 Sprite 渲染，状态色编码（在线绿/离线灰），
 *   点击回调 onDeviceClick(device, action)，支持 scene_ids 一键触发
 * - 支持 initialView { heading, pitch, fov } 初始视角
 * - 低配设备降级：low-power 渲染器 / 像素比 1 / 降低几何分段 / 按需渲染（静止停帧省电）
 */
// 低配设备启发式：CPU 核少 / 内存小 / 触屏移动端
const isLowEndDevice = () => {
  if (typeof navigator === 'undefined') return false
  const cores = navigator.hardwareConcurrency || 8
  const mem = navigator.deviceMemory || 8
  const mobile = /Android|iPhone|iPad|Mobi/i.test(navigator.userAgent || '')
  return mobile || cores <= 4 || mem <= 4
}

// 设备类型 → 图标（P0 设备热点，导出供 GaussianViewer 复用）
export const DEVICE_ICONS = {
  light: '💡', switch: '🔘', socket: '🔌', curtain: '🪟', speaker: '🔊',
  sensor: '📡', camera: '📷', lock: '🔒', thermostat: '🌡',
  air_purifier: '🌀', robot_vacuum: '🤖',
}
const deviceIcon = (type) => DEVICE_ICONS[type] || '⚙️'

/** 设备 Sprite 着色：激活（触发中闪烁/联动高亮）橙 / 在线绿 / 离线灰（导出供 GaussianViewer 复用） */
export const paintDeviceSprite = (canvas, device) => {
  const ctx = canvas.getContext('2d')
  const online = device.status === 'online' || device.status === 'installed'
  const color = device.activating
    ? 'rgba(250, 160, 40, 0.95)'
    : online ? 'rgba(34, 197, 94, 0.92)' : 'rgba(120, 120, 120, 0.85)'
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.beginPath()
  ctx.arc(32, 32, 27, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
  ctx.lineWidth = 3
  ctx.strokeStyle = '#fff'
  ctx.stroke()
  ctx.font = '24px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(deviceIcon(device.type), 32, 33)
}

/** 绘制设备 Sprite（激活橙 / 在线绿 / 离线灰） */
const drawDeviceSprite = (device) => {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  paintDeviceSprite(canvas, device)
  return canvas
}

export default function PanoramaViewer({
  imageUrl, hotspots = [], devices = [], initialView, onHotspotClick, onDeviceClick,
}) {
  const mountRef = useRef(null)
  const devicesRef = useRef(devices)
  const deviceSpritesRef = useRef([])
  const renderTriggerRef = useRef(null) // 供外部 effect 触发按需渲染（激活动画）
  useEffect(() => { devicesRef.current = devices }, [devices])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    const lowEnd = isLowEndDevice()

    const width = mount.clientWidth || 640
    const height = mount.clientHeight || 360

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 500)
    camera.rotation.order = 'YXZ'
    camera.fov = initialView?.fov ?? 75
    camera.updateProjectionMatrix()

    const renderer = new THREE.WebGLRenderer({
      antialias: !lowEnd,
      powerPreference: 'low-power', // 低配核显优先省电路径
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(lowEnd ? 1 : Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    // 全景球体（相机固定在球心看向 -z，旋转球体实现环视）
    const texture = new THREE.TextureLoader().load(imageUrl, () => { scheduleRender() })
    texture.wrapS = THREE.RepeatWrapping
    texture.colorSpace = THREE.SRGBColorSpace
    // 低配设备降低几何分段（球面纹理映射分段数与画质无直接关系，48×32 已足够平滑）
    const geometry = new THREE.SphereGeometry(100, lowEnd ? 32 : 48, lowEnd ? 16 : 32)
    const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.BackSide })
    const sphere = new THREE.Mesh(geometry, material)
    sphere.rotation.y = ((initialView?.heading ?? 0) * Math.PI) / 180
    scene.add(sphere)

    // 热点 Sprite（世界坐标固定，不随球旋转）
    const hotSprites = []
    const makeSprite = (hs) => {
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
      // yaw=0 → -z 正前方；顺时针为正（θ=π-yaw）
      sprite.position.setFromSphericalCoords(98, Math.PI / 2 - pitchRad, Math.PI - yawRad)
      sprite.scale.set(6, 6, 1)
      return sprite
    }
    hotspots.forEach((hs) => {
      const s = makeSprite(hs)
      scene.add(s)
      hotSprites.push(s)
    })

    // 设备 Sprite（P0：状态色编码，点击回调 onDeviceClick）
    const deviceSprites = []
    const makeDeviceSprite = (d) => {
      const tex = new THREE.CanvasTexture(drawDeviceSprite(d))
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: tex, depthTest: false }),
      )
      const yawRad = ((d.yaw ?? 0) * Math.PI) / 180
      const pitchRad = ((d.pitch ?? 0) * Math.PI) / 180
      sprite.position.setFromSphericalCoords(96, Math.PI / 2 - pitchRad, Math.PI - yawRad)
      sprite.scale.set(7, 7, 1)
      return sprite
    }
    devicesRef.current.forEach((d) => {
      const s = makeDeviceSprite(d)
      scene.add(s)
      deviceSprites.push(s)
    })
    deviceSpritesRef.current = deviceSprites

    // 交互：拖拽旋转球体环视 + 滚轮缩放
    let dragYaw = 0
    let dragPitch = 0
    let dragging = false
    let lastX = 0
    let lastY = 0
    // 按需渲染：静止 600ms 后停帧，低配设备省电省 GPU
    let raf = 0
    let needsRender = true
    let idleTimer = null
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
    // 暴露渲染触发通道：激活动画 effect 每帧调用，保持按需渲染循环活跃
    renderTriggerRef.current = scheduleRender
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
      dragYaw += dx * 0.005 // 向右拖 → 场景向左转
      dragPitch += dy * 0.005
      dragPitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, dragPitch))
      sphere.rotation.y = ((initialView?.heading ?? 0) * Math.PI) / 180 + dragYaw
      camera.rotation.x = -((initialView?.pitch ?? 0) * Math.PI) / 180 + dragPitch
      scheduleRender()
    }
    const onUp = () => { dragging = false }
    const onWheel = (e) => {
      e.preventDefault()
      camera.fov = Math.max(30, Math.min(110, camera.fov + e.deltaY * 0.05))
      camera.updateProjectionMatrix()
      scheduleRender()
    }
    // 热点/设备点击（Raycaster 投影到屏幕）
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
      const dIdx = deviceSprites.indexOf(obj)
      if (dIdx >= 0 && onDeviceClick) {
        onDeviceClick(devicesRef.current[dIdx])
      }
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

    // 初始渲染（纹理加载完成后由 scheduleRender 再触发一次）
    scheduleRender()

    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(idleTimer)
      renderTriggerRef.current = null
      ro.disconnect()
      el.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('click', onClick)
      geometry.dispose()
      material.dispose()
      texture.dispose()
      hotSprites.forEach((s) => s.material.map?.dispose())
      deviceSprites.forEach((s) => s.material.map?.dispose())
      deviceSpritesRef.current = []
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrl])

  // 设备状态刷新（轮询/WS 更新时仅重绘颜色，不重建场景）
  useEffect(() => {
    const sprites = deviceSpritesRef.current
    const list = devicesRef.current
    sprites.forEach((s, i) => {
      const d = list[i]
      if (!d) return
      const tex = s.material.map
      if (tex && tex.image) {
        paintDeviceSprite(tex.image, d)
        tex.needsUpdate = true
      }
    })
  }, [devices])

  // 设备激活动画：触发中闪烁 / 场景联动高亮（橙色 + 脉冲放大），结束后复位
  useEffect(() => {
    const sprites = deviceSpritesRef.current
    const list = devicesRef.current
    const actives = list
      .map((d, i) => ({ d, s: sprites[i] }))
      .filter((x) => x.s && x.d?.activating)
    if (actives.length === 0) {
      sprites.forEach((s) => s.scale.set(7, 7, 1))
      return
    }
    let raf = 0
    const t0 = performance.now()
    const tick = () => {
      const t = (performance.now() - t0) / 1000
      actives.forEach(({ s }) => {
        const k = 1 + 0.18 * Math.abs(Math.sin(t * 5)) // 1.0~1.18 脉冲放大
        s.scale.set(7 * k, 7 * k, 1)
      })
      renderTriggerRef.current?.() // 保持按需渲染循环活跃
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      sprites.forEach((s) => s.scale.set(7, 7, 1))
    }
  }, [devices])

  return <div ref={mountRef} className="panorama-viewer" />
}
