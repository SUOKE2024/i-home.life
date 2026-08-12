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
  description?: string | null;
  address?: string | null;
  total_area?: number | null;
  status: ProjectStatus;
  project_type: ProjectType | string;
  house_type?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  contact_name?: string | null;
  contact_phone?: string | null;
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

// ── 预算（对齐 app/schemas/budget.py:BudgetResponse）──
// 端点：GET /api/budgets/project/{id}
export interface BudgetItem {
  id: string;
  budget_id: string;
  category: string;
  name: string;
  estimated_amount: number;
  actual_amount: number;
  unit: string;
  quantity: number;
  unit_price: number;
  note?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface Budget {
  id: string;
  project_id: string;
  total_estimated: number;
  total_actual: number;
  status: string;
  lines: BudgetItem[];
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

// ── BOM 清单（对齐 app/schemas/material.py:BOMItemResponse）──
// 端点：GET /api/materials/bom/{projectId}
export interface BomItem {
  id: string;
  project_id: string;
  material_id: string;
  room_id?: string | null;
  quantity: number;
  unit_price: number;
  total_price: number;
  note?: string | null;
  status: string;
  material?: Material | null;
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

// ── 能耗监测（对齐 app/schemas/energy_monitor.py）──
// 端点：GET /api/energy/records/project/{projectId}、/api/energy/report/{schemeId}
export interface EnergyMonitorItem {
  id: string;
  project_id: string;
  scheme_id: string;
  period: string; // daily / weekly / monthly
  total_consumption_kwh: number;
  device_breakdown: Record<string, number> | null;
  peak_power_w: number;
  avg_power_w: number;
  standby_consumption_kwh: number;
  estimated_cost: number;
  carbon_footprint_kg: number;
  recorded_at: string;
  created_at: string;
}

export interface EnergySavingTip {
  id: string;
  scheme_id: string;
  tip_type: string;
  device_type: string | null;
  device_name: string | null;
  current_consumption: number | null;
  potential_saving_pct: number | null;
  suggestion: string;
  priority: string; // high / medium / low
  status: string;
  created_at: string;
}

export interface EnergyReport {
  scheme_id: string;
  period: string;
  total_consumption_kwh: number;
  estimated_cost: number;
  carbon_footprint_kg: number;
  peak_power_w: number;
  avg_power_w: number;
  standby_consumption_kwh: number;
  standby_ratio: number;
  trend: Array<{ recorded_at: string; total_consumption_kwh: number; estimated_cost: number }>;
  device_ranking: Array<{ device_name: string; consumption_kwh: number; percentage: number }>;
  tips: EnergySavingTip[];
  generated_at: string;
}

// ── 支付管理（对齐 app/schemas/payment.py）──
// 端点：/api/payments/project/{projectId}、schedule、final-settlement、confirm/refund/fail/invoice
export interface PaymentItem {
  id: string;
  project_id: string;
  settlement_id: string | null;
  milestone_code: string;
  stage_code: string | null;
  stage_order: number;
  due_at: string | null;
  amount: number;
  payment_method: string;
  status: string; // pending / paid / failed / refunded / disputed
  transaction_id: string | null;
  payer: string | null;
  payee: string | null;
  evidence_url: string | null;
  note: string | null;
  invoice_no: string | null;
  invoice_url: string | null;
  invoiced_at: string | null;
  paid_at: string | null;
  refunded_at: string | null;
  refund_amount: number;
  refund_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentScheduleNode {
  stage_code: string;
  stage_order: number;
  milestone_code: string;
  total_amount: number;
  paid_amount: number;
  pending_amount: number;
  refunded_amount: number;
  failed_amount: number;
  payment_count: number;
  due_at: string | null;
  status: string; // pending / partial / paid / overdue
}

export interface FinalSettlementReport {
  project_id: string;
  total_contract_amount: number;
  total_paid: number;
  total_pending: number;
  total_refunded: number;
  total_failed: number;
  total_disputed: number;
  paid_ratio: number;
  invoice_count: number;
  invoiced_amount: number;
  milestone_summary: Array<Record<string, unknown>>;
  payment_count: number;
  generated_at: string;
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

/** GET /api/sketch-to-3d/supported-formats 返回结构（对齐 sketch_to_3d.py:supported_formats） */
export interface SketchSupportedFormats {
  image_formats: string[];
  max_file_size_mb: number;
  recommended_resolution: string;
  tips: string[];
}

// ── IFC/BIM 导出（对齐 app/schemas/ifc_export.py）──
// 端点：POST /api/bim/export/structural/{projectId} + POST /api/bim/export/design/{planId}
// 返回 FileResponse（application/x-ifc 二进制下载）
export interface IFCExportRequest {
  include_furniture: boolean;
  lod_level: 'LOD200' | 'LOD300' | 'LOD350';
}

// ── 设计方案生成（对齐 app/api/agents.py:DesignPlanResponse）──
// 端点：POST /api/agents/design
// 后端调用 DesignerAgent.generate_layouts（纯算法、确定性，无 LLM）
export interface DesignPlanResult {
  agent_type: string; // "designer"
  space_planning: string; // 空间规划（方案摘要 + 生成说明）
  style_suggestion: string; // 风格建议（推荐方案）
  circulation_analysis: string; // 动线分析（对推荐方案房间的真实动线分析摘要）
  material_plan: string; // 材料方案（materials 逐行）
  full_reply: string; // 完整 JSON（layouts 序列化）
}

// ── 讨论式方案交互（对齐 app/services/design_proposal_service.py）──
// 端点：POST /api/agents/design/proposals + POST /api/agents/design/proposals/{id}/revise
export interface DesignProposalSpec {
  proposal_id: string; // A/B/C
  title: string; // 紧凑型/标准型/豪华型
  layout_type: string; // L型/U型/岛型
  area_sqm: number;
  budget_cny: number;
  highlights: string[];
  rationale: string;
  change_log: string[];
  source: string; // llm | fallback
}

export interface DesignProposalResult {
  proposals: DesignProposalSpec[];
  session_id: string;
  source: string;
}

export interface DesignProposalReviseResult {
  proposal: DesignProposalSpec;
  proposal_id: string;
}

// ── 动线分析（对齐 app/agents/designer.py:analyze_circulation 返回）──
// 端点：POST /api/agents/design/circulation
// 纯算法：访客/家务/居住三条动线评分 + 冲突检测 + 优化建议
export interface CirculationRoom {
  name: string;
  type: string; // living_room | bedroom | kitchen | bathroom | dining_room | balcony | entryway | cloakroom ...
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CirculationSegment {
  from: string;
  to: string;
  distance: number;
}

export interface CirculationIssue {
  type: string; // too_long | cross_room | missing_room
  severity: string; // critical | warning | info
  detail: string;
}

export interface CirculationAnalysis {
  type: string; // visitor | housework | living
  name: string; // 访客动线 | 家务动线 | 居住动线
  description: string;
  path: Array<{ name: string; type: string }>;
  segments: CirculationSegment[];
  total_length: number;
  crossed_rooms: string[];
  missing_types: string[];
  score: number; // 0-100
  issues: CirculationIssue[];
  suggestions: string[];
}

export interface CirculationAnalysisResult {
  rooms_count: number;
  circulations: CirculationAnalysis[];
  overall_score: number;
  rating: string; // excellent | good | fair | poor
  rating_text: string; // 优秀 | 良好 | 一般 | 需优化
  total_issues: number;
  critical_count: number;
  warning_count: number;
  issues: CirculationIssue[];
  suggestions: string[];
  reply: string;
  error?: string; // rooms 为空时后端返回 { error }
}

// ──────────────────────────────────────────────────────────────────
//  B2B 装企交付（v1.4.x，对齐 app/api/b2b_delivery.py）
//  交付单状态机：draft → quoted → accepted → in_construction → completed / cancelled
//  命名 B2BDeliveryStatus 避免与采购物流 DeliveryStatus 冲突
// ──────────────────────────────────────────────────────────────────

export type B2BDeliveryStatus =
  | 'generating'
  | 'draft'
  | 'quoted'
  | 'accepted'
  | 'in_construction'
  | 'completed'
  | 'cancelled';

/** POST /api/b2b/delivery 响应（整包交付） */
export interface DeliveryPackage {
  delivery_id: string;
  delivery_order_id: string;
  status: B2BDeliveryStatus;
  name: string;
  summary: string;
  proposals: DeliveryProposalSpec[];
  budget_estimate: {
    source: string;
    project_id?: string;
    area: number;
    style: string;
    total_estimated?: number;
    line_count?: number;
    status?: string;
    breakdown_by_category?: Record<string, number>;
    tiers?: Record<string, { label: string; price_per_sqm: string; total_estimate: number }>;
    breakdown_ratio?: Record<string, number>;
    recommended_tier?: string;
  };
  construction_plan: {
    source: string;
    total_days: number;
    buffer_days: number;
    buffer_ratio: number;
    phases: { phase_code: string; name: string; days: number }[];
    note: string;
  };
  sources: Record<string, string>;
  generated_at: string;
}

export interface DeliveryProposalSpec {
  proposal_id: string;
  title: string;
  layout_type: string;
  area_sqm: number;
  budget_cny: number;
  highlights: string[];
  rationale: string;
  change_log: string[];
  source: string;
}

/** GET /api/b2b/delivery 列表项 */
export interface DeliveryListItem {
  delivery_order_id: string;
  name: string;
  area: number;
  style: string;
  status: B2BDeliveryStatus;
  summary: string | null;
  created_at: string;
}

/** GET /api/b2b/delivery/{id} 详情（整包快照） */
export interface DeliveryOrderDetail {
  delivery_order_id: string;
  project_id: string | null;
  name: string;
  area: number;
  style: string;
  budget: number;
  requirements: string;
  status: B2BDeliveryStatus;
  summary: string | null;
  proposals: DeliveryProposalSpec[] | null;
  budget_estimate: DeliveryPackage['budget_estimate'] | null;
  construction_plan: DeliveryPackage['construction_plan'] | null;
  sources: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

// ──────────────────────────────────────────────────────────────────
//  v1.5.0 F41-F47 新增功能（对齐 app/api/*.py 返回结构）
// ──────────────────────────────────────────────────────────────────

// ── F41 适老改造（对齐 app/api/elderly_adaptation.py:SchemeResponse）──
// occupant_type: elderly_living / semi_selfcare / nursing / family
// compliance_status: pass / warning / fail
export interface ElderlyAdaptationScheme {
  id: string;
  project_id: string;
  name: string;
  occupant_type: string;
  items?: unknown[] | null;
  accessibility_report?: Record<string, unknown> | null;
  compliance_status: string;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** POST /api/elderly-adaptation/schemes/{id}/validate 返回（GB 50763-2012 合规判定） */
export interface ElderlyAdaptationValidation {
  compliance_status: string; // pass | warning | fail
  score: number | null;
  summary: string;
}

// ── F42 局部焕新（对齐 app/api/partial_renovation.py:PlanResponse）──
// scope_type: kitchen_refresh / bathroom_refresh / wall_refresh / single_room / full_renovation
// budget_level: economic / comfort / quality
export interface PartialRenovationPlan {
  id: string;
  project_id: string;
  name: string;
  scope_type: string;
  budget_level: string;
  duration_days: number;
  budget_lower: number;
  budget_upper: number;
  tasks?: unknown[] | null;
  interference_plan?: Record<string, string> | null;
  status: string;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** GET /api/partial-renovation/templates 返回（对齐 partial_renovation_service.list_templates） */
export interface PartialRenovationTemplate {
  scope_type: string;
  name: string;
  duration_days: number;
  budget_range: Record<string, [number, number]>;
  task_count: number;
}

// ── F43 资金托管（对齐 app/api/escrow_trustee.py:_account_dict）──
// trustee_type: bank / third_party
// status: active / release_requested / released
export interface EscrowTrusteeAccount {
  id: string;
  escrow_payment_id: string;
  trustee_type: string;
  account_no_masked: string;
  interest_to_owner: boolean;
  owner_confirmed: boolean;
  contractor_confirmed: boolean;
  status: string;
  release_rule: string;
  released_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** GET /api/escrow/trustee-accounts/{id}/interest 返回（托管资金利息归属说明） */
export interface EscrowInterestInfo {
  interest_to_owner: boolean;
  note: string;
}

// ── F44 环保材料标签（对齐 app/services/eco_material_service.py）──
/** 材料环保认证标签 + 材料信息（_cert_item，用于 /materials 列表） */
export interface MaterialEcoCertItem {
  material_id: string;
  material_name: string;
  sku: string;
  brand: string | null;
  unit_price: number;
  eco_grade: string; // ENF / E0 / E1
  certification: string;
}

/** GET /api/eco-materials/grades 返回：各环保等级数量统计（含 0） */
export type EcoGradeCounts = Record<string, number>;

/** POST /api/eco-materials/validate 返回（对标 HC-003 环保等级硬约束） */
export interface EcoComplianceReport {
  total: number;
  compliant_count: number;
  non_compliant_count: number;
  items: Array<{
    material_id: string;
    material_name: string;
    eco_grade: string;
    certification: string;
    compliant: boolean;
    requirement: string;
    note: string;
  }>;
}

// ── F45 方案前置决策（对齐 app/services/solution_first_service.generate_package）──
export interface SolutionFirstLayout {
  plan_no: string; // A / B / C
  name: string;
  summary: string;
  layout_points: string[];
  pros: string[];
  cons: string[];
  source: string; // rule_based
  source_note: string;
}

export interface SolutionFirstPackage {
  project_id: string;
  project_name: string;
  plan_count: number;
  layouts: SolutionFirstLayout[];
  budget_range: {
    level: string;
    lower: number;
    upper: number;
    per_sqm_lower: number;
    per_sqm_upper: number;
    levels: Array<{ level: string; per_sqm_lower: number; per_sqm_upper: number; lower: number; upper: number }>;
    note: string;
  };
  recommendations: string[];
  source: string;
  source_note: string;
  generated_at: string;
}

// ── F46 生态桥接优先级（对齐 app/services/ecosystem_bridge_status.py）──
/** GET /api/ecosystem/status 返回（含诚实降级标注） */
export interface EcosystemBridgeStatus {
  bridges: Array<{
    key: string;
    name: string;
    priority: number;
    configured: boolean;
    status: string; // ready | requires_api_key
    required_env_keys: string[];
    note: string;
  }>;
  updated_at: string;
  honest_note: string;
}

/** GET /api/ecosystem/bridges 返回（优先级列表 + 策略说明） */
export interface EcosystemBridges {
  bridges: Array<{
    key: string;
    name: string;
    priority: number;
    required_env_keys: string[];
    bridge: string;
  }>;
  priority_strategy: string;
}

// ── F47 AI 装修问答（对齐 app/services/ai_qa_search_service.py）──
/** POST /api/ai-qa/search 返回（含引用来源，未命中诚实降级） */
export interface AIQASource {
  domain: string;
  title: string;
  citation: string;
  snippet: string;
}

export interface AIQAResult {
  query: string;
  answer: string;
  sources: AIQASource[];
  match_type: string; // knowledge_base | no_match
  honest_note: string;
}

/** GET /api/ai-qa/faq 返回（知识库 faq 域前 20 条） */
export interface AIQAFaq {
  total: number;
  topics: Array<{
    id: string;
    name: string;
    content: string;
    citation: string;
  }>;
}

// ── F11 多方案预算对比（对齐 app/agents/budget.py:compare_budget_plans）──
/** 单个档位方案（经济/舒适/品质） */
export interface BudgetComparePlan {
  tier: string; // economy | comfort | premium | luxury
  tier_name: string; // 中文档位名
  total_range: [number, number];
  total_estimated: number;
  breakdown: Record<string, number>; // 分项 {分类: 金额}
}

/** POST /api/budgets/compare-plans 返回 */
export interface BudgetCompareResult {
  area: number;
  plans: BudgetComparePlan[];
  differences: {
    economy_to_comfort: number;
    comfort_to_premium: number;
  };
  recommendation: string;
  reply: string;
}

// ── F13 预算模板库（对齐 app/agents/budget.py:list_templates / apply_template）──
export interface BudgetTemplate {
  code: string;
  name: string;
  area: number;
  tier: string;
  style: string;
  total_range: [number, number];
  line_count: number;
}

/** GET /api/budgets/templates 返回 */
export interface BudgetTemplateList {
  templates: BudgetTemplate[];
  total: number;
  reply: string;
}

export interface BudgetTemplateLine {
  category: string;
  name: string;
  unit_price: number;
  quantity: number;
  unit: string;
  estimated_amount: number;
}

/** POST /api/budgets/templates/apply 返回 */
export interface BudgetTemplateApplyResult {
  template_code: string;
  template_name: string;
  applied_area: number;
  scale: number;
  total_estimated: number;
  lines: BudgetTemplateLine[];
  reply: string;
}

// ── F18 厨卫水电（对齐 app/schemas/kitchen_bath_mep.py）──
export interface KitchenBathMEPPlan {
  id: string;
  project_id: string;
  room_name: string;
  room_type: string; // kitchen | bathroom | laundry | balcony
  water_inlets: Record<string, unknown>[] | null;
  drains: Record<string, unknown>[] | null;
  gas_pipe_layout: Record<string, unknown>[] | null;
  electrical_circuits: Record<string, unknown>[] | null;
  equipotential_bonding: boolean;
  water_heater_type: string | null;
  water_heater_capacity_l: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MEPPoint {
  id: string;
  plan_id: string;
  point_type: string; // water_inlet | drain | ...
  device: string | null;
  position_x: number;
  position_y: number;
  position_z: number;
  spec: string | null;
  voltage: string | null;
  power_w: number | null;
  notes: string | null;
  created_at: string;
}

/** GET /api/mep-kb/plans/{planId}/circuits 返回 */
export interface MEPCircuitResult {
  plan_id: string;
  circuits: Array<{
    circuit_no: string;
    type: string;
    device: string;
    power_w: number;
    wire: string;
    breaker: string;
    voltage: string;
  }>;
  total_circuits: number;
  total_power_w: number;
  main_breaker_recommended: string;
}

/** GET /api/mep-kb/plans/{planId}/equipotential 返回 */
export interface MEPEquipotentialResult {
  plan_id: string;
  compliant: boolean;
  room_type: string;
  equipotential_bonding: boolean;
  checks: Array<{
    item: string;
    value: string;
    passed: boolean;
    standard: string;
  }>;
}

/** GET /api/mep-kb/plans/{planId}/gas 返回 */
export interface MEPGasResult {
  plan_id: string;
  needed: boolean;
  reason?: string;
  outlets: Array<{
    device: string;
    position: { x: number; y: number; z: number };
    pipe_spec: string;
    valve: string;
    note: string;
  }>;
}

// ── F35 服务商匹配（对齐 app/schemas/service_worker.py）──
export interface ServiceWorker {
  id: string;
  name: string;
  phone: string | null;
  avatar_url: string | null;
  city: string | null;
  district: string | null;
  role: string;
  role_attributes: Record<string, unknown>;
  qualification: string;
  rating: number;
  completed_projects: number;
  years_of_experience: number;
  hourly_rate: number;
  daily_rate: number;
  status: string;
  introduction: string | null;
  certifications: string[];
  portfolio_urls: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkerMatch {
  id: string;
  project_id: string;
  worker_id: string;
  role: string;
  match_score: number;
  score_breakdown: Record<string, number>; // 六维评分明细
  recommendation: string | null;
  status: string; // pending | shortlisted | hired | rejected
  worker: ServiceWorker | null;
  created_at: string;
  updated_at: string;
}

// ── F40 三方协作 IM（对齐 app/schemas/chat.py + chat.py 扩展字段）──
export interface ChatRoom {
  id: string;
  project_id: string;
  name: string;
  member_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  project_id: string;
  sender_id: string;
  sender_name: string;
  sender_role: string;
  content: string;
  message_type: string;
  mentions: string[];
  reply_to_id: string | null;
  thread_root_id: string | null;
  read_by: string[];
  is_deleted: boolean;
  created_at: string;
  // F40 Agent 自动回复标注（缺失字段为 null）
  generated_by?: string | null;
  agent_mode?: string | null;
  engine?: string | null;
  is_placeholder?: boolean | null;
}

/** GET /api/chat/rooms/{roomId}/agents 返回 */
export interface ChatRoomAgents {
  room_id: string;
  project_id: string;
  agent_members: string[];
}

// ──────────────────────────────────────────────────────────────────
//  Agent 治理 — GB/Z 185 身份卡 / 工具批准 / Skill / 记忆 / A2A / MCP / Harness / Eval
//  对齐 app/api/agent_identity.py、agent_approvals.py、agent_skills.py、
//  agent_memory.py、a2a.py、mcp.py、harness_api.py、eval.py
// ──────────────────────────────────────────────────────────────────

// ── GB/Z 185 身份卡（app/api/agent_identity.py + app/services/agent_identity_card.py）──
// flag: gbz185_agent_card_enabled（默认 False，关闭时端点 404 诚实降级）
/** GET /api/agents/identity 列表项 */
export interface AgentIdentityListItem {
  name: string;
  type_code: string; // 2 位智能体类型码
  security_level: string; // 1-4
}

/** GET /api/agents/identity 返回 */
export interface AgentIdentityListResponse {
  agents: AgentIdentityListItem[];
  total: number;
}

/** GET /api/agents/identity/{name} 身份卡（28 位 AID + ACDL GB/Z 185.4） */
export interface AgentIdentityCard {
  agent_name: string;
  aid: string; // 28 位身份码
  acdl: {
    schema: string;
    acdl_version: string;
    agent: {
      agent_id: string;
      name: string;
      security_level: string; // L1-L4
      capabilities: string[];
      interface: Record<string, unknown>;
    };
  };
}

// ── Agent 工具批准（app/api/agent_approvals.py）──
// state: pending | approved | rejected | expired
/** 单条批准请求（ApprovalItemResponse） */
export interface AgentApprovalItem {
  id: string;
  approval_id: string;
  user_id: string;
  agent_name: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  project_id: string | null;
  scope: string;
  trace_id: string | null;
  state: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** GET /api/agents/approvals 返回（仅 pending 请求） */
export interface AgentApprovalListResponse {
  count: number;
  items: AgentApprovalItem[];
}

/** POST /api/agents/approvals/{approvalId}/execute 返回 */
export interface AgentApprovalExecuteResponse {
  executed: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
}

// ── Agent Skill 资产（app/api/agent_skills.py）──
// flag: agent_skill_enabled（创建/导入时校验，关闭返回 503）
// status: draft | active | archived
/** Skill 资产（SkillItemResponse） */
export interface AgentSkillItem {
  id: string;
  name: string;
  description: string;
  owner_scope: string; // personal | project | team | org
  owner_id: string;
  agent_name: string;
  system_prompt: string;
  provider: string;
  tools: unknown[];
  cost_tier: string;
  acceptance_criteria: unknown[];
  version: number;
  status: string;
  parent_version_id: string | null;
  share_scope: string;
  share_grants: unknown[];
  created_by: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  skill_pack_source: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** GET /api/agents/skills 返回 */
export interface AgentSkillListResponse {
  count: number;
  items: AgentSkillItem[];
}

/** POST /api/agents/skills/{skillId}/instantiate 返回 */
export interface AgentSkillInstantiateResponse {
  skill_id: string;
  agent_name: string;
  reply: string;
  status: string; // ok | degraded
}

// ── Agent 长期记忆（app/api/agent_memory.py）──
// category: preference | location | fact；scope: personal | project | team | org
/** 单条记忆（MemoryItemResponse） */
export interface AgentMemoryItem {
  id: string;
  category: string;
  key: string;
  value: string;
  source: string | null;
  importance: number; // 1-5
  scope: string;
  project_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** GET /api/agents/memory 返回 */
export interface AgentMemoryListResponse {
  count: number;
  items: AgentMemoryItem[];
}

// ── A2A 协议（app/api/a2a.py）──
// flag: a2a_enabled（任务下发/查询时校验，关闭返回 503）
/** GET /api/a2a/agents 列表项 */
export interface A2AAgentInfo {
  name: string;
  class_name: string;
  description: string;
}

/** GET /api/a2a/agents 返回 */
export interface A2AAgentListResponse {
  agents: A2AAgentInfo[];
  count: number;
}

/** POST /api/a2a/tasks/send 响应 / GET /api/a2a/tasks/{id}（A2ATaskResponse） */
export interface A2ATaskResponse {
  task_id: string;
  state: string; // submitted | working | completed | failed
  result: unknown;
  error: string | null;
}

/** GET /api/a2a/tasks/{id}/status 返回 */
export interface A2ATaskStatusResponse {
  task_id: string;
  state: string;
}

// ── MCP Server（app/api/mcp.py + app/mcp/server.py）──
// flag: mcp_enabled（jsonrpc/cimd/mrtr 校验）；mrtr 另受 mcp_mrtr_enabled 控制
/** GET /api/mcp/manifest 返回（服务器元信息） */
export interface MCPManifest {
  name: string;
  version: string;
  protocol_version: string;
  tools_count: number;
  capabilities: Record<string, unknown>;
  deprecated?: string;
}

/** GET /api/mcp/tools 列表项（MCP 协议格式） */
export interface MCPTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, unknown>;
    required: string[];
  };
  annotations: { category: string };
}

/** GET /api/mcp/tools 返回 */
export interface MCPToolsResponse {
  tools: MCPTool[];
}

/** POST /api/mcp/tools/call 返回（MCP 协议格式结果） */
export interface MCPToolCallResult {
  content: Array<{ type: string; text: string }>;
  isError: boolean;
  tool: string;
}

/** GET /api/mcp/mrtr 返回（MRTR 待响应请求列表） */
export interface MCPMrtrListResponse {
  requests: Array<{
    id: string;
    method: string;
    params: Record<string, unknown> | null;
    state: string;
    created_at: string;
    expires_at: string;
  }>;
}

// ── Harness（app/api/harness_api.py + app/agents/harness.py）──
/** GET /api/harness/metrics 返回（HarnessMetricsResponse） */
export interface HarnessMetrics {
  total_runs: number;
  success_runs: number;
  fallback_runs: number;
  failed_runs: number;
  success_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  trace_count: number;
  registered_agents: string[];
}

/** 单条执行轨迹（AgentTrace.to_dict，traces 端点返回） */
export interface HarnessTrace {
  trace_id: string;
  agent_name: string;
  agent_version: string;
  provider: string;
  model: string;
  started_at: string | null;
  finished_at: string | null;
  status: string; // success | failed | fallback
  user_message_truncated: string;
  response_truncated: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  tool_call_count: number;
  tool_call_rounds: number;
  fallback_used: boolean;
  fallback_reason: string;
  retry_count: number;
  latency_ms: number;
  first_token_latency_ms: number;
  error_message: string;
  error_type: string;
  user_id: string;
  project_id: string;
  scope: string;
  context_source: string;
}

/** GET /api/harness/traces 返回 */
export interface HarnessTracesResponse {
  traces: HarnessTrace[];
  total: number;
}

/** GET /api/harness/eval 返回（HarnessEvalResponse） */
export interface HarnessEvalResponse {
  status: string; // ok | no_data
  sample_size: number;
  metrics: Record<string, number>;
}

/** GET /api/harness/health 返回 */
export interface HarnessHealthResponse {
  status: string;
  registered_agents: string[];
  trace_count: number;
  total_runs: number;
}

// ── 评估框架（app/api/eval.py + app/eval/ihome_eval.py）──
// flag: eval_enabled（关闭时 report/run 返回 run_id="disabled" 报告，非 4xx/5xx）
/** GET /api/eval/dimensions 列表项 */
export interface EvalDimensionItem {
  id: string;
  name: string;
  benchmark: string;
}

/** GET /api/eval/dimensions 返回 */
export interface EvalDimensionsResponse {
  dimensions: EvalDimensionItem[];
  total: number;
}

/** GET /api/eval/report + POST /api/eval/run 返回（EvalReportResponse） */
export interface EvalReport {
  run_id: string; // disabled 表示 eval_enabled=False
  baseline: string; // base_llm | keyword | full_system | mock
  sample_size: number;
  started_at: number;
  finished_at: number;
  metrics: Record<string, number>;
  dimension_scores: Record<string, number>;
  // v1.12.x: per-agent 评分 + 量化目标基线
  per_agent_scores: Record<string, EvalPerAgentScore>;
  quality_targets: Record<string, number>;
  notes: string[];
}

/** v1.12.x per-agent 评分（对齐 2026 逐 Agent 评估） */
export interface EvalPerAgentScore {
  sample_size: number;
  success_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  meets_targets: boolean;
}

/** GET /api/eval/drift 返回（v1.12.x 漂移检测） */
export interface EvalDriftRecord {
  agent_name: string;
  sample_size: number;
  status: string; // ok | warn | critical | insufficient_samples
  metric: string;
  current: number;
  target: number;
}

export interface EvalDriftResponse {
  window_days: number;
  quality_targets: Record<string, number>;
  records: EvalDriftRecord[];
  summary: { total: number; critical: number; warn: number; ok: number; insufficient_samples: number };
}

/** GET /api/admin/agent-governance-audit 返回（v1.12.x OWASP Agentic Skills Top 10 对照） */
export interface GovernanceFinding {
  id: string; // AG1-AG10
  name: string;
  desc: string;
  control: string;
  status: string; // pass | warn | fail
  evidence: string;
  recommendation: string;
}

export interface GovernanceAuditResponse {
  generated_at: string;
  framework: string;
  summary: { total: number; pass: number; warn: number; fail: number; score: string };
  findings: GovernanceFinding[];
  recommendations: string[];
}

// ──────────────────────────────────────────────────────────────────
//  积分商城（对齐 app/schemas/points.py，前缀 /api/points）
// ──────────────────────────────────────────────────────────────────

/** GET /api/points/account 积分账户（PointsAccountResponse） */
export interface PointsAccount {
  id: string;
  user_id: string;
  account_type: string;
  balance: number;
  total_earned: number;
  total_spent: number;
  level: string;
  year_earned: number;
  year_spent: number;
  created_at: string;
  updated_at: string;
}

/** GET /api/points/transactions 积分流水（PointsTransactionResponse） */
export interface PointsTransaction {
  id: string;
  user_id: string;
  amount: number;
  transaction_type: string;
  source: string;
  description: string;
  balance_after: number;
  created_at: string;
}

/** GET /api/points/rules 积分规则（PointsRuleResponse） */
export interface PointsRule {
  id: string;
  action: string;
  role: string;
  points: number;
  limit_daily: number | null;
  limit_weekly: number | null;
  description: string;
  is_active: boolean;
}

/** GET /api/points/mall 商城商品（PointsMallItemResponse） */
export interface PointsMallItem {
  id: string;
  name: string;
  category: string;
  description: string | null;
  image_url: string | null;
  points_required: number;
  stock: number;
  discount_type: string | null;
  discount_value: number | null;
  discount_max: number | null;
  validity_days: number;
  is_active: boolean;
  sort_order: number;
}

/** GET /api/points/redemptions + POST /api/points/redeem 兑换记录（RedemptionResponse） */
export interface PointsRedemption {
  id: string;
  user_id: string;
  item_id: string;
  item_name: string;
  points_spent: number;
  discount_code: string | null;
  discount_type: string | null;
  discount_value: number | null;
  discount_max: number | null;
  expires_at: string | null;
  status: string;
  created_at: string;
}

/** GET /api/points/ranking 排行榜条目（RankingResponse） */
export interface PointsRankingEntry {
  user_id: string;
  user_name: string | null;
  role: string;
  year_earned: number;
  rank: number;
  level: string | null;
}

/** POST /api/points/earn 请求（PointsEarnRequest，仅管理员） */
export interface PointsEarnInput {
  user_id: string;
  source: string;
  amount?: number | null;
  reference_id?: string | null;
  description?: string | null;
}

// ──────────────────────────────────────────────────────────────────
//  AI 图生图（对齐 app/schemas/ai_image.py，前缀 /api/ai-image）
// ──────────────────────────────────────────────────────────────────

/** POST /api/ai-image/jobs 请求（AIImageJobCreate） */
export interface AIImageJobCreateInput {
  project_id: string;
  floorplan_id?: string | null;
  job_type?: string;
  input_image_url?: string | null;
  prompt?: string | null;
  negative_prompt?: string | null;
  model_name?: string;
  controlnet_type?: string | null;
  controlnet_strength?: number;
  guidance_scale?: number;
  num_inference_steps?: number;
  seed?: number | null;
}

/** GET /api/ai-image/jobs/{id} 任务详情（AIImageJobResponse） */
export interface AIImageJob {
  id: string;
  project_id: string;
  floorplan_id: string | null;
  job_type: string;
  input_image_url: string | null;
  output_image_url: string | null;
  prompt: string | null;
  negative_prompt: string | null;
  model_name: string;
  controlnet_type: string | null;
  controlnet_strength: number;
  guidance_scale: number;
  num_inference_steps: number;
  seed: number | null;
  status: string;
  progress_percent: number;
  error_message: string | null;
  render_duration_sec: number;
  render_backend: string; // mock（诚实降级占位）/ real
  created_at: string;
  completed_at: string | null;
}

/** GET /api/ai-image/jobs/project/{projectId} 列表项（AIImageJobListItem） */
export interface AIImageJobListItem {
  id: string;
  project_id: string;
  job_type: string;
  input_image_url: string | null;
  output_image_url: string | null;
  model_name: string;
  status: string;
  progress_percent: number;
  created_at: string;
}

/** GET /api/ai-image/jobs/{id}/status 任务状态（dict） */
export interface AIImageJobStatus {
  id: string;
  status: string;
  progress_percent: number;
  output_image_url: string | null;
  error_message: string | null;
  render_backend: string;
  cost_yuan: number;
}

/** GET /api/ai-image/presets 预设模板（AIImagePresetResponse） */
export interface AIImagePreset {
  id: string;
  name: string;
  category: string;
  prompt_template: string;
  negative_prompt_template: string | null;
  default_params: string | null;
  preview_image_url: string | null;
  usage_count: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

/** POST /api/ai-image/presets 请求（AIImagePresetCreate） */
export interface AIImagePresetCreateInput {
  name: string;
  category?: string;
  prompt_template: string;
  negative_prompt_template?: string | null;
  default_params?: Record<string, unknown>;
  preview_image_url?: string | null;
  is_public?: boolean;
}

/** POST /api/ai-image/jobs/apply-preset 请求（ApplyPresetRequest） */
export interface AIImageApplyPresetInput {
  preset_id: string;
  project_id: string;
  floorplan_id?: string | null;
  input_image_url: string;
  customizations?: Record<string, unknown>;
}

/** POST /api/ai-image/jobs/batch 请求（BatchRenderRequest） */
export interface AIImageBatchRenderInput {
  project_id: string;
  floorplan_id?: string | null;
  preset_ids: string[];
  input_image_url?: string | null;
}

// ──────────────────────────────────────────────────────────────────
//  身份认证（对齐 app/schemas/identity.py，前缀 /api/identity）
// ──────────────────────────────────────────────────────────────────

/** POST /api/identity/submit 请求（IdentitySubmitRequest） */
export interface IdentitySubmitInput {
  real_name: string;
  id_card: string;
  id_card_front?: string | null;
  id_card_back?: string | null;
  selfie_with_id?: string | null;
  role_attributes?: Record<string, unknown> | null;
}

/** POST /api/identity/submit 响应 + GET /api/identity/pending 列表项（IdentityVerificationResponse） */
export interface IdentityVerification {
  id: string;
  user_id: string;
  role: string;
  real_name: string;
  id_card: string;
  third_party_verified: boolean;
  third_party_provider: string | null;
  status: string;
  role_attributes: Record<string, unknown> | null;
  review_note: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /api/identity/status 认证状态（IdentityStatusResponse） */
export interface IdentityStatus {
  is_verified: boolean;
  status: string; // pending / approved / rejected / not_submitted
  role: string | null;
  submitted_at: string | null;
  review_note: string | null;
  verified_at: string | null;
}

// ──────────────────────────────────────────────────────────────────
//  量房（对齐 app/schemas/survey.py，前缀 /api/surveys）
// ──────────────────────────────────────────────────────────────────

/** 单个房间测量数据（RoomMeasureItem） */
export interface RoomMeasureItem {
  name: string;
  room_type: string;
  width: number;
  length: number;
  height: number | null;
  area: number | null;
  notes: string | null;
}

/** POST /api/surveys 请求（SurveyCreate） */
export interface SurveyCreateInput {
  project_id: string;
  name?: string;
  surveyor?: string | null;
  method?: string;
  scene_type?: string;
  wall_height?: number;
  rooms: RoomMeasureItem[];
  scan_data?: string | null;
  voice_transcript?: string | null;
  device_info?: string | null;
  notes?: string | null;
}

/** PUT /api/surveys/{id} 请求（SurveyUpdate） */
export interface SurveyUpdateInput {
  name?: string | null;
  surveyor?: string | null;
  method?: string | null;
  scene_type?: string | null;
  wall_height?: number | null;
  rooms?: RoomMeasureItem[] | null;
  scan_data?: string | null;
  voice_transcript?: string | null;
  device_info?: string | null;
  status?: string | null;
  notes?: string | null;
}

/** GET /api/surveys/project/{projectId} 列表项（SurveyListItem） */
export interface SurveyItem {
  id: string;
  project_id: string;
  name: string;
  surveyor: string | null;
  method: string;
  scene_type: string;
  total_area: number;
  wall_height: number;
  status: string;
  created_at: string;
  updated_at: string;
}

/** GET /api/surveys/{id} 详情（SurveyResponse） */
export interface SurveyDetail extends SurveyItem {
  rooms: RoomMeasureItem[];
  scan_data: string | null;
  voice_transcript: string | null;
  device_info: string | null;
  notes: string | null;
}

/** GET /api/surveys/device-check 设备能力检测（dict） */
export interface SurveyDeviceCheck {
  available_sensors: Record<string, Record<string, unknown>>;
  recommended_workflow: Record<string, string[]>;
}

// ──────────────────────────────────────────────────────────────────
//  AR 空间测量（对齐 app/schemas/ar_scan.py，前缀 /api/surveys/ar）
// ──────────────────────────────────────────────────────────────────

/** POST /api/surveys/ar/sessions 请求（ScanSessionCreate） */
export interface ARScanSessionCreateInput {
  project_id: string;
  survey_id?: string | null;
  floorplan_id?: string | null;
  name?: string;
  scanner?: string | null;
  device_model?: string | null;
  platform?: string;
  requested_method?: string;
  device_capability?: Record<string, unknown> | null;
  floor_count?: number;
  wall_height?: number;
  notes?: string | null;
}

/** GET /api/surveys/ar/sessions/{id} 会话详情（ScanSessionResponse） */
export interface ARScanSession {
  id: string;
  project_id: string;
  survey_id: string | null;
  floorplan_id: string | null;
  name: string;
  scanner: string | null;
  device_model: string | null;
  platform: string;
  scan_method: string;
  requested_method: string | null;
  device_capability: string | null;
  floor_count: number;
  room_count: number;
  total_area: number;
  wall_height: number;
  scan_duration_sec: number;
  scan_points_count: number;
  model_url: string | null;
  model_format: string | null;
  raw_data_url: string | null;
  panorama_urls: string | null;
  accuracy_rms_error: number | null;
  accuracy_level: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /api/surveys/ar/sessions/project/{projectId} 列表项（ScanSessionListItem） */
export interface ARScanSessionListItem {
  id: string;
  project_id: string;
  name: string;
  scanner: string | null;
  platform: string;
  scan_method: string;
  total_area: number;
  room_count: number;
  accuracy_level: string | null;
  status: string;
  created_at: string;
}

/** PATCH /api/surveys/ar/sessions/{id} 请求（ScanSessionUpdate） */
export interface ARScanSessionUpdateInput {
  name?: string | null;
  scanner?: string | null;
  scan_method?: string | null;
  floor_count?: number | null;
  room_count?: number | null;
  floorplan_id?: string | null;
  total_area?: number | null;
  wall_height?: number | null;
  scan_duration_sec?: number | null;
  scan_points_count?: number | null;
  model_url?: string | null;
  model_format?: string | null;
  raw_data_url?: string | null;
  panoramas?: string[] | null;
  status?: string | null;
  notes?: string | null;
}

/** POST /api/surveys/ar/device-capability 请求（DeviceCapabilityRequest） */
export interface ARDeviceCapabilityInput {
  platform?: string;
  device_model?: string | null;
  os_version?: string | null;
  has_lidar?: boolean;
  has_depth_sensor?: boolean;
  has_gyroscope?: boolean;
  has_accelerometer?: boolean;
  has_magnetometer?: boolean;
  arkit_version?: string | null;
  arcore_version?: string | null;
  ar_engine_version?: string | null;
  camera_resolution?: string | null;
  supports_roomplan?: boolean;
  supports_photogrammetry?: boolean;
}

/** POST /api/surveys/ar/device-capability 响应（ARDeviceCapabilityResponse） */
export interface ARDeviceCapabilityResult {
  platform: string;
  recommended_method: string;
  available_methods: string[];
  lidar_supported: boolean;
  fallback_chain: string[];
  estimated_accuracy_cm: number;
  estimated_scan_time_per_room_min: number;
}

/** POST /api/surveys/ar/sessions/{id}/process 请求（ProcessScanRequest） */
export interface ARProcessScanInput {
  model_url?: string | null;
  model_format?: string;
  raw_data_url?: string | null;
  panoramas?: string[] | null;
  scan_points_count?: number;
  scan_duration_sec?: number;
}

/** POST /api/surveys/ar/features 请求（WallFeatureCreate） */
export interface WallFeatureCreateInput {
  session_id: string;
  room_name: string;
  wall_id?: string | null;
  feature_type: string;
  position_x?: number;
  position_y?: number;
  width?: number;
  height?: number;
  depth?: number;
  sill_height?: number | null;
  load_bearing?: boolean;
  material?: string | null;
  direction?: string | null;
  extra?: Record<string, unknown> | null;
  confidence?: number;
  detected_by?: string;
}

/** GET /api/surveys/ar/features/{sessionId} 墙面特征（WallFeatureResponse） */
export interface WallFeature {
  id: string;
  session_id: string;
  room_name: string;
  wall_id: string | null;
  feature_type: string;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  depth: number;
  sill_height: number | null;
  load_bearing: boolean;
  material: string | null;
  direction: string | null;
  extra: string | null;
  confidence: number;
  detected_by: string;
  created_at: string;
}

/** POST /api/surveys/ar/points 请求（MeasurementPointCreate） */
export interface MeasurementPointCreateInput {
  session_id: string;
  label: string;
  room_name?: string | null;
  point_type?: string;
  ar_value: number;
  reference_value: number;
  unit?: string;
  notes?: string | null;
}

/** GET /api/surveys/ar/points/{sessionId} 测量校准点（MeasurementPointResponse） */
export interface MeasurementPoint {
  id: string;
  session_id: string;
  label: string;
  room_name: string | null;
  point_type: string;
  ar_value: number;
  reference_value: number;
  unit: string;
  deviation: number;
  deviation_percent: number;
  measured_at: string;
  notes: string | null;
}

/** GET /api/surveys/ar/sessions/{id}/accuracy 精度报告（AccuracyReportResponse） */
export interface ARAccuracyReport {
  session_id: string;
  rms_error_cm: number;
  accuracy_level: string; // high / medium / low
  max_deviation_cm: number;
  avg_deviation_cm: number;
  passed_count: number;
  total_count: number;
  pass_rate: number;
  degradation_path: string[];
  recommendations: string[];
  points: MeasurementPoint[];
}

// ── 管理后台（对齐 app/api/admin.py）──

/** GET /api/admin/stats 平台统计（PlatformStatsResponse） */
export interface PlatformStats {
  total_projects: number;
  total_users: number;
  active_projects: number;
  pending_verifications: number;
  total_materials: number;
  total_suppliers: number;
  weekly_new_users: number;
}

/** GET /api/admin/audit-logs 审计日志条目 */
export interface AuditLogItem {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: string | null;
  request_ip: string | null;
  user_agent: string | null;
  created_at: string | null;
}

/** GET /api/admin/audit-logs 分页响应 */
export interface AuditLogPage {
  items: AuditLogItem[];
  total: number;
  skip: number;
  limit: number;
}

// ── 通知（对齐 app/api/notifications.py + app/schemas/notification.py）──

/** GET /api/notifications/devices 设备推送令牌（DeviceTokenResponse） */
export interface DeviceToken {
  id: string;
  user_id: string;
  device_token: string;
  platform: string; // ios / android / harmonyos
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── 文件（对齐 app/api/files.py + app/schemas/file_attachment.py）──

/** GET /api/files/project/{project_id} 项目附件（FileAttachmentListItem） */
export interface ProjectFileItem {
  id: string;
  project_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  category: string;
  created_at: string;
}
