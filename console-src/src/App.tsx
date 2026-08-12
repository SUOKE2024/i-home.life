import { Routes, Route, useLocation } from 'react-router-dom';
import AuthGate from './components/AuthGate';
import ErrorBoundary from './components/ErrorBoundary';
import WorkbenchPage from './pages/WorkbenchPage';
import NotFoundPage from './pages/NotFoundPage';
import PlaceholderHome from './pages/PlaceholderHome';

import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import DashboardPage from './pages/DashboardPage';
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
import DesignPage from './pages/DesignPage';
import DeliveryPage from './pages/DeliveryPage';
import ElderlyAdaptationPage from './pages/ElderlyAdaptationPage';
import PartialRenovationPage from './pages/PartialRenovationPage';
import EscrowPage from './pages/EscrowPage';
import EnergyPage from './pages/EnergyPage';
import PaymentsPage from './pages/PaymentsPage';
import EcoMaterialsPage from './pages/EcoMaterialsPage';
import SolutionFirstPage from './pages/SolutionFirstPage';
import EcosystemPage from './pages/EcosystemPage';
import AIQAPage from './pages/AIQAPage';
import BudgetComparePage from './pages/BudgetComparePage';
import BudgetTemplatesPage from './pages/BudgetTemplatesPage';
import KitchenBathMepPage from './pages/KitchenBathMepPage';
import WorkersPage from './pages/WorkersPage';
import IMChatPage from './pages/IMChatPage';
import AgentIdentityPage from './pages/AgentIdentityPage';
import AgentApprovalsPage from './pages/AgentApprovalsPage';
import AgentSkillsPage from './pages/AgentSkillsPage';
import AgentMemoryPage from './pages/AgentMemoryPage';
import A2APage from './pages/A2APage';
import MCPPage from './pages/MCPPage';
import HarnessPage from './pages/HarnessPage';
import EvalPage from './pages/EvalPage';
import GovernanceAuditPage from './pages/GovernanceAuditPage';
import PointsPage from './pages/PointsPage';
import AIImagePage from './pages/AIImagePage';
import IdentityPage from './pages/IdentityPage';
import SurveysPage from './pages/SurveysPage';
import AdminPage from './pages/AdminPage';
import NotificationsPage from './pages/NotificationsPage';
import FilesPage from './pages/FilesPage';
import HealthMonitorPage from './pages/HealthMonitorPage';
import ConstructionDrawingPage from './pages/ConstructionDrawingPage';
import SensorsPage from './pages/SensorsPage';

export default function App() {
  const location = useLocation();
  return (
    <AuthGate>
      {/* 路由级错误兜底：任一页面运行时异常不再白屏，且路由切换自动复位 */}
      <ErrorBoundary resetOnLocationChange url={location.pathname}>
        <Routes>
          <Route path="/" element={<WorkbenchPage />} />
          <Route path="/tokens" element={<PlaceholderHome />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/construction" element={<ConstructionPage />} />
          <Route path="/procurement" element={<ProcurementPage />} />
          <Route path="/settlement" element={<SettlementPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/materials" element={<MaterialsPage />} />
          <Route path="/change-orders" element={<ChangeOrdersPage />} />
          <Route path="/crews" element={<CrewsPage />} />
          <Route path="/smart-home" element={<SmartHomePage />} />
          <Route path="/scene" element={<ScenePage />} />
          <Route path="/floorplans" element={<FloorplansPage />} />
          <Route path="/lighting" element={<LightingPage />} />
          <Route path="/soft-furnishing" element={<SoftFurnishingPage />} />
          <Route path="/kitchen" element={<KitchenPage />} />
          <Route path="/bathroom" element={<BathroomPage />} />
          <Route path="/door-window" element={<DoorWindowPage />} />
          <Route path="/takeoff" element={<TakeoffPage />} />
          <Route path="/structural" element={<StructuralPage />} />
          <Route path="/appliance" element={<AppliancePage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/furniture" element={<FurniturePage />} />
          <Route path="/hard-decoration" element={<HardDecorationPage />} />
          <Route path="/mep" element={<MepPage />} />
          <Route path="/vr-panorama" element={<VRPanoramaPage />} />
          <Route path="/custom-furniture" element={<CustomFurniturePage />} />
          <Route path="/quality" element={<QualityPage />} />
          <Route path="/ai-render" element={<AIRenderPage />} />
          <Route path="/cad" element={<CADPage />} />
          <Route path="/sketch-3d" element={<Sketch3DPage />} />
          <Route path="/ifc-export" element={<IFCExportPage />} />
          <Route path="/design" element={<DesignPage />} />
          <Route path="/delivery" element={<DeliveryPage />} />
          <Route path="/elderly-adaptation" element={<ElderlyAdaptationPage />} />
          <Route path="/partial-renovation" element={<PartialRenovationPage />} />
          <Route path="/escrow" element={<EscrowPage />} />
          <Route path="/energy" element={<EnergyPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/eco-materials" element={<EcoMaterialsPage />} />
          <Route path="/solution-first" element={<SolutionFirstPage />} />
          <Route path="/ecosystem" element={<EcosystemPage />} />
          <Route path="/ai-qa" element={<AIQAPage />} />
          <Route path="/budget-compare" element={<BudgetComparePage />} />
          <Route path="/budget-templates" element={<BudgetTemplatesPage />} />
          <Route path="/kitchen-bath-mep" element={<KitchenBathMepPage />} />
          <Route path="/workers" element={<WorkersPage />} />
          <Route path="/im-chat" element={<IMChatPage />} />
          {/* Agent 治理 */}
          <Route path="/agent-identity" element={<AgentIdentityPage />} />
          <Route path="/agent-approvals" element={<AgentApprovalsPage />} />
          <Route path="/agent-skills" element={<AgentSkillsPage />} />
          <Route path="/agent-memory" element={<AgentMemoryPage />} />
          <Route path="/a2a" element={<A2APage />} />
          <Route path="/mcp" element={<MCPPage />} />
          <Route path="/harness" element={<HarnessPage />} />
          <Route path="/eval" element={<EvalPage />} />
          <Route path="/governance-audit" element={<GovernanceAuditPage />} />
          {/* 积分商城 / AI 图生图 / 身份认证 / 量房-AR 扫描 */}
          <Route path="/points" element={<PointsPage />} />
          <Route path="/ai-image" element={<AIImagePage />} />
          <Route path="/identity" element={<IdentityPage />} />
          <Route path="/surveys" element={<SurveysPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/files" element={<FilesPage />} />
          <Route path="/health-monitor" element={<HealthMonitorPage />} />
          <Route path="/construction-drawing" element={<ConstructionDrawingPage />} />
          <Route path="/sensors" element={<SensorsPage />} />
          {/* 真 404：取代此前静默回退到 Workbench 的反直觉行为 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ErrorBoundary>
    </AuthGate>
  );
}
