import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 10
 *
 * 验证 MepPage（水电暖通点位标准）+ VRPanoramaPage（VR 全景图）：
 *   1. 房型 tab 切换 + 点位标准展示
 *   2. 项目全景图列表渲染 + 状态徽章
 *   3. 空状态
 *
 * mock 策略：localStorage 预设 paseto_token，拦截 /api/* 返回固定数据。
 */

const MOCK_PROJECTS = [
  {
    id: 'proj-1', name: '三居室整装', address: '上海市浦东新区',
    total_area: 120, status: 'construction', project_type: 'full_renovation',
    owner_id: 'user-1', created_at: '2026-06-15T10:00:00Z', updated_at: '2026-07-20T14:30:00Z',
  },
];

// ════════════════════════════════════════════
// MepPage 水电暖通
// ════════════════════════════════════════════

const MOCK_LIVING_ROOM = {
  name: '客厅', switches: 3, sockets: 8, lights: 4, network: 2, tv: 1, ac: 1,
  details: [
    { name: '电视背景墙插座', height: 300, count: 3, type: 'socket' },
    { name: '沙发两侧插座', height: 300, count: 2, type: 'socket' },
    { name: '空调插座', height: 2200, count: 1, type: 'ac_socket' },
    { name: '主灯开关', height: 1300, count: 1, type: 'switch' },
    { name: '网络面板', height: 300, count: 1, type: 'network' },
  ],
};

const MOCK_KITCHEN = {
  name: '厨房', switches: 2, sockets: 10, lights: 3, network: 0, ac: 0,
  details: [
    { name: '冰箱专用插座', height: 500, count: 1, type: 'socket' },
    { name: '油烟机插座', height: 2200, count: 1, type: 'socket' },
    { name: '台面插座(带开关)', height: 1100, count: 4, type: 'socket' },
    { name: '洗碗机/烤箱插座', height: 500, count: 2, type: 'socket' },
    { name: '主灯开关', height: 1300, count: 1, type: 'switch' },
  ],
};

test.describe('MepPage 水电暖通', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch10');
    });
    await page.route('**/api/voice/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('客厅点位标准渲染 + tab 切换至厨房', async ({ page }) => {
    await page.route('**/api/mep/room-standards/living_room', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_LIVING_ROOM) });
    });
    await page.route('**/api/mep/room-standards/kitchen', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_KITCHEN) });
    });

    await page.goto('./mep');
    await expect(page.getByTestId('wb-mep-content')).toBeVisible({ timeout: 5000 });

    // 默认客厅：5 个统计（开关/插座/灯具/网络/电视/空调 = 6 个）
    await expect(page.locator('.wb-takeoff-stat')).toHaveCount(6);
    await expect(page.getByTestId('wb-mep-stats')).toContainText('8');
    // 详细点位 5 项
    await expect(page.locator('[data-testid^="wb-mep-detail--"]')).toHaveCount(5);
    await expect(page.getByTestId('wb-mep-detail--0')).toContainText('电视背景墙插座');

    // 切换至厨房
    await page.getByTestId('wb-mep-tab--kitchen').click();
    await expect(page.getByTestId('wb-mep-content')).toContainText('厨房');
    // 厨房无 tv 字段 → 5 个统计（开关/插座/灯具/网络/空调）
    await expect(page.locator('.wb-takeoff-stat')).toHaveCount(5);
    await expect(page.getByTestId('wb-mep-detail--0')).toContainText('冰箱专用插座');

    await expect(page).toHaveScreenshot('mep-kitchen.png');
  });
});

// ════════════════════════════════════════════
// VRPanoramaPage VR 全景
// ════════════════════════════════════════════

const MOCK_PANORAMAS = [
  {
    id: 'vr1', project_id: 'proj-1', room_name: '客厅', panorama_type: 'equirectangular',
    image_url: null, thumbnail_url: null, resolution: '4K',
    initial_view: null, hotspots: [{ id: 'h1' }, { id: 'h2' }],
    status: 'completed', created_at: '2026-07-01T10:00:00Z',
  },
  {
    id: 'vr2', project_id: 'proj-1', room_name: '主卧', panorama_type: 'equirectangular',
    image_url: null, thumbnail_url: null, resolution: '8K',
    initial_view: null, hotspots: [],
    status: 'rendering', created_at: '2026-07-02T10:00:00Z',
  },
];

test.describe('VRPanoramaPage VR 全景', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch10');
    });
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/voice/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('全景图列表渲染 + 状态徽章 + 热点数', async ({ page }) => {
    await page.route('**/api/vr/panoramas/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PANORAMAS) });
    });

    await page.goto('./vr-panorama');
    await expect(page.getByTestId('wb-vrpanorama-content')).toBeVisible({ timeout: 5000 });

    await expect(page.locator('[data-testid^="wb-vrpanorama-item--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-vrpanorama-item--0')).toContainText('客厅');
    await expect(page.getByTestId('wb-vrpanorama-item--0')).toContainText('球面全景');
    await expect(page.getByTestId('wb-vrpanorama-item--0')).toContainText('4K');
    await expect(page.getByTestId('wb-vrpanorama-item--0')).toContainText('2 热点');
    await expect(page.getByTestId('wb-vrpanorama-status--0')).toContainText('已完成');
    await expect(page.getByTestId('wb-vrpanorama-status--1')).toContainText('渲染中');

    await expect(page).toHaveScreenshot('vrpanorama-list.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/vr/panoramas/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.goto('./vr-panorama');
    await expect(page.getByTestId('wb-vrpanorama-empty')).toBeVisible({ timeout: 5000 });
  });
});
