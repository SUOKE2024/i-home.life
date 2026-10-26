#!/usr/bin/env bash
# deploy-remote.sh 发布门禁行为验证（T1-5）
#
# 为什么需要这个测试：门禁脚本一旦写错，故障时的"回滚"可能只是把坏代码再启一次
# （这正是 2026-10-24 修复前的缺陷）。该缺陷无法在本地靠读代码发现，必须用
# 桩替身跑一遍分支。
#
# 做法：用假 ssh / rsync / curl 替换远端交互，验证三种场景：
#   1. 配置预检失败 → **不得重启**，退出码非 0
#   2. 健康探针失败 → 触发 rollback_code（日志出现 ROLLBACK），退出码非 0
#   3. 全绿 → 退出码 0
#
# 用法：bash scripts/tests/test_deploy_gate.sh
# 退出码：0 = 三场景全部符合预期
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SH="$SCRIPT_DIR/../deploy-remote.sh"

WORK="$(mktemp -d)"
STUB_BIN="$WORK/bin"
STUB_LOG="$WORK/calls.log"
mkdir -p "$STUB_BIN"
PASS=0
FAIL=0

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

ok()   { echo "  ✓ $*"; PASS=$((PASS + 1)); }
bad()  { echo "  ✗ $*"; FAIL=$((FAIL + 1)); }

# ── 桩：ssh ────────────────────────────────────────────────────────────────
cat > "$STUB_BIN/ssh" <<'STUB'
#!/usr/bin/env bash
# 记录调用；按场景返回退出码
cmdline="$*"
if [ -t 0 ]; then stdin_data=""; else stdin_data="$(cat)"; fi

case "$cmdline" in
  *get_settings*)
    echo "SSH:config-precheck" >> "$STUB_LOG"
    exit "${STUB_CONFIG_RC:-0}"
    ;;
  *"systemctl restart ihome"*)
    echo "SSH:restart" >> "$STUB_LOG"
    exit "${STUB_RESTART_RC:-0}"
    ;;
  *"bash -s"*)
    # 远端脚本（快照 / 回滚 / 依赖安装）
    if echo "$stdin_data" | grep -q -e "rollback" -e "回滚代码"; then
      echo "SSH:rollback-script" >> "$STUB_LOG"
    elif echo "$stdin_data" | grep -q "code-pre"; then
      echo "SSH:snapshot-script" >> "$STUB_LOG"
    else
      echo "SSH:remote-script" >> "$STUB_LOG"
    fi
    exit "${STUB_SCRIPT_RC:-0}"
    ;;
  *"curl"*"/health"*)
    echo "SSH:probe" >> "$STUB_LOG"
    exit "${STUB_HEALTH_RC:-0}"
    ;;
  *"cp -a .env"*)
    echo "SSH:env-backup" >> "$STUB_LOG"
    exit 0
    ;;
  *)
    echo "SSH:other" >> "$STUB_LOG"
    exit 0
    ;;
esac
STUB

# ── 桩：rsync / curl（门禁路径上不该用到，出现即记录） ─────────────────────
cat > "$STUB_BIN/rsync" <<'STUB'
#!/usr/bin/env bash
echo "RSYNC:$*" >> "$STUB_LOG"
exit 0
STUB
cat > "$STUB_BIN/curl" <<'STUB'
#!/usr/bin/env bash
echo "CURL:$*" >> "$STUB_LOG"
exit "${STUB_HEALTH_RC:-0}"
STUB
chmod +x "$STUB_BIN/ssh" "$STUB_BIN/rsync" "$STUB_BIN/curl"

export STUB_LOG
export PATH="$STUB_BIN:$PATH"

# 载入函数（用非法子命令避免执行真实部署分支）。
# 注意：deploy-remote.sh 顶部有 `set -e`，source 后会传播到本脚本，
# 因此必须显式关闭 errexit，否则断言里的"失败分支"会把测试自身打死。
# shellcheck disable=SC1090
source "$DEPLOY_SH" __load_only__ >/dev/null 2>&1 || true
set +e +u

run_gate() {
  : > "$STUB_LOG"
  ( restart_gate ) >"$WORK/out.txt" 2>&1
  echo $?
}

echo "── 场景 1：配置预检失败（坏配置应被拦在重启之前）"
RC=$(STUB_CONFIG_RC=1 run_gate)
if [ "$RC" != "0" ]; then ok "退出码非 0（${RC}）"; else bad "退出码为 0，门禁未拦截"; fi
if grep -q "SSH:restart" "$STUB_LOG"; then
  bad "发生了重启 —— 坏配置应在重启前被拦"
else
  ok "未触发重启"
fi
if grep -q "配置预检失败" "$WORK/out.txt"; then ok "输出提示清晰"; else bad "缺少失败提示"; fi

echo
echo "── 场景 2：健康探针失败（应回滚代码而非原地重启）"
RC=$(STUB_HEALTH_RC=1 run_gate)
if [ "$RC" != "0" ]; then ok "退出码非 0（${RC}）"; else bad "退出码为 0，未阻断"; fi
if grep -q "SSH:rollback-script" "$STUB_LOG"; then
  ok "触发了回滚脚本"
else
  bad "未触发回滚（可能仍是"重启同一份坏代码"的旧缺陷）"
fi
if grep -q "SSH:restart" "$STUB_LOG"; then ok "重启与回滚均执行（回滚需重启生效）"; fi

echo
echo "── 场景 3：全绿"
RC=$(STUB_HEALTH_RC=0 run_gate)
if [ "$RC" = "0" ]; then ok "退出码 0"; else bad "正常路径退出码为 ${RC}"; fi
if grep -q "门禁通过" "$WORK/out.txt"; then ok "输出门禁通过"; else bad "缺少通过提示"; fi
if grep -q "SSH:rollback-script" "$STUB_LOG"; then bad "正常路径不应回滚"; else ok "未误触发回滚"; fi

echo
echo "── 汇总：通过 $PASS / 失败 $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
