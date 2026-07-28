/**
 * 业务领域类型 — 对齐后端 schemas（app/schemas/）
 *
 * 字段命名与后端 snake_case 一致（后端返回 snake_case，前端直接消费）。
 * 仅声明 Web 控制台实际使用的字段。
 */

// ── 用户（对齐 app/schemas/user.py:UserResponse）──
export interface User {
  id: string;
  phone: string;
  name: string;
  role: string;
  sub_role?: string | null;
  avatar_url?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

// ── 项目（对齐 app/schemas/project.py）──
export type ProjectType =
  | 'full_renovation'
  | 'hard_decoration'
  | 'soft_furnishing'
  | 'curtain'
  | 'kitchen'
  | 'bathroom'
  | 'electrical'
  | 'carpentry'
  | 'painting'
  | 'plumbing'
  | 'masonry'
  | 'installation';

export type ProjectStatus =
  | 'planning'
  | 'design'
  | 'construction'
  | 'inspection'
  | 'settlement'
  | 'completed'
  | 'archived'
  | string;

export interface Project {
  id: string;
  name: string;
  address?: string | null;
  total_area?: number | null;
  status: ProjectStatus;
  project_type: ProjectType | string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  name: string;
  address?: string;
  total_area?: number;
  project_type?: ProjectType | string;
  source?: 'manual' | 'ar_measure';
}

// ── 预算（对齐 app/schemas/budget.py）──
export interface BudgetItem {
  id?: string;
  line_name: string;
  category?: string;
  amount: number;
  spent_amount?: number;
  note?: string;
}

export interface Budget {
  id: string;
  project_id: string;
  total_amount: number;
  spent_amount?: number;
  items: BudgetItem[];
  created_at?: string;
  updated_at?: string;
}

// ── 施工任务（对齐 app/schemas/construction.py:TaskResponse）──
// 后端状态约束：pending | in_progress | ready | paused | completed | cancelled
export type ConstructionTaskStatus =
  | 'pending'
  | 'in_progress'
  | 'ready'
  | 'paused'
  | 'completed'
  | 'cancelled'
  | string;

export interface ConstructionTask {
  id: string;
  project_id: string;
  name: string;
  phase: string;
  assigned_to?: string | null;
  status: ConstructionTaskStatus;
  priority: number;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 采购订单（对齐 app/schemas/procurement.py:OrderResponse）──
// 后端订单状态：draft | pending | confirmed | shipped | delivered | cancelled
// 后端物流状态 delivery_status：pending | shipping | in_transit | delivered | delayed | cancelled
export type OrderStatus = 'draft' | 'pending' | 'confirmed' | 'shipped' | 'delivered' | 'cancelled' | string;
export type DeliveryStatus = 'pending' | 'shipping' | 'in_transit' | 'delivered' | 'delayed' | 'cancelled' | string;

export interface OrderLine {
  id: string;
  material_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  note?: string | null;
  delivered_quantity?: number;
}

export interface ProcurementOrder {
  id: string;
  project_id: string;
  supplier_id: string;
  total_amount: number;
  status: OrderStatus;
  expected_delivery?: string | null;
  note?: string | null;
  lines?: OrderLine[];
  // A5 采购交付透明度
  delivery_status?: DeliveryStatus | null;
  tracking_number?: string | null;
  carrier?: string | null;
  estimated_delivery_date?: string | null;
  actual_delivery_date?: string | null;
  delivery_address?: string | null;
  assembly_required?: boolean;
  assembly_difficulty?: string | null;
  delivery_notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

// ── 结算（对齐 app/schemas/settlement.py:SettlementResponse）──
export interface SettlementLine {
  id: string;
  category: string;
  name: string;
  contract_amount: number;
  change_amount: number;
  actual_amount: number;
  status: string;
  note?: string | null;
  is_anomaly: boolean;
  anomaly_type?: string | null;
  anomaly_severity?: string | null;
  anomaly_detail?: string | null;
}

export interface Settlement {
  id: string;
  project_id: string;
  milestone: string;
  contract_amount: number;
  actual_amount: number;
  payable_amount: number;
  status: string;
  anomaly_count: number;
  critical_anomaly_count: number;
  suggested_deduction: number;
  review_required: boolean;
  review_reason?: string | null;
  lines: SettlementLine[];
  settled_at?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 任务协调（对齐 app/schemas/task.py:TaskResponse / TaskListResponse）──
// 后端 TaskListResponse 字段为 { tasks, total }（非 items）
export interface TaskItem {
  id: string;
  project_id: string;
  task_type: string;
  title: string;
  description?: string | null;
  assigned_agent: string;
  assigned_user_id?: string | null;
  assigned_user_name?: string | null;
  priority: number;
  status: string;
  parent_task_id?: string | null;
  dependencies?: string[] | null;
  claimable: boolean;
  claim_deadline?: string | null;
  claim_role?: string | null;
  result?: Record<string, unknown> | null;
  created_by: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TaskListResponse {
  tasks: TaskItem[];
  total: number;
}

// ── 物料（对齐 app/schemas/material.py）──
export interface MaterialCategory {
  id: string;
  name: string;
  code: string;
  description?: string | null;
  created_at: string;
}

export interface Material {
  id: string;
  category_id: string;
  name: string;
  sku: string;
  unit: string;
  unit_price: number;
  brand?: string | null;
  spec?: string | null;
  image_url?: string | null;
  description?: string | null;
  is_active: boolean;
  category?: MaterialCategory | null;
  created_at: string;
  updated_at: string;
}

// ── 变更管理（对齐 app/schemas/change_order.py）──
// 后端状态：pending | reviewing | approved | rejected | cancelled | completed
// 可行性：feasible | infeasible | partial
export interface ChangeOrderItem {
  id: string;
  change_order_id: string;
  name: string;
  action: 'add' | 'modify' | 'remove' | string;
  target_type: string;
  target_id?: string | null;
  before_data?: string | null;
  after_data?: string | null;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface ChangeOrder {
  id: string;
  project_id: string;
  title: string;
  description: string;
  change_type: string;
  feasibility?: string | null;
  feasibility_note?: string | null;
  cost_impact: number;
  schedule_impact_days: number;
  design_impact?: string | null;
  status: string;
  submitted_by?: string | null;
  reviewed_by?: string | null;
  approved_by?: string | null;
  submitted_at: string;
  reviewed_at?: string | null;
  approved_at?: string | null;
  items: ChangeOrderItem[];
  created_at: string;
  updated_at: string;
}

// ── 工程队（对齐 app/schemas/construction_crew.py）──
export interface ConstructionCrew {
  id: string;
  name: string;
  leader: string;
  phone?: string | null;
  city?: string | null;
  district?: string | null;
  qualification: string;
  specialties: string[];
  rating: number;
  completed_projects: number;
  avg_duration: number;
  daily_rate: number;
  status: string;
  introduction?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrewMatch {
  id: string;
  project_id: string;
  crew_id: string;
  match_score: number;
  score_breakdown?: Record<string, unknown>;
  recommendation?: string | null;
  status: string;
  crew?: ConstructionCrew | null;
  created_at: string;
  updated_at: string;
}

// ── 智能家居方案（对齐 app/schemas/smart_home.py）──
// 后端状态：draft | planned | installing | completed
export interface SmartHomeScheme {
  id: string;
  project_id: string;
  room_name: string;
  room_type: string;
  protocol: string;
  hub_brand: string;
  device_count: number;
  total_price: number;
  status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 场景自动化（对齐 app/schemas/scene_automation.py）──
// scene_type: manual | scheduled | triggered | geo
export interface SceneAutomation {
  id: string;
  project_id: string;
  scheme_id?: string | null;
  scene_name: string;
  scene_type: string;
  trigger_condition?: string | null;
  actions: unknown[];
  enabled: boolean;
  priority: number;
  created_at: string;
  updated_at: string;
}

// ── 户型（对齐 app/schemas/floorplan.py:FloorPlanListItem）──
export interface FloorPlan {
  id: string;
  project_id: string;
  name: string;
  total_area: number;
  room_count: number;
  wall_height: number;
  updated_at: string;
}

// ── 灯光设计（对齐 app/schemas/lighting.py:LightingSchemeResponse）──
// scheme_type: main_light | none_main | mixed | scene
export interface LightingScheme {
  id: string;
  project_id: string;
  room_name: string;
  scheme_type: string;
  room_area: number;
  ceiling_height: number;
  total_lumens?: number | null;
  total_power_w?: number | null;
  color_temp_k?: number | null;
  cri?: number | null;
  ugpr?: number | null;
  status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 软装设计（对齐 app/schemas/soft_furnishing.py:SoftFurnishingSchemeResponse）──
// style: modern | 现代 | 北欧 | 新中式 | 美式 | 法式 | 工业 | 日式
export interface SoftFurnishingScheme {
  id: string;
  project_id: string;
  room_name: string;
  style: string;
  color_scheme?: Record<string, unknown> | null;
  budget_total: number;
  budget_used: number;
  status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 厨房设计（对齐 app/schemas/kitchen.py:KitchenDesignResponse）──
// layout_type: L | U | I | G | double_i | island
export interface KitchenDesign {
  id: string;
  project_id: string;
  room_name: string;
  layout_type: string;
  room_width: number;
  room_length: number;
  ceiling_height: number;
  counter_height: number;
  counter_depth: number;
  water_inlet_pos?: string | null;
  drain_pos?: string | null;
  gas_pos?: string | null;
  vent_pos?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── 卫浴设计（对齐 app/schemas/bathroom.py:BathroomDesignResponse）──
// layout_type: dry_wet_separation | three_separation | traditional | single
export interface BathroomDesign {
  id: string;
  project_id: string;
  room_name: string;
  layout_type: string;
  room_width: number;
  room_length: number;
  ceiling_height: number;
  dry_area?: number | null;
  wet_area?: number | null;
  floor_drain_count: number;
  waterproof_height_mm: number;
  drain_slope_percent: number;
  status: string;
  has_natural_window: boolean;
  window_area_m2?: number | null;
  mechanical_vent_airflow?: number | null;
  created_at: string;
  updated_at: string;
}

// ── 门窗规格（对齐 app/schemas/door_window_waterproof.py:DoorWindowSpecResponse）──
// spec_type: entry_door | interior_door | window | sliding_door | french_window
// material: solid_wood | wood_composite | aluminum | pvc | steel
export interface DoorWindowSpec {
  id: string;
  project_id: string;
  room_name: string;
  location?: string | null;
  spec_type: string;
  material: string;
  width: number;
  height: number;
  thickness?: number | null;
  opening_direction: string;
  glass_type?: string | null;
  brand?: string | null;
  model?: string | null;
  price: number;
  has_screen: boolean;
  has_lock: boolean;
  notes?: string | null;
  created_at: string;
  updated_at?: string;
}

// ── 防水方案（对齐 app/schemas/door_window_waterproof.py:WaterproofPlanResponse）──
export interface WaterproofPlan {
  id: string;
  project_id: string;
  room_name: string;
  room_type: string;
  wall_height_mm: number;
  floor_area: number;
  wall_area: number;
  waterproof_material: string;
  coating_layers: number;
  thickness_mm: number;
  closure_test_hours: number;
  material_quantity: number;
  unit_price: number;
  total_price: number;
  status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── 工程量正向算量（对齐 app/services/quantity_takeoff_service.py:ForwardTakeoffResult）──
// 端点：GET /api/takeoff/project/{projectId}（app/api/takeoff.py:117，flag: forward_takeoff_enabled）
export interface TakeoffSummary {
  total_brick_count: number;
  total_mortar_m3: number;
  total_tile_count: number;
  total_paint_area_m2: number;
  total_ceiling_area_m2: number;
  total_wall_length_m: number;
  total_floor_area_m2: number;
  wall_height_m: number;
  door_count: number;
  window_count: number;
}

export interface WallTakeoffItem {
  name: string;
  length: number;
  height: number;
  thickness: number;
  volume: number;
  area: number;
  brick_count: number;
  mortar_volume: number;
  paint_area: number;
}

export interface FloorTakeoffItem {
  name: string;
  area: number;
  tile_size: string;
  tile_count: number;
  mortar_volume: number;
}

export interface CeilingTakeoffItem {
  name: string;
  area: number;
  board_count: number;
}

export interface PaintTakeoffItem {
  name: string;
  area: number;
  primer_count: number;
  finish_count: number;
  total_paint_liters: number;
}

export interface ForwardTakeoffResult {
  project_id: string;
  floorplan_id: string;
  floorplan_name: string;
  walls: WallTakeoffItem[];
  floors: FloorTakeoffItem[];
  ceilings: CeilingTakeoffItem[];
  paints: PaintTakeoffItem[];
  summary: TakeoffSummary;
  reply: string;
  geometry: Record<string, unknown>;
}

// ── 土建结构（对齐 app/schemas/structural.py）──
// 端点：GET /api/structural/projects/{projectId}/{walls|beams|columns|slabs}
export interface LoadBearingWall {
  id: string;
  project_id: string;
  room_id: string | null;
  wall_name: string;
  is_load_bearing: boolean;
  thickness_mm: number;
  length_m: number;
  height_m: number;
  material: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Beam {
  id: string;
  project_id: string;
  beam_name: string;
  beam_type: string;
  width_mm: number;
  height_mm: number;
  length_m: number;
  material: string;
  concrete_grade: string | null;
  position_desc: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface StructuralColumn {
  id: string;
  project_id: string;
  column_name: string;
  column_type: string;
  width_mm: number;
  depth_mm: number;
  height_m: number;
  material: string;
  concrete_grade: string | null;
  position_desc: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FloorSlab {
  id: string;
  project_id: string;
  slab_name: string;
  slab_type: string;
  thickness_mm: number;
  area_m2: number;
  concrete_grade: string | null;
  rebar_diameter_mm: number | null;
  rebar_spacing_mm: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ── 家电（对齐 app/schemas/appliance.py）──
// 端点：GET /api/appliance/categories + GET /api/appliance/search
export interface ApplianceCategory {
  id: string;
  name: string;
  code: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Appliance {
  id: string;
  category_id: string;
  name: string;
  brand: string | null;
  model: string | null;
  subcategory: string;
  spec: string | null;
  power_rating: number | null;
  energy_label: string | null;
  price: number;
  install_requirements: Record<string, unknown> | null;
  dimensions: Record<string, unknown> | null;
  weight_kg: number | null;
  image_url: string | null;
  tags: string[] | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── 产品/服务（对齐 app/schemas/product.py:ProductResponse）──
// 端点：GET /api/products（全局列表，user 维度）
export interface Product {
  id: string;
  user_id: string;
  supplier_id: string;
  name: string;
  category: string;
  description: string | null;
  price_min: number | null;
  price_max: number | null;
  unit: string;
  images: string[] | null;
  cover_image: string | null;
  tags: string[] | null;
  specs: Record<string, unknown> | null;
  stock_status: string;
  status: string;
  ai_generated: boolean;
  ai_description: string | null;
  created_at: string;
  updated_at: string;
}

// ── 家具品类库（对齐 app/schemas/furniture_catalog.py:FurnitureCatalogItemResponse）──
// 端点：GET /api/furniture-catalog（全局列表）
export interface FurnitureCatalogItem {
  id: string;
  category: string;
  subcategory: string;
  name: string;
  brand: string | null;
  model: string | null;
  width: number | null;
  depth: number | null;
  height: number | null;
  weight_kg: number | null;
  material: string | null;
  color: string | null;
  style: string;
  price: number;
  sale_price: number | null;
  image_url: string | null;
  model_3d_url: string | null;
  ar_preview_supported: boolean;
  stock_count: number;
  rating: number;
  sales_count: number;
  view_count: number;
  tags: string[] | null;
  specs: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── 硬装方案（对齐 app/schemas/hard_decoration.py:HardDecorationSchemeResponse）──
// 端点：GET /api/hard-decoration/schemes/project/{projectId}
export interface HardDecorationScheme {
  id: string;
  project_id: string;
  room_name: string;
  scheme_type: string;
  floor_area: number;
  wall_area: number;
  ceiling_area: number;
  total_budget: number;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ── 水电暖通标准（对齐 app/services/mep_service.py:ROOM_MEP_STANDARDS）──
// 端点：GET /api/mep/room-standards/{room_type}
export interface MepPointDetail {
  name: string;
  height: number;
  count: number;
  type: string;
}

export interface MepRoomStandard {
  name: string;
  switches: number;
  sockets: number;
  lights: number;
  network: number;
  tv?: number;
  ac: number;
  details: MepPointDetail[];
  // 错误响应字段
  error?: string;
  available?: string[];
}

// ── VR 全景图（对齐 app/schemas/vr_panorama.py:VRPanoramaListItem）──
// 端点：GET /api/vr/panoramas/project/{projectId}
export interface VRPanoramaListItem {
  id: string;
  project_id: string;
  room_name: string;
  panorama_type: string;
  image_url: string | null;
  thumbnail_url: string | null;
  resolution: string;
  initial_view: Record<string, unknown> | null;
  hotspots: Array<Record<string, unknown>>;
  status: string;
  created_at: string;
}

// ── 定制家具设计（对齐 app/schemas/custom_furniture.py）──
// 端点：
//   GET /api/custom-furniture/designs/project/{projectId}
//   GET /api/custom-furniture/designs/{designId}/modules
//   GET /api/custom-furniture/designs/{designId}/bom
//   GET /api/custom-furniture/designs/{designId}/price
//   GET /api/custom-furniture/designs/{designId}/panels
//   GET /api/custom-furniture/designs/{designId}/validation
export interface CustomFurnitureDesign {
  id: string;
  project_id: string;
  room_name: string;
  furniture_type: string;
  total_width: number;
  total_height: number;
  total_depth: number;
  panel_material: string;
  panel_thickness: number;
  edge_banding: string;
  hardware_brand: string;
  color: string | null;
  style: string;
  total_price: number;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FurnitureModule {
  id: string;
  design_id: string;
  module_type: string;
  position_index: number;
  width: number;
  height: number;
  depth: number;
  quantity: number;
  material: string | null;
  color: string | null;
  hardware_specs: Record<string, unknown> | null;
  price: number;
  created_at: string;
  updated_at: string;
}

export interface FurnitureBOMItem {
  id: string;
  design_id: string;
  item_name: string;
  item_type: string;
  spec: string | null;
  material: string | null;
  quantity: number;
  unit: string;
  unit_price: number;
  total_price: number;
  supplier: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FurniturePriceEstimate {
  panel_cost: number;
  hardware_cost: number;
  door_cost: number;
  process_cost: number;
  total_price: number;
}

export interface FurniturePanelCompute {
  total_panel_area_m2: number;
  panel_sheets: number;
  hardware_list: Array<Record<string, unknown>>;
}

export interface FurnitureValidation {
  valid: boolean;
  issues: Array<Record<string, unknown>>;
}

// ── 质量问题（对齐 app/schemas/quality.py:QualityIssueResponse）──
// 端点：
//   GET /api/construction/quality-issues/{projectId}?phase=&status=&severity=
//   GET /api/construction/quality-checklist/{phase}
export interface QualityIssue {
  id: string;
  project_id: string;
  task_id: string | null;
  inspection_id: string | null;
  phase: string;
  category: string;
  description: string;
  severity: string;
  status: string;
  images: string | null;
  detected_by: string;
  standard: string | null;
  location: string | null;
  resolution: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QualityChecklistItem {
  item: string;
  standard: string;
  method: string;
}

export interface QualityChecklist {
  phase: string;
  total_items: number;
  checklist: QualityChecklistItem[];
  reply: string;
}

// ── AI 渲染能力（对齐 app/api/ai_render.py:get_capabilities 返回）──
// 端点：GET /api/ai-render/capabilities
export interface AIRenderCapabilities {
  styles: string[];
  restage_modes: string[];
  render_types: string[];
  note: string;
}

// ── CAD 导入（对齐 app/api/cad_import.py:CADImportResult）──
// 端点：POST /api/cad-import/dxf（multipart upload）
export interface CADImportResult {
  file_type: string; // dxf | dwg
  entity_count: number;
  lines: Array<{ x1: number; y1: number; x2: number; y2: number }>;
  polylines: Array<Array<{ x: number; y: number }>>;
  circles: Array<{ x: number; y: number; r: number }>;
  arcs: Array<{ x: number; y: number; r: number; start_angle: number; end_angle: number }>;
  texts: Array<{ x: number; y: number; text: string; height: number }>;
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number; width: number; height: number } | null;
  converted_from_dwg: boolean;
}

// ── 草图转 3D（对齐 app/api/sketch_to_3d.py）──
// 端点：POST /api/sketch-to-3d/analyze（multipart）+ POST /api/sketch-to-3d/generate-3d（multipart）
//      GET /api/sketch-to-3d/supported-formats
export interface SketchAnalysisResult {
  sketch_id: string;
  detected_walls: Array<Record<string, unknown>>;
  detected_doors: Array<Record<string, unknown>>;
  detected_windows: Array<Record<string, unknown>>;
  estimated_area: number;
  room_count: number;
  confidence: number;
  raw_layout: Record<string, unknown>;
}

export interface Sketch3DResponse {
  sketch_id: string;
  analysis: SketchAnalysisResult;
  layout_3d: {
    plans?: Array<Record<string, unknown>>;
    recommendation?: string;
    bim_compatible?: boolean;
  };
  suggestions: string[];
}

// ── IFC/BIM 导出（对齐 app/schemas/ifc_export.py）──
// 端点：POST /api/bim/export/structural/{projectId} + POST /api/bim/export/design/{planId}
// 返回 FileResponse（application/x-ifc 二进制下载）
export interface IFCExportRequest {
  include_furniture: boolean;
  lod_level: 'LOD200' | 'LOD300' | 'LOD350';
}
