#!/usr/bin/env node
/**
 * check-token-sync.mjs — DESIGN.md（规范源）与三端核心 token 一致性校验
 *
 * 背景：console-src/src/tokens/tokens.ts 注释声明「由 CI 校验脚本 scripts/check-token-sync.ts
 * 保证一致」，但该脚本此前缺失。DESIGN.md（Google design.md 格式）落地后，以它为唯一规范源，
 * 校验 Flutter suoke_theme.dart / console tokens.css / webapp tokens.css 的跨主题恒定核心值。
 *
 * 用法:
 *   node scripts/check-token-sync.mjs
 *   # 与 design-lint 搭配（CI）:
 *   npx @google/design.md lint DESIGN.md && node scripts/check-token-sync.mjs
 *
 * 规则:
 *   - 只校验「跨主题恒定 + 三端均应有」的核心 token（品牌/表面/文字）。
 *   - 语义色与 Agent 色存在历史差异（webapp 旧亮色系 vs console/flutter 深色系），不在本脚本范围。
 *   - 退出码 1 = 漂移，CI 可据此拦截。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8');

// ── 从 DESIGN.md front matter 提取规范值 ──
const dm = read('DESIGN.md');
const fm = dm.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? '';
if (!fm) {
  console.error('❌ 无法解析 DESIGN.md front matter');
  process.exit(1);
}
const specColor = (name) => {
  const m = fm.match(new RegExp(`^  ${name}: "#([0-9A-Fa-f]{6})"`, 'm'));
  return m ? m[1].toUpperCase() : null;
};

// ── 三端源码 ──
const sources = {
  Flutter: read('flutter_app/lib/theme/suoke_theme.dart'),
  console: read('console-src/src/tokens/tokens.css'),
  webapp: read('webapp/src/styles/tokens.css'),
};

// ── 校验清单：DESIGN.md token → 期望 hex（大小写不敏感搜索，防漂移）──
const CHECKS = [
  'primary', 'accent-bright', 'on-accent',
  'surface1', 'surface2',
  'text-primary', 'text-secondary', 'text-muted',
];

let failed = 0;
for (const token of CHECKS) {
  const expected = specColor(token);
  if (!expected) {
    console.error(`❌ DESIGN.md 缺少 color token: ${token}`);
    failed++;
    continue;
  }
  const expectedUpper = expected.toUpperCase();
  for (const [end, src] of Object.entries(sources)) {
    if (!src.toUpperCase().includes(expectedUpper)) {
      console.error(`❌ [${end}] 缺少规范值 ${token}=#${expected}`);
      failed++;
    }
  }
}

if (failed === 0) {
  console.log(`✅ DESIGN.md 与三端核心 token 一致（${CHECKS.length} 项 × 3 端）`);
  process.exit(0);
}
process.exit(1);
