#!/usr/bin/env node
/**
 * 生成/校正微信小程序工程配置（project.config.json）。
 *
 * 用法：
 *   MINIPROGRAM_APP_ID=wx1234567890abcdef node scripts/prepare-miniprogram.mjs
 *
 * 为什么需要脚本：project.config.json 里的 appid 属于「团队账号信息」，
 * 不入库真实值（避免在开源/多租户构建中误提交），由 CI 或本地构建前注入。
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const configPath = resolve(root, 'project.config.json');

if (!existsSync(configPath)) {
  console.error('[prepare] 未找到 project.config.json');
  process.exit(1);
}

const appid = process.env.MINIPROGRAM_APP_ID || '';
const projectname = process.env.MINIPROGRAM_PROJECT_NAME || 'suoke-home-miniapp';
const config = JSON.parse(readFileSync(configPath, 'utf8'));

if (!appid) {
  console.warn(
    '[prepare] 未提供 MINIPROGRAM_APP_ID，保留现有 appid：' +
      `${config.appid}（开发者工具仅能以游客/试玩模式打开）`
  );
} else if (!/^wx[0-9a-f]{16}$/i.test(appid)) {
  console.error('[prepare] MINIPROGRAM_APP_ID 格式不合法，应为 wx + 16 位十六进制');
  process.exit(1);
} else {
  config.appid = appid;
}

config.projectname = projectname;
config.description = '索克家居业主端小程序 · 空间健康资产运营商（Taro 4.3 + React 18）';
config.miniprogramRoot = 'dist/';
config.compileType = 'miniprogram';
config.setting = {
  ...config.setting,
  // 生产构建产物已是 ES5 兼容 + 压缩，交给 Taro 处理，微信侧不再二次转译
  es6: false,
  enhance: false,
  minified: false,
  urlCheck: true,
  // 上传前必须开启：代码质量与体积检查
  checkSiteMap: true,
  ignoreUploadUnusedFiles: true
};

writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, 'utf8');
console.log(`[prepare] project.config.json 已更新：appid=${config.appid}, projectname=${projectname}`);

// 上线前必查项提示（不做自动校验，避免误判阻断构建）
console.log(`
[prepare] 上线前需在「微信公众平台 → 开发管理」完成：
  1. 服务器域名 → request 合法域名：https://i-home.life
  2. 业务域名（如使用 webview）：https://i-home.life
  3. 隐私保护指引：声明 openid / 手机号 / 设备信息 / 健康数据 的收集用途
  4. 服务类目：家居装修 / 家政服务（与「空间健康资产运营」口径一致）
`);
