import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 9
 *
 * 验证 ProductsPage / FurniturePage / HardDecorationPage：
 *   1. 列表渲染（mock API，字段对齐 snake_case）
 *   2. 分类筛选 / 方案类型筛选交互
 *   3. 空状态
 *
 * mock 策略：localStorage 预设 paseto_token，拦截 /api/* 返回固定数据。
 */

const MOCK_PROJECTS = [
  {
    id: 'proj-1',
    name: '三居室整装',
    address: '上海市浦东新区',
    total_area: 120,
    status: 'construction',
    project_type: 'full_renovation',
    owner_id: 'user-1',
    created_at: '2026-06-15T10:00:00Z',
    updated_at: '2026-07-20T14:30:00Z',
  },
];

// ════════════════════════════════════════════
// ProductsPage 产品管理
// ════════════════════════════════════════════

const MOCK_PRODUCTS = [
  {
    id: 'p1', user_id: 'u1', supplier_id: 's1', name: '高档复合地板', category: '地板',
    description: '环保E0级', price_min: 89, price_max: 159, unit: '㎡',
    images: null, cover_image: null, tags: ['环保', '耐磨'], specs: null,
    stock_status: 'in_stock', status: 'active', ai_generated: false, ai_description: null,
    created_at: '', updated_at: '',
  },
  {
    id: 'p2', user_id: 'u1', supplier_id: 's2', name: '乳胶漆套餐', category: '涂料',
    description: '全屋涂刷', price_min: 25, price_max: null, unit: '㎡',
    images: null, cover_image: null, tags: null, specs: null,
    stock_status: 'in_stock', status: 'active', ai_generated: true, ai_description: 'AI推荐',
    created_at: '', updated_at: '',
  },
];

test.describe('ProductsPage 产品管理', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch9');
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('产品列表渲染 + 分类筛选', async ({ page }) => {
    await page.route('**/api/products', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PRODUCTS) });
    });

    await page.goto('./products');
    await expect(page.getByTestId('wb-products-content')).toBeVisible({ timeout: 5000 });

    // 默认全部 2 个
    await expect(page.locator('[data-testid^="wb-products-item--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-products-item--0')).toContainText('复合地板');
    await expect(page.getByTestId('wb-products-item--1')).toContainText('AI');

    // 点击地板筛选 → 1 个
    await page.getByTestId('wb-products-filter--地板').click();
    await expect(page.locator('[data-testid^="wb-products-item--"]')).toHaveCount(1);

    await expect(page).toHaveScreenshot('products-filtered.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/products', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.goto('./products');
    await expect(page.getByTestId('wb-products-empty')).toBeVisible({ timeout: 5000 });
  });
});

// ════════════════════════════════════════════
// FurniturePage 家具品类
// ════════════════════════════════════════════

const MOCK_FURNITURE = [
  {
    id: 'f1', category: '沙发', subcategory: '三人沙发', name: '北欧布艺沙发', brand: '宜家',
    model: 'KIVIK', width: 2.2, depth: 0.95, height: 0.83, weight_kg: 45, material: '棉麻',
    color: '灰色', style: '北欧', price: 4999, sale_price: 3999, image_url: null,
    model_3d_url: null, ar_preview_supported: true, stock_count: 12, rating: 4.5,
    sales_count: 230, view_count: 1500, tags: ['热销'], specs: null, status: 'active',
    created_at: '', updated_at: '',
  },
  {
    id: 'f2', category: '床', subcategory: '双人床', name: '实木双人床', brand: '林氏',
    model: null, width: 1.8, depth: 2.0, height: 1.0, weight_kg: 80, material: '橡木',
    color: '原木色', style: '日式', price: 3299, sale_price: null, image_url: null,
    model_3d_url: null, ar_preview_supported: false, stock_count: 0, rating: 4.2,
    sales_count: 150, view_count: 800, tags: null, specs: null, status: 'active',
    created_at: '', updated_at: '',
  },
];

test.describe('FurniturePage 家具品类', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch9');
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('家具列表渲染 + 分类筛选 + 促销价展示', async ({ page }) => {
    await page.route('**/api/furniture-catalog', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FURNITURE) });
    });

    await page.goto('./furniture');
    await expect(page.getByTestId('wb-furniture-content')).toBeVisible({ timeout: 5000 });

    await expect(page.locator('[data-testid^="wb-furniture-item--"]')).toHaveCount(2);
    // 沙发有 AR 标记 + 促销价
    await expect(page.getByTestId('wb-furniture-item--0')).toContainText('AR');
    await expect(page.getByTestId('wb-furniture-item--0')).toContainText('3,999');
    // 床缺货
    await expect(page.getByTestId('wb-furniture-item--1')).toContainText('缺货');

    // 点击床筛选
    await page.getByTestId('wb-furniture-filter--床').click();
    await expect(page.locator('[data-testid^="wb-furniture-item--"]')).toHaveCount(1);

    await expect(page).toHaveScreenshot('furniture-filtered.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/furniture-catalog', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.goto('./furniture');
    await expect(page.getByTestId('wb-furniture-empty')).toBeVisible({ timeout: 5000 });
  });
});

// ════════════════════════════════════════════
// HardDecorationPage 硬装设计
// ════════════════════════════════════════════

const MOCK_SCHEMES = [
  {
    id: 'hd1', project_id: 'proj-1', room_name: '客厅', scheme_type: 'floor',
    floor_area: 28.5, wall_area: 0, ceiling_area: 0, total_budget: 8500,
    status: 'active', notes: '800x800 通体大理石',
    created_at: '2026-06-20T10:00:00Z', updated_at: '2026-06-20T10:00:00Z',
  },
  {
    id: 'hd2', project_id: 'proj-1', room_name: '主卧', scheme_type: 'wall',
    floor_area: 0, wall_area: 42.0, ceiling_area: 0, total_budget: 3200,
    status: 'draft', notes: null,
    created_at: '2026-06-21T10:00:00Z', updated_at: '2026-06-21T10:00:00Z',
  },
  {
    id: 'hd3', project_id: 'proj-1', room_name: '客厅', scheme_type: 'ceiling',
    floor_area: 0, wall_area: 0, ceiling_area: 28.5, total_budget: 5600,
    status: 'completed', notes: '石膏板吊顶+灯带',
    created_at: '2026-06-22T10:00:00Z', updated_at: '2026-06-22T10:00:00Z',
  },
];

test.describe('HardDecorationPage 硬装设计', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch9');
    });
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('硬装方案列表渲染 + 类型筛选 + 状态徽章', async ({ page }) => {
    await page.route('**/api/hard-decoration/schemes/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SCHEMES) });
    });

    await page.goto('./hard-decoration');
    await expect(page.getByTestId('wb-harddecoration-content')).toBeVisible({ timeout: 5000 });

    // 默认全部 3 个
    await expect(page.locator('[data-testid^="wb-harddecoration-item--"]')).toHaveCount(3);
    await expect(page.getByTestId('wb-harddecoration-item--0')).toContainText('客厅');
    await expect(page.getByTestId('wb-harddecoration-status--0')).toContainText('进行中');
    await expect(page.getByTestId('wb-harddecoration-status--2')).toContainText('已完成');

    // 点击地面筛选 → 1 个
    await page.getByTestId('wb-harddecoration-filter--floor').click();
    await expect(page.locator('[data-testid^="wb-harddecoration-item--"]')).toHaveCount(1);

    await expect(page).toHaveScreenshot('harddecoration-filtered.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/hard-decoration/schemes/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.goto('./hard-decoration');
    await expect(page.getByTestId('wb-harddecoration-empty')).toBeVisible({ timeout: 5000 });
  });
});
