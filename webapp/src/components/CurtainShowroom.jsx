import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { X, Package, Shuffle, Lightbulb, Wrench, Layers, Store } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from './ui'
import {
  getCurtainShowroomOverview,
  getCurtainShowroomProducts,
  addBomItem,
} from '../lib/api'

/** 颜色名 → hex（seed 数据色板；未命中回退中性米白） */
const COLOR_MAP = {
  米白: '#e8e2d6', 雾霾蓝: '#aebcc9', 奶油: '#f0e6d2', 静谧灰: '#8a8a90',
  原麻: '#c9b98f', 藏青: '#2e3a52', 黛青: '#3e4a54', 米杏: '#e0cfa8',
  云朵白: '#f2f1ec', 浅粉: '#f0d8d8', 白纱: '#f4f2ee', 米金: '#d8c49a',
}

function colorToHex(name) {
  return COLOR_MAP[name] || '#d8d2c8'
}

/** 程序化面料纹理（无外部图依赖，诚实标注为示意纹理） */
function makeFabricTexture(fabric, colorName) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const ctx = canvas.getContext('2d')
  const base = colorToHex(colorName)
  const sheer = fabric === '纱'

  ctx.fillStyle = base
  ctx.fillRect(0, 0, 256, 256)

  if (sheer) {
    ctx.globalAlpha = 0.65
    ctx.fillStyle = base
    ctx.fillRect(0, 0, 256, 256)
    ctx.globalAlpha = 1
    ctx.strokeStyle = 'rgba(255,255,255,0.55)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 256; i += 6) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 256); ctx.stroke()
    }
  } else {
    // 织纹经纬线
    ctx.strokeStyle = 'rgba(0,0,0,0.06)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 256; i += 4) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 256); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(256, i); ctx.stroke()
    }
    if (fabric === '提花') {
      ctx.strokeStyle = 'rgba(0,0,0,0.10)'
      for (let x = -256; x < 512; x += 32) {
        for (let y = -256; y < 512; y += 32) {
          ctx.beginPath()
          ctx.moveTo(x, y + 8); ctx.lineTo(x + 8, y); ctx.lineTo(x + 16, y + 8); ctx.lineTo(x + 8, y + 16)
          ctx.closePath(); ctx.stroke()
        }
      }
    } else if (fabric === '雪尼尔') {
      ctx.fillStyle = 'rgba(255,255,255,0.10)'
      for (let i = 0; i < 900; i++) {
        ctx.fillRect(Math.random() * 256, Math.random() * 256, 2, 2)
      }
    } else if (fabric === '棉麻') {
      ctx.strokeStyle = 'rgba(255,255,255,0.12)'
      for (let i = 0; i <= 256; i += 16) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 256); ctx.stroke()
      }
    }
  }

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  return tex
}

function disposeObject(root) {
  root.traverse((obj) => {
    if (obj.isMesh) {
      obj.geometry?.dispose()
      if (obj.material) {
        if (obj.material.map) obj.material.map.dispose()
        obj.material.dispose()
      }
    }
  })
}

/** 程序化房间（地板/墙/顶/窗），诚实为 3D 示意场景 */
function buildRoom() {
  const g = new THREE.Group()
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(7.2, 7.2),
    new THREE.MeshStandardMaterial({ color: '#4a3f35', roughness: 0.9 }),
  )
  floor.rotation.x = -Math.PI / 2
  floor.position.y = -1.5
  floor.receiveShadow = true
  g.add(floor)

  const ceiling = new THREE.Mesh(
    new THREE.PlaneGeometry(7.2, 7.2),
    new THREE.MeshStandardMaterial({ color: '#e9e5dc', roughness: 0.9 }),
  )
  ceiling.rotation.x = Math.PI / 2
  ceiling.position.y = 3.2
  g.add(ceiling)

  const wallMat = new THREE.MeshStandardMaterial({ color: '#d8d2c8', roughness: 0.95 })
  const back = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.7), wallMat)
  back.position.set(0, 0.85, -2.5)
  g.add(back)
  const left = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.7), wallMat)
  left.rotation.y = Math.PI / 2
  left.position.set(-3.6, 0.85, 0)
  g.add(left)
  const right = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.7), wallMat)
  right.rotation.y = -Math.PI / 2
  right.position.set(3.6, 0.85, 0)
  g.add(right)

  // 窗外透光玻璃
  const glass = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 1.6),
    new THREE.MeshStandardMaterial({ color: '#9fc8e8', roughness: 0.1, metalness: 0.1 }),
  )
  glass.position.set(0, 1.6, -2.45)
  g.add(glass)
  return g
}

/** 按安装方式构建窗帘几何（含程序化面料纹理） */
function buildCurtain(renderType, fabric, colorName) {
  const group = new THREE.Group()
  const tex = makeFabricTexture(fabric, colorName)
  const sheer = fabric === '纱'
  const mat = new THREE.MeshStandardMaterial({
    map: tex, side: THREE.DoubleSide, roughness: 0.85, metalness: 0,
    transparent: sheer, opacity: sheer ? 0.55 : 1.0,
  })
  const width = 2.6
  const height = 1.9
  const topY = 2.45
  const bottomY = topY - height
  const z = -2.3

  const addFabric = (mesh) => {
    mesh.userData.isFabric = true
    group.add(mesh)
  }

  if (renderType === 'blind') {
    const slatCount = 20
    const slatH = height / slatCount
    for (let i = 0; i < slatCount; i++) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(width, slatH * 0.82), mat)
      m.position.set(0, topY - slatH * (i + 0.5), z)
      addFabric(m)
    }
    return group
  }

  if (renderType === 'roller') {
    const roll = new THREE.Mesh(
      new THREE.CylinderGeometry(0.09, 0.09, width, 16).rotateZ(Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: '#8a7a5a', roughness: 0.6 }),
    )
    roll.position.set(0, topY, z)
    group.add(roll)
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat)
    panel.position.set(0, (topY + bottomY) / 2, z)
    addFabric(panel)
    return group
  }

  // 罗马杆/轨道/挂钩/打孔：杆 + 褶皱帘（轨道为隐藏式细轨）
  if (renderType !== 'track') {
    const rod = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.05, width + 0.4, 16).rotateZ(Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: '#b99a6b', roughness: 0.5, metalness: 0.3 }),
    )
    rod.position.set(0, topY + 0.06, z - 0.02)
    group.add(rod)
  } else {
    const track = new THREE.Mesh(
      new THREE.BoxGeometry(width + 0.2, 0.03, 0.06),
      new THREE.MeshStandardMaterial({ color: '#6b6457', roughness: 0.5 }),
    )
    track.position.set(0, topY + 0.06, z - 0.02)
    group.add(track)
  }

  // 褶皱帘（正弦波折叠）
  const seg = 22
  const geo = new THREE.PlaneGeometry(width, height, seg, 1)
  const pos = geo.attributes.position
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i)
    pos.setZ(i, Math.sin((x / width) * Math.PI * 5) * 0.13)
  }
  geo.computeVertexNormals()
  const curtain = new THREE.Mesh(geo, mat)
  curtain.position.set(0, (topY + bottomY) / 2, z)
  addFabric(curtain)
  return group
}

function makeHotspotSprite() {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  ctx.beginPath()
  ctx.arc(32, 32, 24, 0, 2 * Math.PI)
  ctx.fillStyle = 'rgba(201, 151, 59, 0.92)'
  ctx.fill()
  ctx.lineWidth = 3
  ctx.strokeStyle = '#fff'
  ctx.stroke()
  ctx.font = 'bold 20px sans-serif'
  ctx.fillStyle = '#08080F'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('展', 32, 33)
  const tex = new THREE.CanvasTexture(canvas)
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }))
}

function applyLighting(w, lighting) {
  const c = new THREE.Color(lighting.light_color || '#ffffff')
  const intensity = lighting.ambient_intensity ?? 1.0
  w.ambient.color.copy(c)
  w.ambient.intensity = 0.35 * intensity + 0.15
  w.hemi.color.copy(c)
  w.hemi.intensity = 0.3 * intensity
  w.dir.color.copy(c)
  w.dir.intensity = 0.9 * intensity
  const bg = c.clone().multiplyScalar(0.32)
  w.scene.background = bg
  w.scene.fog = new THREE.Fog(bg, 6, 22)
}

/**
 * CurtainShowroom — 窗帘智能展厅（单店铺固定）
 *
 * 3D 程序化房间 + 窗帘贴图换装 + 时间/灯光 + 安装方式几何 + 热点加 BOM。
 * 诚实标注：3D 示意场景（非实景实拍），面料纹理为程序化生成（非实物照片）。
 */
export default function CurtainShowroom({ projectId }) {
  const mountRef = useRef(null)
  const worldRef = useRef(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [overview, setOverview] = useState(null)
  const [products, setProducts] = useState([])
  const [currentArea, setCurrentArea] = useState(null)
  const [currentInstallation, setCurrentInstallation] = useState(null)
  const [currentLighting, setCurrentLighting] = useState(null)
  const [currentProduct, setCurrentProduct] = useState(null)
  const [filters, setFilters] = useState({ series_id: null, brand: null, fabric: null })
  const [exhibit, setExhibit] = useState(null) // 热点/自选后的展品详情面板

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const [ov, pr] = await Promise.all([
      getCurtainShowroomOverview(),
      getCurtainShowroomProducts(),
    ])
    if (!ov.isSuccess || !ov.data?.showroom) {
      setError(ov.error || '窗帘展厅未配置')
      setLoading(false)
      return
    }
    const o = ov.data
    const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
    const area = o.areas?.[0] || null
    const installation = area?.installation || o.installations?.[0] || null
    const product = area?.default_product || list[0] || null
    const lighting = o.lighting_presets?.[0] || null
    setOverview(o)
    setProducts(list)
    setCurrentArea(area)
    setCurrentInstallation(installation)
    setCurrentProduct(product)
    setCurrentLighting(lighting)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const onHotspotRef = useRef(null)
  onHotspotRef.current = () => { if (currentProduct) setExhibit(currentProduct) }

  // ── 3D 世界（mount 一次）──
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    const width = mount.clientWidth || 720
    const height = mount.clientHeight || 540

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 100)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    mount.appendChild(renderer.domElement)

    const ambient = new THREE.AmbientLight('#ffffff', 0.5)
    const hemi = new THREE.HemisphereLight('#ffffff', '#3a3a3a', 0.3)
    const dir = new THREE.DirectionalLight('#ffffff', 1.1)
    dir.position.set(2.5, 4, 3.5)
    dir.castShadow = true
    scene.add(ambient, hemi, dir)

    scene.add(buildRoom())

    const curtainGroup = new THREE.Group()
    scene.add(curtainGroup)

    const hotspot = makeHotspotSprite()
    hotspot.scale.set(0.6, 0.6, 1)
    hotspot.position.set(0, 1.6, -2.15)
    scene.add(hotspot)

    const target = new THREE.Vector3(0, 1.4, 0)
    const state = { yaw: 0, pitch: 0.06, radius: 5.6 }
    const updateCamera = () => {
      camera.position.set(
        target.x + state.radius * Math.sin(state.yaw) * Math.cos(state.pitch),
        target.y + state.radius * Math.sin(state.pitch),
        target.z + state.radius * Math.cos(state.yaw) * Math.cos(state.pitch),
      )
      camera.lookAt(target)
    }
    updateCamera()

    worldRef.current = {
      scene, camera, renderer, ambient, hemi, dir, curtainGroup, hotspot, state, updateCamera,
    }

    let dragging = false
    let lastX = 0
    let lastY = 0
    const el = renderer.domElement
    const onDown = (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY }
    const onMove = (e) => {
      if (!dragging) return
      const dx = e.clientX - lastX
      const dy = e.clientY - lastY
      lastX = e.clientX
      lastY = e.clientY
      state.yaw += dx * 0.005
      state.pitch = Math.max(-0.4, Math.min(0.9, state.pitch + dy * 0.005))
      updateCamera()
    }
    const onUp = () => { dragging = false }
    const onWheel = (e) => {
      e.preventDefault()
      state.radius = Math.max(3.5, Math.min(9, state.radius + e.deltaY * 0.01))
      updateCamera()
    }
    const raycaster = new THREE.Raycaster()
    const onClick = (e) => {
      const rect = el.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(ndc, camera)
      if (raycaster.intersectObject(hotspot).length > 0) {
        onHotspotRef.current?.()
      }
    }
    el.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('click', onClick)
    el.style.cursor = 'grab'
    el.style.touchAction = 'none'

    let raf = requestAnimationFrame(function tick() {
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    })

    const resize = () => {
      const w = mount.clientWidth || width
      const h = mount.clientHeight || height
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(mount)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      el.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('click', onClick)
      disposeObject(scene)
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
      worldRef.current = null
    }
  }, [])

  // ── 换装（安装方式 / 展品变化时重建窗帘）──
  useEffect(() => {
    const w = worldRef.current
    if (!w || !currentProduct || !currentInstallation) return
    while (w.curtainGroup.children.length) {
      const c = w.curtainGroup.children[0]
      w.curtainGroup.remove(c)
      disposeObject(c)
    }
    const curtain = buildCurtain(
      currentInstallation.render_type, currentProduct.fabric, currentProduct.color,
    )
    w.curtainGroup.add(curtain)
  }, [currentInstallation, currentProduct])

  // ── 时间/灯光 ──
  useEffect(() => {
    const w = worldRef.current
    if (!w || !currentLighting) return
    applyLighting(w, currentLighting)
  }, [currentLighting])

  const selectProduct = (p) => {
    setCurrentProduct(p)
    setExhibit(p)
  }

  const randomSwap = () => {
    if (!filtered.length) return
    const p = filtered[Math.floor(Math.random() * filtered.length)]
    selectProduct(p)
  }

  const selectArea = (a) => {
    setCurrentArea(a)
    if (a?.installation) setCurrentInstallation(a.installation)
    if (a?.default_product) selectProduct(a.default_product)
  }

  const addToBom = async () => {
    if (!exhibit) return
    if (!exhibit.material_id) {
      setExhibit((e) => ({ ...e, action: { ok: false, msg: '该展品未关联物料，无法加入 BOM' } }))
      return
    }
    setExhibit((e) => ({ ...e, action: { busy: true } }))
    const r = await addBomItem({ project_id: projectId, material_id: exhibit.material_id, quantity: 1 })
    setExhibit((e) => ({
      ...e,
      action: r.isSuccess
        ? { ok: true, msg: '已加入 BOM（采购清单）' }
        : { ok: false, msg: r.error || '加入 BOM 失败' },
    }))
  }

  // 派生筛选
  const brandOptions = [...new Set(products.map((p) => p.brand).filter(Boolean))]
  const fabricOptions = [...new Set(products.map((p) => p.fabric).filter(Boolean))]
  const filtered = products.filter((p) => {
    if (filters.series_id && p.series_id !== filters.series_id) return false
    if (filters.brand && p.brand !== filters.brand) return false
    if (filters.fabric && p.fabric !== filters.fabric) return false
    return true
  })

  const toggleFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: f[key] === value ? null : value }))
  }

  if (loading) return <Spinner label="正在加载窗帘展厅…" />
  if (error) return <ErrorBox message={error} onRetry={load} />
  if (!overview) return <Empty message="窗帘展厅暂无数据" />

  return (
    <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
      {/* 3D 场景 */}
      <div style={{ flex: '1 1 480px', minWidth: 320 }}>
        <div
          ref={mountRef}
          style={{
            width: '100%', height: 560, borderRadius: 12, overflow: 'hidden',
            background: '#0a0c10', border: '1px solid var(--border)', position: 'relative',
          }}
        >
          <div style={{
            position: 'absolute', left: 10, top: 10, zIndex: 20, fontSize: 11,
            color: 'rgba(255,255,255,0.7)', background: 'rgba(10,12,16,0.6)',
            padding: '4px 8px', borderRadius: 6,
          }}
          >
            3D 示意场景 · 非实景实拍 · 面料纹理为程序化生成
          </div>
          <div style={{
            position: 'absolute', left: 10, bottom: 10, zIndex: 20, fontSize: 11,
            color: 'rgba(255,255,255,0.6)',
          }}
          >
            拖拽环视 · 滚轮缩放 · 点击金色「展」热点查看详情
          </div>

          {exhibit && (
            <div style={{
              position: 'absolute', right: 12, top: 12, width: 260, zIndex: 30,
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, padding: 14, boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <strong style={{ fontSize: 15 }}>{exhibit.name}</strong>
                <button
                  className="ghost"
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                  onClick={() => setExhibit(null)}
                  aria-label="关闭"
                >
                  <X size={18} />
                </button>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                {exhibit.brand || '无品牌'} · {exhibit.fabric}
                {exhibit.color ? ` · ${exhibit.color}` : ''}
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>
                ¥{Number(exhibit.unit_price || 0).toFixed(2)}
                <span style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 400 }}> / {exhibit.unit}</span>
              </div>
              {exhibit.description && (
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>{exhibit.description}</div>
              )}
              <button
                className="btn btn-primary"
                style={{ width: '100%', marginTop: 10 }}
                disabled={exhibit.action?.busy}
                onClick={addToBom}
              >
                {exhibit.action?.busy ? '加入中…' : '加入 BOM'}
              </button>
              {exhibit.action && !exhibit.action.busy && (
                <div style={{
                  marginTop: 8, fontSize: 12, padding: '6px 8px', borderRadius: 6,
                  background: exhibit.action.ok ? 'rgba(34, 197, 94, 0.12)' : 'rgba(220, 60, 60, 0.12)',
                  color: exhibit.action.ok ? 'var(--success, #22c55e)' : 'var(--danger, #dc3c3c)',
                }}
                >
                  {exhibit.action.msg}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 控制面板 */}
      <div style={{ flex: '0 0 320px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="card" style={{ padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
            <Store size={16} color="var(--primary, #C9973B)" />{overview.showroom.name}
          </div>
          {overview.showroom.description && (
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
              {overview.showroom.description}
            </div>
          )}
        </div>

        {/* 展示区域 */}
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Layers size={14} />展示区域
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {overview.areas.map((a) => (
              <button
                key={a.id}
                className={currentArea?.id === a.id ? 'btn btn-primary' : 'btn'}
                style={{ fontSize: 12, padding: '4px 10px', height: 'auto' }}
                onClick={() => selectArea(a)}
              >
                {a.name}
              </button>
            ))}
          </div>
        </div>

        {/* 安装方式 */}
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Wrench size={14} />安装方式
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {overview.installations.map((ins) => (
              <button
                key={ins.id}
                className={currentInstallation?.id === ins.id ? 'btn btn-primary' : 'btn'}
                style={{ fontSize: 12, padding: '4px 10px', height: 'auto' }}
                onClick={() => setCurrentInstallation(ins)}
              >
                {ins.name}
              </button>
            ))}
          </div>
        </div>

        {/* 时间/灯光 */}
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Lightbulb size={14} />时间 / 灯光
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {overview.lighting_presets.map((l) => (
              <button
                key={l.id}
                className={currentLighting?.id === l.id ? 'btn btn-primary' : 'btn'}
                style={{ fontSize: 12, padding: '4px 10px', height: 'auto' }}
                onClick={() => setCurrentLighting(l)}
              >
                {l.name}
              </button>
            ))}
          </div>
        </div>

        {/* 换装筛选 + 随机 */}
        <div className="card" style={{ padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Package size={14} />系列 / 品牌 / 材质换装
            </div>
            <button className="btn" style={{ fontSize: 12, padding: '4px 10px', height: 'auto' }} onClick={randomSwap}>
              <Shuffle size={13} style={{ verticalAlign: -2, marginRight: 4 }} />随机换装
            </button>
          </div>

          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>系列</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
            <Chip active={!filters.series_id} onClick={() => setFilters((f) => ({ ...f, series_id: null }))}>全部</Chip>
            {overview.series.map((s) => (
              <Chip key={s.id} active={filters.series_id === s.id} onClick={() => toggleFilter('series_id', s.id)}>{s.name}</Chip>
            ))}
          </div>

          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>品牌</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
            <Chip active={!filters.brand} onClick={() => setFilters((f) => ({ ...f, brand: null }))}>全部</Chip>
            {brandOptions.map((b) => (
              <Chip key={b} active={filters.brand === b} onClick={() => toggleFilter('brand', b)}>{b}</Chip>
            ))}
          </div>

          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>材质</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <Chip active={!filters.fabric} onClick={() => setFilters((f) => ({ ...f, fabric: null }))}>全部</Chip>
            {fabricOptions.map((f) => (
              <Chip key={f} active={filters.fabric === f} onClick={() => toggleFilter('fabric', f)}>{f}</Chip>
            ))}
          </div>
        </div>

        {/* 展品色卡 */}
        <div className="card" style={{ padding: 12, maxHeight: 260, overflowY: 'auto' }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>展品色卡（点击自选换装）</div>
          {filtered.length === 0 && <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>无匹配展品</div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(76px, 1fr))', gap: 8 }}>
            {filtered.map((p) => (
              <button
                key={p.id}
                onClick={() => selectProduct(p)}
                style={{
                  border: currentProduct?.id === p.id ? '2px solid var(--primary, #C9973B)' : '1px solid var(--border)',
                  borderRadius: 8, padding: 6, background: 'var(--bg, #f6f7f9)', cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                }}
              >
                <span style={{
                  width: '100%', height: 34, borderRadius: 4,
                  background: colorToHex(p.color), border: '1px solid var(--border)',
                }}
                />
                <span style={{ fontSize: 10, color: 'var(--text-dim)', textAlign: 'center', lineHeight: 1.2 }}>
                  {p.color || p.name}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Chip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 11, padding: '3px 8px', borderRadius: 20, cursor: 'pointer',
        border: active ? '1px solid var(--primary, #C9973B)' : '1px solid var(--border)',
        background: active ? 'rgba(201, 151, 59, 0.14)' : 'transparent',
        color: active ? 'var(--primary, #C9973B)' : 'var(--text-dim)',
      }}
    >
      {children}
    </button>
  )
}
