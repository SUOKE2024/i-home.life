import React, { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, FolderKanban, Wallet, HardHat, ShieldCheck, FileCheck2,
  ShoppingCart, Home, Bot, UserCircle, LogOut, Menu, Search, Bell, ChevronDown,
  Activity,
} from 'lucide-react'
import { Logo, Avatar } from './ui'
import { useApp } from '../lib/store'

const NAV = [
  { to: '/', label: '聚合看板', icon: LayoutDashboard, end: true },
  { to: '/projects', label: '项目管理', icon: FolderKanban },
  { to: '/budget', label: '预算管理', icon: Wallet },
  { to: '/construction', label: '施工管理', icon: HardHat },
  { to: '/quality', label: '质检验收', icon: ShieldCheck },
  { to: '/settlement', label: '结算管理', icon: FileCheck2 },
  { to: '/procurement', label: '采购管理', icon: ShoppingCart },
  { to: '/smart-home', label: '智能家居', icon: Home },
]

const PAGE_TITLES = {
  '/': ['聚合看板', 'HOME DASHBOARD'],
  '/projects': ['项目管理', 'PROJECTS'],
  '/budget': ['预算管理', 'BUDGET'],
  '/construction': ['施工管理', 'CONSTRUCTION'],
  '/quality': ['质检验收', 'QA INSPECTION'],
  '/settlement': ['结算管理', 'SETTLEMENT'],
  '/procurement': ['采购管理', 'PROCUREMENT'],
  '/smart-home': ['智能家居', 'SMART HOME'],
  '/ai': ['AI 管家', 'AI CONCIERGE'],
  '/profile': ['我的', 'PROFILE'],
  '/diagnostics': ['全链路诊断', 'DIAGNOSTICS'],
}

export default function Shell() {
  const { user, logout, toast, navCollapsed, setNavCollapsed } = useApp()
  const loc = useLocation()
  const nav = useNavigate()
  const [tick, setTick] = useState(0)

  const meta = PAGE_TITLES[loc.pathname] || PAGE_TITLES['/']

  const handleLogout = async () => {
    await logout()
    toast('已退出登录', 'info')
    nav('/auth')
  }

  return (
    <div className={`shell${navCollapsed ? ' shell--collapsed' : ''}`}>
      <SideNav
        collapsed={navCollapsed}
        onToggle={() => setNavCollapsed(!navCollapsed)}
        user={user}
        onLogout={handleLogout}
      />
      <div className="shell-main">
        <TopBar title={meta[0]} sub={meta[1]} tick={tick} user={user} />
        <main className="shell-content">
          <Outlet />
        </main>
        <Footer />
      </div>
      <Toasts />
    </div>
  )
}

/* ================= 侧边导航 ================= */
function SideNav({ collapsed, onToggle, user, onLogout }) {
  return (
    <aside className={`sidenav${collapsed ? ' sidenav--collapsed' : ''}`}>
      <div className="sidenav-brand">
        <Logo size={collapsed ? 32 : 34} withText={!collapsed} />
      </div>

      <nav className="sidenav-nav">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={collapsed ? label : undefined}
            className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
          >
            <Icon size={18} strokeWidth={1.8} />
            {!collapsed && <span className="nav-label">{label}</span>}
            {!collapsed && <i className="nav-caret" />}
          </NavLink>
        ))}

        <div className="nav-divider" />

        <NavLink
          to="/ai"
          className={({ isActive }) => `nav-item nav-item--ai${isActive ? ' nav-item--active' : ''}`}
          title={collapsed ? 'AI 管家' : undefined}
        >
          <Bot size={18} strokeWidth={1.8} />
          {!collapsed && <span className="nav-label">AI 管家</span>}
          {!collapsed && <span className="nav-ai-live mono">● AI</span>}
        </NavLink>

        <NavLink
          to="/diagnostics"
          className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
          title={collapsed ? '全链路诊断' : undefined}
        >
          <Activity size={18} strokeWidth={1.8} />
          {!collapsed && <span className="nav-label">全链路诊断</span>}
        </NavLink>

        <NavLink
          to="/profile"
          className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
          title={collapsed ? '我的' : undefined}
        >
          <UserCircle size={18} strokeWidth={1.8} />
          {!collapsed && <span className="nav-label">我的</span>}
        </NavLink>
      </nav>

      <div className="sidenav-foot">
        {!collapsed && (
          <div className="sidenav-user">
            <Avatar text={user?.name?.[0] || '索'} />
            <div className="grow">
              <div className="sidenav-user-name">{user?.name || '索克用户'}</div>
              <div className="sidenav-user-meta mono">
                {user?.phone || '未登录'} · {user?.role || '-'}
              </div>
            </div>
            <button className="icon-btn icon-btn--ghost" onClick={onLogout} title="退出登录">
              <LogOut size={15} />
            </button>
          </div>
        )}
        <button className="nav-collapse" onClick={onToggle} title={collapsed ? '展开导航' : '收起导航'}>
          <Menu size={16} />
        </button>
      </div>
    </aside>
  )
}

/* ================= 顶栏 ================= */
function TopBar({ title, sub, tick, user }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <h1 className="topbar-title">{title}</h1>
        <span className="topbar-sub mono">{sub}</span>
      </div>

      <div className="topbar-right">
        <div className="topbar-date mono dim">{new Date().toLocaleDateString('zh-CN')}</div>
        <button className="icon-btn" title="搜索">
          <Search size={16} />
        </button>
        <button className="icon-btn" title="通知">
          <Bell size={16} />
          <i className="notify-dot" />
        </button>
        <div className="topbar-user">
          <Avatar text={user?.name?.[0] || '索'} size={30} />
          <span className="topbar-user-name">{user?.name?.slice(0, 6) || '索克用户'}</span>
          <ChevronDown size={13} className="dim" />
        </div>
      </div>
    </header>
  )
}

/* ================= 备案号 Footer =================
 * 工信部要求：网站主页下方悬挂互联网信息服务备案号，并链接至工信部备案管理系统。
 */
function Footer() {
  return (
    <footer className="app-footer">
      <span className="app-footer-copy">© 2026 索克家居 · i-home.life — AI 智能装修平台</span>
      <span className="app-footer-beian">
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
          滇ICP备2026015233号-2
        </a>
      </span>
    </footer>
  )
}

/* ================= Toast ================= */
function Toasts() {
  const { toasts } = useApp()
  return (
    <div className="toasts">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast--${t.type}`}>
          <i className="toast-dot" />
          {t.message}
        </div>
      ))}
    </div>
  )
}
