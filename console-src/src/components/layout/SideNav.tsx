/**
 * SideNav — 桌面侧栏（>1024px 才显示，由 SuokeLayout 控制）
 *
 * 分组导航，对齐 Flutter 27 页的业务分类 + ChatHeader 头像入口的设置页。
 * 每项点击切换路由（react-router useNavigate）。
 *
 * 分组（对齐 agent-router.ts 的 agent 分类 + 设置页区块）：
 *   - 主入口：工作台
 *   - 项目：项目列表
 *   - 设计类：设计/户型/灯光/软装/硬装/AI渲染/VR全景/CAD/草图3D/定制家具
 *   - 施工类：施工/任务/变更/工程队/工程量/土建/水电暖通/门窗防水
 *   - 采购类：采购/产品/物料/比价/BOM
 *   - 财务类：预算/结算/支付
 *   - 质检类：质检
 *   - 生活类：厨房/卫浴/家电/家具/智能家居/场景
 *   - 个人：设置
 *
 * 批次 3 仅渲染导航项 + 路由跳转；目标页占位（批次 4/5 实现）。
 */

import { useNavigate, useLocation } from 'react-router-dom';
import { getAgentInfo } from '../../services/agent-router';

interface NavItem {
  label: string;
  path: string;
  agent?: string; // 关联 agent key，取 emoji/color
  emoji?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: '主入口',
    items: [
      { label: '工作台', path: '/', emoji: '🏠' },
      { label: '仪表盘', path: '/dashboard', emoji: '📊' },
      { label: '装企交付', path: '/delivery', emoji: '📦' },
      { label: '协作IM', path: '/im-chat', emoji: '💬' },
    ],
  },
  {
    title: '项目',
    items: [{ label: '项目列表', path: '/projects', emoji: '📋' }],
  },
  {
    title: '设计',
    items: [
      { label: '设计', path: '/design', agent: 'design' },
      { label: '户型', path: '/floorplans', agent: 'floorplans' },
      { label: '灯光', path: '/lighting', agent: 'lighting' },
      { label: '软装', path: '/soft-furnishing', agent: 'soft_furnishing' },
      { label: '硬装', path: '/hard-decoration', agent: 'hard_decoration' },
      { label: 'AI渲染', path: '/ai-render', agent: 'ai_render' },
      { label: 'VR全景', path: '/vr-panorama', agent: 'vr_panorama' },
      { label: 'CAD导入', path: '/cad', agent: 'cad_import' },
      { label: '草图转3D', path: '/sketch-3d', agent: 'sketch_to_3d' },
      { label: '定制家具', path: '/custom-furniture', agent: 'custom_furniture' },
    ],
  },
  {
    title: '施工',
    items: [
      { label: '施工', path: '/construction', agent: 'construction' },
      { label: '任务', path: '/tasks', agent: 'tasks' },
      { label: '变更', path: '/change-orders', agent: 'change_orders' },
      { label: '工程队', path: '/crews', agent: 'crews' },
      { label: '服务商匹配', path: '/workers', emoji: '🧑‍🔧' },
      { label: '工程量', path: '/takeoff', agent: 'takeoff' },
      { label: '土建结构', path: '/structural', agent: 'structural' },
      { label: '水电暖通', path: '/mep', agent: 'mep' },
      { label: '厨卫水电', path: '/kitchen-bath-mep', emoji: '🔧' },
      { label: '门窗防水', path: '/door-window', agent: 'door_window_waterproof' },
    ],
  },
  {
    title: '采购',
    items: [
      { label: '采购', path: '/procurement', agent: 'procurement' },
      { label: '产品', path: '/products', agent: 'products' },
      { label: '物料', path: '/materials', agent: 'procurement' },
      { label: 'BIM导出', path: '/ifc-export', agent: 'ifc_export' },
    ],
  },
  {
    title: '财务',
    items: [
      { label: '预算', path: '/budget', agent: 'budget' },
      { label: '方案对比', path: '/budget-compare', emoji: '📊' },
      { label: '模板库', path: '/budget-templates', emoji: '📚' },
      { label: '结算', path: '/settlement', agent: 'settlement' },
    ],
  },
  {
    title: '质检',
    items: [{ label: '质检', path: '/quality', agent: 'quality' }],
  },
  {
    title: '生活',
    items: [
      { label: '厨房', path: '/kitchen', agent: 'kitchen' },
      { label: '卫浴', path: '/bathroom', agent: 'bathroom' },
      { label: '家电', path: '/appliance', agent: 'appliance' },
      { label: '家具', path: '/furniture', agent: 'furniture_catalog' },
      { label: '智能家居', path: '/smart-home', agent: 'smart_home' },
      { label: '场景', path: '/scene', agent: 'scene_automation' },
    ],
  },
  {
    title: '个人',
    items: [{ label: '设置', path: '/settings', emoji: '⚙️' }],
  },
  {
    title: '新增功能（v1.5.0）',
    items: [
      { label: '适老改造', path: '/elderly-adaptation', emoji: '🧓' },
      { label: '局部焕新', path: '/partial-renovation', emoji: '🔧' },
      { label: '资金托管', path: '/escrow', emoji: '🛡' },
      { label: '环保材料', path: '/eco-materials', emoji: '🌿' },
      { label: '方案前置', path: '/solution-first', emoji: '🚀' },
      { label: '生态桥接', path: '/ecosystem', emoji: '🔗' },
      { label: 'AI 问答', path: '/ai-qa', emoji: '🤖' },
    ],
  },
];

export default function SideNav() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="wb-sidenav" aria-label="主导航" data-testid="wb-sidenav">
      <div className="wb-sidenav__brand">
        <span style={{ fontSize: 20 }}>🏠</span>
        <span className="wb-sidenav__brand-text">索克家居</span>
      </div>
      <div className="wb-sidenav__scroll">
        {NAV_GROUPS.map((group) => (
          <div className="wb-sidenav__group" key={group.title}>
            <div className="wb-sidenav__group-title">{group.title}</div>
            {group.items.map((item) => {
              const info = item.agent ? getAgentInfo(item.agent) : null;
              const emoji = item.emoji ?? info?.emoji ?? '·';
              const color = info?.color;
              const isActive = location.pathname === item.path;
              return (
                <button
                  key={item.path}
                  type="button"
                  className={`wb-sidenav__item ${isActive ? 'wb-sidenav__item--active' : ''}`}
                  onClick={() => navigate(item.path)}
                  aria-current={isActive ? 'page' : undefined}
                  data-testid={`wb-sidenav-item--${item.path.replace(/\//g, '') || 'root'}`}
                  style={isActive && color ? { color } : undefined}
                >
                  <span className="wb-sidenav__item-emoji">{emoji}</span>
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </nav>
  );
}
