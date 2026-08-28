import React, { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppProvider, useApp } from './lib/store'
import Shell from './components/Shell'

import LoginPage from './pages/Login'
import WeChatCallback from './pages/WeChatCallback'
import DocsPage from './pages/DocsPage'
import DashboardPage from './pages/Dashboard'

// 路由级懒加载：Login / Dashboard（首屏）与公开文档页保持静态，其余按需加载减小首屏 bundle
const ProjectsPage = lazy(() => import('./pages/Projects'))
const ProjectDetailPage = lazy(() => import('./pages/ProjectDetail'))
const BudgetPage = lazy(() => import('./pages/Budget'))
const ConstructionPage = lazy(() => import('./pages/Construction'))
const QualityPage = lazy(() => import('./pages/Quality'))
const SettlementPage = lazy(() => import('./pages/Settlement'))
const ProcurementPage = lazy(() => import('./pages/Procurement'))
const SmartHomePage = lazy(() => import('./pages/SmartHome'))
const AiPage = lazy(() => import('./pages/Ai'))
const ProfilePage = lazy(() => import('./pages/Profile'))
const DiagnosticsPage = lazy(() => import('./pages/Diagnostics'))
const DesignFlowPage = lazy(() => import('./pages/DesignFlow'))
// VR 全景页依赖 three.js，懒加载避免拖慢首屏 bundle
const VirtualTourPage = lazy(() => import('./pages/VirtualTour'))
const ARScanPage = lazy(() => import('./pages/ARScan'))
const ShowroomPage = lazy(() => import('./pages/ShowroomPage'))

function SuspenseFallback() {
  return <div className="page-loading mono">加载中…</div>
}

// 懒加载页面统一包装，避免每条路由手写 Suspense
function Lazy({ children }) {
  return <Suspense fallback={<SuspenseFallback />}>{children}</Suspense>
}

function RequireAuth({ children }) {
  const { loggedIn, booted } = useApp()
  if (!booted) return null // 会话恢复中
  if (!loggedIn) return <Navigate to="/auth" replace />
  return children
}

export default function App() {
  return (
    <AppProvider>
      <Routes>
        <Route path="/auth" element={<LoginPage />} />
        <Route path="/wechat-callback" element={<WeChatCallback />} />
        {/* 公开文档页（指南/隐私/条款，无需登录；内容来自 assets/guide + assets/legal） */}
        <Route path="/guide" element={<DocsPage doc="guide" />} />
        <Route path="/legal/privacy" element={<DocsPage doc="privacy" />} />
        <Route path="/legal/terms" element={<DocsPage doc="terms" />} />
        <Route path="/legal/agent-memory-privacy" element={<DocsPage doc="agent-memory" />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<Lazy><ProjectsPage /></Lazy>} />
          <Route path="/projects/:id" element={<Lazy><ProjectDetailPage /></Lazy>} />
          <Route path="/budget" element={<Lazy><BudgetPage /></Lazy>} />
          <Route path="/construction" element={<Lazy><ConstructionPage /></Lazy>} />
          <Route path="/quality" element={<Lazy><QualityPage /></Lazy>} />
          <Route path="/settlement" element={<Lazy><SettlementPage /></Lazy>} />
          <Route path="/procurement" element={<Lazy><ProcurementPage /></Lazy>} />
          <Route path="/smart-home" element={<Lazy><SmartHomePage /></Lazy>} />
          <Route
            path="/virtual-tour"
            element={
              <Lazy>
                <VirtualTourPage />
              </Lazy>
            }
          />
          <Route
            path="/ar-scan"
            element={
              <Lazy>
                <ARScanPage />
              </Lazy>
            }
          />
          <Route
            path="/showroom"
            element={
              <Lazy>
                <ShowroomPage />
              </Lazy>
            }
          />
          <Route path="/ai" element={<Lazy><AiPage /></Lazy>} />
          <Route path="/design-flow" element={<Lazy><DesignFlowPage /></Lazy>} />
          <Route path="/profile" element={<Lazy><ProfilePage /></Lazy>} />
          <Route path="/diagnostics" element={<Lazy><DiagnosticsPage /></Lazy>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppProvider>
  )
}
