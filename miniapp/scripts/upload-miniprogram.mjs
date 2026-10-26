#!/usr/bin/env node
/**
 * 微信小程序上传（体验版 / 正式版）。
 *
 * 前置：
 *   1. npm run build:weapp            产出 dist/
 *   2. 微信公众平台 → 开发管理 → 开发设置 → 小程序代码上传密钥，下载密钥文件
 *   3. 将开发者出口 IP 加入白名单（否则 upload 返回 80082）
 *
 * 用法：
 *   MINIPROGRAM_APP_ID=wx... \
 *   MINIPROGRAM_PRIVATE_KEY_PATH=./.secrets/private.key \
 *   node scripts/upload-miniprogram.mjs --version 1.1.0 --desc "接入生产后端与AI管家"
 *
 * 参数：
 *   --version <semver>   版本号，默认读 package.json version
 *   --desc <text>        版本描述，默认取 git 最近提交标题
 *   --robot <1-30>       机器人编号，默认 1
 */
import { execSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ci from 'miniprogram-ci';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function arg(name, fallback = '') {
  const index = process.argv.indexOf(`--${name}`);
  return index > -1 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'));
const appid = process.env.MINIPROGRAM_APP_ID || '';
const privateKeyPath = process.env.MINIPROGRAM_PRIVATE_KEY_PATH || '';
const version = arg('version', pkg.version || '1.0.0');
const robot = Number(arg('robot', '1'));

let desc = arg('desc', '');
if (!desc) {
  try {
    desc = execSync('git log -1 --pretty=%s', { cwd: root, encoding: 'utf8' }).trim();
  } catch {
    desc = `v${version}`;
  }
}

if (!appid) {
  console.error('[upload] 缺少 MINIPROGRAM_APP_ID');
  process.exit(1);
}
if (!privateKeyPath || !existsSync(resolve(root, privateKeyPath))) {
  console.error(`[upload] 缺少代码上传密钥文件：${privateKeyPath || '(未设置 MINIPROGRAM_PRIVATE_KEY_PATH)'}`);
  process.exit(1);
}
if (!existsSync(resolve(root, 'dist/app.json'))) {
  console.error('[upload] dist/app.json 不存在，请先执行 npm run build:weapp');
  process.exit(1);
}

const project = new ci.Project({
  appid,
  type: 'miniProgram',
  projectPath: resolve(root),
  privateKeyPath: resolve(root, privateKeyPath),
  ignores: ['node_modules/**/*', '.git/**/*', 'src/**/*', 'scripts/**/*', '**/*.map']
});

console.log(`[upload] appid=${appid} version=${version} robot=${robot} desc=${desc}`);

try {
  const result = await ci.upload({
    project,
    version,
    desc,
    robot,
    setting: {
      es6: true,
      es7: true,
      minify: true,
      minifyWXML: true,
      minifyWXSS: true,
      codeProtect: false,
      autoPrefixWXSS: true,
      // 上传阶段不压缩图片，避免破坏已优化资源
      minifyJS: true
    },
    onProgressUpdate: (task) => {
      if (typeof task === 'string') console.log(`  ${task}`);
    }
  });
  console.log('[upload] 上传成功', result);
  console.log(
    '[upload] 下一步：微信公众平台 → 版本管理 → 提交审核（体验版可先扫码验收）'
  );
} catch (err) {
  console.error('[upload] 上传失败', err?.message || err);
  process.exit(1);
}
