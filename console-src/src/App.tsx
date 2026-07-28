import { Routes, Route } from 'react-router-dom';
import WorkbenchPage from './pages/WorkbenchPage';
import PlaceholderHome from './pages/PlaceholderHome';
import PlaceholderPage from './pages/PlaceholderPage';
import ProjectsPage from './pages/ProjectsPage';
import SettingsPage from './pages/SettingsPage';
import BudgetPage from './pages/BudgetPage';
import ConstructionPage from './pages/ConstructionPage';
import ProcurementPage from './pages/ProcurementPage';
import SettlementPage from './pages/SettlementPage';
import TasksPage from './pages/TasksPage';
import MaterialsPage from './pages/MaterialsPage';
import ChangeOrdersPage from './pages/ChangeOrdersPage';
import CrewsPage from './pages/CrewsPage';
import SmartHomePage from './pages/SmartHomePage';
import ScenePage from './pages/ScenePage';
import FloorplansPage from './pages/FloorplansPage';
import LightingPage from './pages/LightingPage';
import SoftFurnishingPage from './pages/SoftFurnishingPage';
import KitchenPage from './pages/KitchenPage';
import BathroomPage from './pages/BathroomPage';
import DoorWindowPage from './pages/DoorWindowPage';
import TakeoffPage from './pages/TakeoffPage';
import StructuralPage from './pages/StructuralPage';
import AppliancePage from './pages/AppliancePage';
import ProductsPage from './pages/ProductsPage';
import FurniturePage from './pages/FurniturePage';
import HardDecorationPage from './pages/HardDecorationPage';
import MepPage from './pages/MepPage';
import VRPanoramaPage from './pages/VRPanoramaPage';
import CustomFurniturePage from './pages/CustomFurniturePage';
import QualityPage from './pages/QualityPage';
import AIRenderPage from './pages/AIRenderPage';
import CADPage from './pages/CADPage';
import Sketch3DPage from './pages/Sketch3DPage';
import IFCExportPage from './pages/IFCExportPage';
import { SuokeLayout } from './components/layout';

/**
 * App 路由根
 *
 * 批次 4：/ /projects /settings /budget → 真实页面；其余 27 页占位
 * 批次 5：4 个高频真实页（Construction/Procurement/Settlement/Tasks）替换占位
 * 批次 6：5 个真实页（Materials/ChangeOrders/Crews/SmartHome/Scene）替换占位
 * 批次 7：6 个真实页（Floorplans/Lighting/SoftFurnishing/Kitchen/Bathroom/DoorWindow）替换占位
 */

/** 占位路由配置（批次 5 替换为真实页面） */
const PLACEHOLDER_ROUTES: Array<{
  path: string;
  title: string;
  emoji?: string;
  agent?: string;
}> = [
  // 设计（floorplans/lighting/soft-furnishing/hard-decoration/vr-panorama/ai-render/cad/sketch-3d/ifc-export 已实现，见下方真实路由）
  { path: '/design', title: '设计', agent: 'design' },
  // 施工（construction/tasks/change-orders/crews/takeoff/structural/mep/quality 已实现，见下方真实路由）
  // 采购（procurement/materials/products 已实现，见下方真实路由）
  // 财务（budget/settlement 已实现，见下方真实路由）
  // 生活（smart-home/scene/kitchen/bathroom/appliance/furniture/custom-furniture 已实现，见下方真实路由）
];

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<WorkbenchPage />} />
      <Route path="/tokens" element={<PlaceholderHome />} />
      {/* 批次 4 真实页面 */}
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/budget" element={<BudgetPage />} />
      {/* 批次 5 真实页面 */}
      <Route path="/construction" element={<ConstructionPage />} />
      <Route path="/procurement" element={<ProcurementPage />} />
      <Route path="/settlement" element={<SettlementPage />} />
      <Route path="/tasks" element={<TasksPage />} />
      {/* 批次 6 真实页面 */}
      <Route path="/materials" element={<MaterialsPage />} />
      <Route path="/change-orders" element={<ChangeOrdersPage />} />
      <Route path="/crews" element={<CrewsPage />} />
      <Route path="/smart-home" element={<SmartHomePage />} />
      <Route path="/scene" element={<ScenePage />} />
      {/* 批次 7 真实页面 */}
      <Route path="/floorplans" element={<FloorplansPage />} />
      <Route path="/lighting" element={<LightingPage />} />
      <Route path="/soft-furnishing" element={<SoftFurnishingPage />} />
      <Route path="/kitchen" element={<KitchenPage />} />
      <Route path="/bathroom" element={<BathroomPage />} />
      <Route path="/door-window" element={<DoorWindowPage />} />
      {/* 批次 8 真实页面 */}
      <Route path="/takeoff" element={<TakeoffPage />} />
      <Route path="/structural" element={<StructuralPage />} />
      <Route path="/appliance" element={<AppliancePage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/furniture" element={<FurniturePage />} />
      <Route path="/hard-decoration" element={<HardDecorationPage />} />
      <Route path="/mep" element={<MepPage />} />
      <Route path="/vr-panorama" element={<VRPanoramaPage />} />
      {/* 批次 11 真实页面 */}
      <Route path="/custom-furniture" element={<CustomFurniturePage />} />
      <Route path="/quality" element={<QualityPage />} />
      <Route path="/ai-render" element={<AIRenderPage />} />
      {/* 批次 12 真实页面（上传/导出类） */}
      <Route path="/cad" element={<CADPage />} />
      <Route path="/sketch-3d" element={<Sketch3DPage />} />
      <Route path="/ifc-export" element={<IFCExportPage />} />
      {/* 批次 5/6/7 占位 */}
      {PLACEHOLDER_ROUTES.map((r) => (
        <Route
          key={r.path}
          path={r.path}
          element={
            <SuokeLayout>
              <PlaceholderPage title={r.title} emoji={r.emoji} agent={r.agent} batch="批次 7" />
            </SuokeLayout>
          }
        />
      ))}
      <Route path="*" element={<WorkbenchPage />} />
    </Routes>
  );
}
