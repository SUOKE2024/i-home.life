import { Suspense, lazy } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import AuthGate from './components/AuthGate';
import ErrorBoundary from './components/ErrorBoundary';
import WorkbenchPage from './pages/WorkbenchPage';
import NotFoundPage from './pages/NotFoundPage';

// 路由级懒加载：Workbench（首屏）与 NotFound（404 兜底）保持静态，其余页面按需加载，
// 避免 70+ 页面全量打进主 bundle 拖慢首次访问
const SupplierWorkbenchPage = lazy(() => import('./pages/SupplierWorkbenchPage'));
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'));
const ProjectDetailPage = lazy(() => import('./pages/ProjectDetailPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const BudgetPage = lazy(() => import('./pages/BudgetPage'));
const ConstructionPage = lazy(() => import('./pages/ConstructionPage'));
const ProcurementPage = lazy(() => import('./pages/ProcurementPage'));
const SettlementPage = lazy(() => import('./pages/SettlementPage'));
const TasksPage = lazy(() => import('./pages/TasksPage'));
const MaterialsPage = lazy(() => import('./pages/MaterialsPage'));
const ChangeOrdersPage = lazy(() => import('./pages/ChangeOrdersPage'));
const CrewsPage = lazy(() => import('./pages/CrewsPage'));
const SmartHomePage = lazy(() => import('./pages/SmartHomePage'));
const ScenePage = lazy(() => import('./pages/ScenePage'));
const FloorplansPage = lazy(() => import('./pages/FloorplansPage'));
const LightingPage = lazy(() => import('./pages/LightingPage'));
const SoftFurnishingPage = lazy(() => import('./pages/SoftFurnishingPage'));
const KitchenPage = lazy(() => import('./pages/KitchenPage'));
const BathroomPage = lazy(() => import('./pages/BathroomPage'));
const DoorWindowPage = lazy(() => import('./pages/DoorWindowPage'));
const TakeoffPage = lazy(() => import('./pages/TakeoffPage'));
const StructuralPage = lazy(() => import('./pages/StructuralPage'));
const AppliancePage = lazy(() => import('./pages/AppliancePage'));
const ProductsPage = lazy(() => import('./pages/ProductsPage'));
const FurniturePage = lazy(() => import('./pages/FurniturePage'));
const HardDecorationPage = lazy(() => import('./pages/HardDecorationPage'));
const MepPage = lazy(() => import('./pages/MepPage'));
const VRPanoramaPage = lazy(() => import('./pages/VRPanoramaPage'));
const CustomFurniturePage = lazy(() => import('./pages/CustomFurniturePage'));
const QualityPage = lazy(() => import('./pages/QualityPage'));
const AIRenderPage = lazy(() => import('./pages/AIRenderPage'));
const CADPage = lazy(() => import('./pages/CADPage'));
const Sketch3DPage = lazy(() => import('./pages/Sketch3DPage'));
const IFCExportPage = lazy(() => import('./pages/IFCExportPage'));
const DesignPage = lazy(() => import('./pages/DesignPage'));
const DeliveryPage = lazy(() => import('./pages/DeliveryPage'));
const ElderlyAdaptationPage = lazy(() => import('./pages/ElderlyAdaptationPage'));
const PartialRenovationPage = lazy(() => import('./pages/PartialRenovationPage'));
const EscrowPage = lazy(() => import('./pages/EscrowPage'));
const EnergyPage = lazy(() => import('./pages/EnergyPage'));
const PaymentsPage = lazy(() => import('./pages/PaymentsPage'));
const EcoMaterialsPage = lazy(() => import('./pages/EcoMaterialsPage'));
const SolutionFirstPage = lazy(() => import('./pages/SolutionFirstPage'));
const EcosystemPage = lazy(() => import('./pages/EcosystemPage'));
const AIQAPage = lazy(() => import('./pages/AIQAPage'));
const BudgetComparePage = lazy(() => import('./pages/BudgetComparePage'));
const BudgetTemplatesPage = lazy(() => import('./pages/BudgetTemplatesPage'));
const KitchenBathMepPage = lazy(() => import('./pages/KitchenBathMepPage'));
const WorkersPage = lazy(() => import('./pages/WorkersPage'));
const IMChatPage = lazy(() => import('./pages/IMChatPage'));
const AgentIdentityPage = lazy(() => import('./pages/AgentIdentityPage'));
const AgentApprovalsPage = lazy(() => import('./pages/AgentApprovalsPage'));
const AgentSkillsPage = lazy(() => import('./pages/AgentSkillsPage'));
const AgentMemoryPage = lazy(() => import('./pages/AgentMemoryPage'));
const A2APage = lazy(() => import('./pages/A2APage'));
const MCPPage = lazy(() => import('./pages/MCPPage'));
const HarnessPage = lazy(() => import('./pages/HarnessPage'));
const EvalPage = lazy(() => import('./pages/EvalPage'));
const GovernanceAuditPage = lazy(() => import('./pages/GovernanceAuditPage'));
const PointsPage = lazy(() => import('./pages/PointsPage'));
const AIImagePage = lazy(() => import('./pages/AIImagePage'));
const IdentityPage = lazy(() => import('./pages/IdentityPage'));
const SurveysPage = lazy(() => import('./pages/SurveysPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const FilesPage = lazy(() => import('./pages/FilesPage'));
const HealthMonitorPage = lazy(() => import('./pages/HealthMonitorPage'));
const ConstructionDrawingPage = lazy(() => import('./pages/ConstructionDrawingPage'));
const SensorsPage = lazy(() => import('./pages/SensorsPage'));

function RouteFallback() {
  return (
    <div style={{ padding: 48, textAlign: 'center', color: 'var(--color-text-secondary, #888)' }}>
      加载中…
    </div>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <AuthGate>
      {/* 路由级错误兜底：任一页面运行时异常不再白屏，且路由切换自动复位 */}
      <ErrorBoundary resetOnLocationChange url={location.pathname}>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<WorkbenchPage />} />
            <Route path="/supplier" element={<SupplierWorkbenchPage />} />
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
        </Suspense>
      </ErrorBoundary>
    </AuthGate>
  );
}
