import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { X, Package, Shuffle, Lightbulb, Wrench, Layers, Store } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from './ui'
import { paintDeviceSprite } from './PanoramaViewer'
import DeviceCommandPanel from './DeviceCommandPanel'
import SceneTriggerOverlay from './SceneTriggerOverlay'
import useDeviceOverlay from '../hooks/useDeviceOverlay'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import {
  getCurtainShowroomOverview,
  getCurtainShowroomProducts,
  addBomItem,
  uploadCurtainTexture,
  getToken,
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

/** 颜色明暗调整（factor >0 变亮，<0 变暗） */
function shadeColor(hex, factor) {
  const c = new THREE.Color(hex)
  const target = factor > 0 ? 1.0 : 0.0
  const amt = Math.abs(factor)
  c.r += (target - c.r) * amt
  c.g += (target - c.g) * amt
  c.b += (target - c.b) * amt
  return `#${c.getHexString()}`
}

function makeCanvas(size) {
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  return c
}

/** 面料 albedo：平纹织造（经纬线明暗交织）+ 纤维噪声 + 材质专属纹理 */
function makeFabricAlbedo(fabric, colorName) {
  const S = 512
  const c = makeCanvas(S)
  const ctx = c.getContext('2d')
  const base = colorToHex(colorName)
  ctx.fillStyle = base
  ctx.fillRect(0, 0, S, S)

  if (fabric === '纱') {
    ctx.fillStyle = shadeColor(base, 0.12)
    ctx.fillRect(0, 0, S, S)
    ctx.strokeStyle = 'rgba(255,255,255,0.85)'
    ctx.lineWidth = 2
    for (let i = 0; i <= S; i += 16) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, S); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(S, i); ctx.stroke()
    }
  } else {
    const thread = fabric === '棉麻' ? 12 : 6
    for (let i = 0; i < S; i += thread) {
      const f = (i / thread) % 2 === 0 ? 0.06 : -0.06
      ctx.fillStyle = shadeColor(base, f)
      ctx.fillRect(i, 0, thread / 2, S)
      ctx.fillStyle = shadeColor(base, f * 0.7)
      ctx.fillRect(0, i, S, thread / 2)
    }
    for (let i = 0; i < 4000; i++) {
      ctx.fillStyle = shadeColor(base, Math.random() * 0.06 - 0.03)
      ctx.fillRect(Math.random() * S, Math.random() * S, 2, 2)
    }
    if (fabric === '提花') {
      ctx.strokeStyle = shadeColor(base, -0.16)
      ctx.lineWidth = 3
      for (let x = -S; x < S * 2; x += 48) {
        for (let y = -S; y < S * 2; y += 48) {
          ctx.beginPath()
          ctx.moveTo(x, y + 14); ctx.lineTo(x + 14, y)
          ctx.lineTo(x + 28, y + 14); ctx.lineTo(x + 14, y + 28)
          ctx.closePath(); ctx.stroke()
        }
      }
    } else if (fabric === '雪尼尔') {
      for (let i = 0; i < 12000; i++) {
        ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.12})`
        ctx.fillRect(Math.random() * S, Math.random() * S, 1.5, 1.5)
      }
    }
  }

  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  tex.anisotropy = 8
  return tex
}

/** 面料 bump（灰度凹凸）：织纹凸起 */
function makeFabricBump(fabric) {
  const S = 256
  const c = makeCanvas(S)
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#808080'
  ctx.fillRect(0, 0, S, S)
  const thread = fabric === '棉麻' ? 16 : 8
  ctx.strokeStyle = '#c8c8c8'
  ctx.lineWidth = 3
  for (let i = 0; i <= S; i += thread) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, S); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(S, i); ctx.stroke()
  }
  const tex = new THREE.CanvasTexture(c)
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  return tex
}

/** 面料 roughness（灰度）：丝绸类更光滑、棉麻更粗糙 */
function makeFabricRoughness(fabric) {
  const S = 256
  const c = makeCanvas(S)
  const ctx = c.getContext('2d')
  const base = fabric === '提花' || fabric === '雪尼尔' ? 70 : fabric === '棉麻' || fabric === '纱' ? 150 : 110
  ctx.fillStyle = `rgb(${base},${base},${base})`
  ctx.fillRect(0, 0, S, S)
  ctx.fillStyle = `rgb(${base + 20},${base + 20},${base + 20})`
  for (let i = 0; i <= S; i += 8) {
    ctx.fillRect(i, 0, 2, S)
    ctx.fillRect(0, i, S, 2)
  }
  const tex = new THREE.CanvasTexture(c)
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  return tex
}

/** 组合 PBR 面料材质（albedo + bump + roughness + sheen 丝绸高光） */
function makeFabricMaterial(fabric, colorName) {
  const silky = fabric === '提花' || fabric === '雪尼尔'
  const sheer = fabric === '纱'
  return new THREE.MeshPhysicalMaterial({
    map: makeFabricAlbedo(fabric, colorName),
    bumpMap: makeFabricBump(fabric),
    bumpScale: fabric === '提花' ? 0.10 : 0.06,
    roughnessMap: makeFabricRoughness(fabric),
    roughness: 0.85,
    metalness: 0.0,
    side: THREE.DoubleSide,
    transparent: sheer,
    opacity: sheer ? 0.55 : 1.0,
    sheen: silky ? 1.0 : 0.0,
    sheenColor: new THREE.Color(colorToHex(colorName)),
    sheenRoughness: 0.55,
  })
}

/** 加载需鉴权的贴图（fetch + PASETO → Blob → THREE.Texture），失败由调用方回退程序化 */
async function loadAuthedTexture(url) {
  const token = getToken()
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw new Error(`贴图加载失败 HTTP ${res.status}`)
  const blob = await res.blob()
  const objUrl = URL.createObjectURL(blob)
  const img = new Image()
  await new Promise((resolve, reject) => {
    img.onload = resolve
    img.onerror = () => reject(new Error('图片解码失败'))
    img.src = objUrl
  })
  URL.revokeObjectURL(objUrl)
  const tex = new THREE.Texture(img)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  tex.needsUpdate = true
  return tex
}

function disposeObject(root) {
  root.traverse((obj) => {
    if (obj.isMesh) {
      obj.geometry?.dispose()
      const m = obj.material
      if (m) {
        ;['map', 'bumpMap', 'roughnessMap', 'normalMap', 'alphaMap', 'displacementMap', 'metalnessMap'].forEach((k) => {
          if (m[k]) m[k].dispose()
        })
        m.dispose()
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

/** 按安装方式构建窗帘几何（PBR 面料 + 预模拟褶皱） */
function buildCurtain(renderType, fabric, colorName) {
  const group = new THREE.Group()
  const mat = makeFabricMaterial(fabric, colorName)
  const width = 2.6
  const height = 1.9
  const topY = 2.45
  const bottomY = topY - height
  const z = -2.3

  const addFabric = (mesh) => {
    mesh.userData.isFabric = true
    mesh.castShadow = true
    mesh.receiveShadow = true
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

  // 褶皱帘：多重褶皱 + 中部鼓出 + 顶部聚拢（预模拟垂坠感）
  const segX = 48
  const segY = 24
  const geo = new THREE.PlaneGeometry(width, height, segX, segY)
  const pos = geo.attributes.position
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i)
    const y = pos.getY(i)
    const t = x / width           // -0.5..0.5
    const v = y / height + 0.5    // 0=底, 1=顶
    const folds = Math.sin(t * Math.PI * 6) * 0.16 + Math.sin(t * Math.PI * 11 + 1.7) * 0.05
    const gather = 0.55 + v * 0.45      // 顶部聚拢、底部舒展
    const billow = Math.cos(t * Math.PI) * 0.10 // 中部鼓出
    pos.setZ(i, folds * gather + billow)
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

/** 智能家居设备 Sprite（复用 P0 设备热点着色：在线绿/离线灰/激活橙） */
function makeDeviceSprite(device) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  paintDeviceSprite(canvas, device)
  const tex = new THREE.CanvasTexture(canvas)
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }))
  const yawRad = ((device.yaw ?? 0) * Math.PI) / 180
  const pitchRad = ((device.pitch ?? 0) * Math.PI) / 180
  const r = 3.0
  const phi = Math.PI / 2 - pitchRad
  const theta = Math.PI - yawRad
  // 球坐标（yaw=0 → -z 正前方），抬高到房间观察中心 y=1.4
  sprite.position.set(
    r * Math.sin(phi) * Math.sin(theta),
    1.4 + r * Math.cos(phi),
    r * Math.sin(phi) * Math.cos(theta),
  )
  sprite.scale.set(0.5, 0.5, 1)
  return sprite
}

function applyLighting(w, lighting) {
  const c = new THREE.Color(lighting.light_color || '#ffffff')
  const intensity = lighting.ambient_intensity ?? 1.0
  w.ambient.color.copy(c)
  w.ambient.intensity = 0.12 * intensity + 0.06
  w.dir.color.copy(c)
  w.dir.intensity = 1.0 * intensity
  w.scene.environmentIntensity = 0.45 * intensity + 0.1
  const bg = c.clone().multiplyScalar(0.30)
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
  const [selectedDevice, setSelectedDevice] = useState(null) // 点击的智能家居设备

  // 智能家居设备图层（复用 P0 设备热点联动：加载 + WS/轮询 + 命令/场景/传感器）
  const { devices, latestSensor, sendCommand, triggerScene, sceneFlash } = useDeviceOverlay(projectId)
  const devicesRef = useRef([])
  const deviceSpritesRef = useRef([])
  const onDeviceClickRef = useRef(null)
  onDeviceClickRef.current = (d) => setSelectedDevice(d)

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

  // ── 3D 世界（overview 加载后构建；此前 loading 早返回致 mountRef 尚未渲染）──
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
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    mount.appendChild(renderer.domElement)

    // PBR：HDRI 环境光（IBL）+ 低环境光 + 单一方向光（软阴影）
    const pmrem = new THREE.PMREMGenerator(renderer)
    const envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = envMap
    scene.environmentIntensity = 0.55

    const ambient = new THREE.AmbientLight('#ffffff', 0.15)
    const dir = new THREE.DirectionalLight('#ffffff', 1.3)
    dir.position.set(2.5, 4, 3.5)
    dir.castShadow = true
    dir.shadow.mapSize.set(1024, 1024)
    dir.shadow.bias = -0.0002
    scene.add(ambient, dir)

    scene.add(buildRoom())

    const curtainGroup = new THREE.Group()
    scene.add(curtainGroup)

    const hotspot = makeHotspotSprite()
    hotspot.scale.set(0.6, 0.6, 1)
    hotspot.position.set(0, 1.6, -2.15)
    scene.add(hotspot)

    // 智能家居设备图层容器（设备 Sprite 随 devices 变化重建）
    const deviceGroup = new THREE.Group()
    scene.add(deviceGroup)
    const rebuildDeviceSprites = (list) => {
      while (deviceGroup.children.length) {
        const s = deviceGroup.children[0]
        deviceGroup.remove(s)
        s.material?.map?.dispose()
        s.material?.dispose()
      }
      const sprites = (list || []).map((d) => makeDeviceSprite(d))
      sprites.forEach((s) => deviceGroup.add(s))
      deviceSpritesRef.current = sprites
    }

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
      scene, camera, renderer, ambient, dir, curtainGroup, hotspot, state, updateCamera,
      rebuildDeviceSprites, pmrem, envMap,
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
      const hit = raycaster.intersectObjects([hotspot, ...deviceSpritesRef.current])[0]
      if (!hit) return
      if (hit.object === hotspot) {
        onHotspotRef.current?.()
        return
      }
      const idx = deviceSpritesRef.current.indexOf(hit.object)
      if (idx >= 0) onDeviceClickRef.current?.(devicesRef.current[idx])
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
      envMap?.dispose()
      pmrem?.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
      worldRef.current = null
    }
  }, [overview])

  // ── 智能家居设备图层：devices 变化时重建 Sprite（含激活/状态色）──
  useEffect(() => {
    devicesRef.current = devices
    worldRef.current?.rebuildDeviceSprites?.(devices)
  }, [devices])

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
    // 已上传真实贴图 → 异步加载替换 albedo；失败静默回退程序化
    if (currentProduct.texture_url) {
      loadAuthedTexture(currentProduct.texture_url).then((tex) => {
        curtain.traverse((obj) => {
          if (obj.isMesh && obj.userData.isFabric) {
            obj.material.map?.dispose()
            obj.material.map = tex
            obj.material.needsUpdate = true
          }
        })
      }).catch(() => {})
    }
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

  // 真实面料贴图上传
  const textureFileRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const handleTextureUpload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !exhibit) return
    setUploading(true)
    setExhibit((ex) => ({ ...ex, textureMsg: { busy: true } }))
    const r = await uploadCurtainTexture(exhibit.id, file)
    if (r.isSuccess && r.data) {
      const url = r.data.texture_url
      setCurrentProduct((p) => (p && p.id === r.data.id ? { ...p, texture_url: url } : p))
      setProducts((list) => list.map((p) => (p.id === r.data.id ? { ...p, texture_url: url } : p)))
      setExhibit((ex) => ({ ...ex, texture_url: url, textureMsg: { ok: true, msg: '真实贴图已上传并替换' } }))
    } else {
      setExhibit((ex) => ({ ...ex, textureMsg: { ok: false, msg: r.error || '上传失败' } }))
    }
    setUploading(false)
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
            3D 场景 · 支持上传真实面料贴图（默认程序化纹理）
          </div>
          <div style={{
            position: 'absolute', left: 10, bottom: 10, zIndex: 20, fontSize: 11,
            color: 'rgba(255,255,255,0.6)',
          }}
          >
            拖拽环视 · 滚轮缩放 · 点「展」看展品加 BOM · 点设备图标控制智能家居
          </div>
          {latestSensor && (
            <div style={{
              position: 'absolute', right: 10, bottom: 10, zIndex: 20, fontSize: 11,
              color: 'rgba(255,255,255,0.75)', background: 'rgba(10,12,16,0.6)',
              padding: '4px 8px', borderRadius: 6,
            }}
            >
              环境 {latestSensor.temperature != null ? `${latestSensor.temperature}°C` : '-'}
              · 湿度 {latestSensor.humidity != null ? `${latestSensor.humidity}%` : '-'}
              · 光照 {latestSensor.light_lux != null ? `${latestSensor.light_lux}lux` : '-'}
            </div>
          )}

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
              <input
                ref={textureFileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                onChange={handleTextureUpload}
              />
              <button
                className="btn"
                style={{ width: '100%', marginTop: 6, fontSize: 12 }}
                disabled={uploading}
                onClick={() => textureFileRef.current?.click()}
              >
                {uploading ? '上传中…' : exhibit.texture_url ? '替换真实面料贴图' : '上传真实面料贴图'}
              </button>
              {exhibit.textureMsg && (
                <div style={{
                  marginTop: 6, fontSize: 11, padding: '5px 8px', borderRadius: 6,
                  background: exhibit.textureMsg.ok ? 'rgba(34, 197, 94, 0.12)' : 'rgba(220, 60, 60, 0.12)',
                  color: exhibit.textureMsg.ok ? 'var(--success, #22c55e)' : 'var(--danger, #dc3c3c)',
                }}
                >
                  {exhibit.textureMsg.msg}
                </div>
              )}
            </div>
          )}
          {selectedDevice && (
            <DeviceCommandPanel
              device={selectedDevice}
              sensor={latestSensor}
              onClose={() => setSelectedDevice(null)}
              onCommand={(device, action) => sendCommand(device, action)}
              onScene={(sceneId) => triggerScene(sceneId)}
            />
          )}
          <SceneTriggerOverlay flash={sceneFlash} />
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
