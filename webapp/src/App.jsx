import React, { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppProvider, useApp } from './lib/store'
import Shell from './components/Shell'

import LoginPage from './pages/Login'
import DocsPage from './pages/DocsPage'
import DashboardPage from './pages/Dashboard'
import ProjectsPage from './pages/Projects'
import BudgetPage from './pages/Budget'
import ConstructionPage from './pages/Construction'
import QualityPage from './pages/Quality'
import SettlementPage from './pages/Settlement'
import ProcurementPage from './pages/Procurement'
import SmartHomePage from './pages/SmartHome'
import AiPage from './pages/Ai'
import ProfilePage from './pages/Profile'
import DiagnosticsPage from './pages/Diagnostics'
// VR 全景页依赖 three.js，懒加载避免拖慢首屏 bundle
const VirtualTourPage = lazy(() => import('./pages/VirtualTour'))
const ARScanPage = lazy(() => import('./pages/ARScan'))
const ShowroomPage = lazy(() => import('./pages/ShowroomPage'))

function SuspenseFallback() {
  return <div className="page-loading mono">加载中…</div>
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
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/construction" element={<ConstructionPage />} />
          <Route path="/quality" element={<QualityPage />} />
          <Route path="/settlement" element={<SettlementPage />} />
          <Route path="/procurement" element={<ProcurementPage />} />
          <Route path="/smart-home" element={<SmartHomePage />} />
          <Route
            path="/virtual-tour"
            element={
              <Suspense fallback={<SuspenseFallback />}>
                <VirtualTourPage />
              </Suspense>
            }
          />
          <Route
            path="/ar-scan"
            element={
              <Suspense fallback={<SuspenseFallback />}>
                <ARScanPage />
              </Suspense>
            }
          />
          <Route
            path="/showroom"
            element={
              <Suspense fallback={<SuspenseFallback />}>
                <ShowroomPage />
              </Suspense>
            }
          />
          <Route path="/ai" element={<AiPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppProvider>
  )
}
