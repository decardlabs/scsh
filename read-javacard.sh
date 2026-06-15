#!/usr/bin/env bash
set -euo pipefail

# read-javacard.sh — 读取 Java 卡信息（默认缺省密钥）
# 自动尝试多个常见 ISD AID 和多个缺省密钥，尽可能多地读取卡片信息。
#
# 用法:
#   ./read-javacard.sh                         # 自动扫描，读取所有信息
#   ./read-javacard.sh <ISD_AID>               # 指定 ISD AID
#   ./read-javacard.sh <ISD_AID> <密钥HEX>     # 指定 ISD AID 和密钥
#   ./read-javacard.sh --help                  # 帮助

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GP_JAR="$SCRIPT_DIR/tools/gp.jar"
if [ ! -f "$GP_JAR" ];then GP_JAR="$SCRIPT_DIR/../gp.jar";fi
if [ ! -f "$GP_JAR" ];then
    GP_JAR="$(find "$SCRIPT_DIR" /usr/local /opt/homebrew ~/.local ~/tools -name gp.jar 2>/dev/null | head -1)" || true
fi

if [ ! -f "$GP_JAR" ]; then
  echo "错误: 找不到 gp.jar" >&2
  echo "请从 https://github.com/martinpaljak/GlobalPlatformPro/releases 下载" >&2
  exit 1
fi

# 缺省密钥列表（按频率排序）
DEFAULT_KEYS=(
  "404142434445464748494A4B4C4D4E4F"  # 通用开发卡
  "000102030405060708090A0B0C0D0E0F"  # 常见缺省 2
)

# 常见 ISD AID 列表（JCOP、Gemalto、Feitian 等）
COMMON_ISDS=(
  "A000000151000000"   # NXP JCOP 3/4
  "A000000003000000"   # NXP JCOP 2.x
  "A0000000030000"     # 部分老卡
  "A0000000041010"     # Gemalto IDPrime
  "A0000001674553494E" # 部分 Feitian
)

if [ "$#" -ge 1 ] && [ "$1" = "--help" -o "$1" = "-h" ]; then
    echo "用法: $0 [<ISD_AID>] [<密钥HEX>]" >&2
    echo "缺省自动尝试常见 ISD AID 和密钥组合" >&2
    exit 0
fi

if [ "$#" -ge 1 ]; then ARG_ISD="$1"; else ARG_ISD=""; fi
if [ "$#" -ge 2 ]; then ARG_KEY="$2"; else ARG_KEY=""; fi

# ---- GP 命令函数 ----
gp() {
  local GP_OPTS=""
  if java -version 2>&1 | head -1 | grep -qE 'version "2[1-9]'; then
    GP_OPTS="--enable-native-access=ALL-UNNAMED"
  fi
  java $GP_OPTS -jar "$GP_JAR" -r "JCOP" -r "ACR" -r "Identiv" -r "SCM" -r "Feitian" -r "USB" --debug 2>/dev/null "$@" || \
  java $GP_OPTS -jar "$GP_JAR" "$@"
  return $?
}

echo "============================================"
echo " Java 卡信息读取工具"
echo "============================================"
echo " gp.jar:  $GP_JAR"
echo ""

# ========================
# 第一步: 列出卡片和读卡器
# ========================
echo "┌──────────────────────────────────────────┐"
echo "│ [1/5] 扫描读卡器与卡片                    │"
echo "└──────────────────────────────────────────┘"
gp --list 2>&1
echo ""

# ========================
# 第二步: 探测 ISD AID 和密钥
# ========================
echo "┌──────────────────────────────────────────┐"
echo "│ [2/5] 探测 ISD AID 和密钥                │"
echo "└──────────────────────────────────────────┘"

ISDS_TO_TRY=()
if [ -n "$ARG_ISD" ]; then
  ISDS_TO_TRY=("$ARG_ISD")
else
  ISDS_TO_TRY=("${COMMON_ISDS[@]}")
fi

KEYS_TO_TRY=()
if [ -n "$ARG_KEY" ]; then
  KEYS_TO_TRY=("$ARG_KEY")
else
  KEYS_TO_TRY=("${DEFAULT_KEYS[@]}")
fi

FOUND_ISD=""
FOUND_KEY=""
FOUND_KEY_VER=""
for isd in "${ISDS_TO_TRY[@]}"; do
  for key in "${KEYS_TO_TRY[@]}"; do
    echo "尝试: ISD=$isd 密钥=${key:0:8}..." >&2
    for kver in "" "--key-ver 0" "--key-ver 255" "--key-ver 1" "--key-ver 32"; do
      if gp --connect "$isd" --key "$key" $kver --info &>/dev/null; then
        echo " ✓ 成功: ISD=$isd 密钥=${key:0:16}... ${kver:-}" >&2
        FOUND_ISD="$isd"
        FOUND_KEY="$key"
        FOUND_KEY_VER="$kver"
        break 3
      fi
    done
  done
done

if [ -z "$FOUND_ISD" ]; then
  echo " > 未找到可连接的安全域，以下信息将受限。" >&2
fi
echo ""

# ========================
# 第三步: 读取卡片详细信息
# ========================
if [ -n "$FOUND_ISD" ]; then
  echo "┌──────────────────────────────────────────┐"
  echo "│ [3/5] 卡片详细信息 (CPLC + 功能)          │"
  echo "└──────────────────────────────────────────┘"
  gp --connect "$FOUND_ISD" --key "$FOUND_KEY" $FOUND_KEY_VER --info 2>&1
  echo ""

  # ========================
  # 第四步: 密钥版本信息
  # ========================
  echo "┌──────────────────────────────────────────┐"
  echo "│ [4/5] 密钥信息                           │"
  echo "└──────────────────────────────────────────┘"
  gp --connect "$FOUND_ISD" --key "$FOUND_KEY" $FOUND_KEY_VER --key-info 2>&1
  echo ""

  # ========================
  # 第五步: 安全通道能力
  # ========================
  echo "┌──────────────────────────────────────────┐"
  echo "│ [5/5] 安全通道能力                       │"
  echo "└──────────────────────────────────────────┘"
  echo "[SCP] 支持的 SCP 协议:"
  gp --connect "$FOUND_ISD" --key "$FOUND_KEY" $FOUND_KEY_VER --scp-info 2>&1
  echo ""
fi

# 列出所有包/APDU 的详细清单
echo "┌──────────────────────────────────────────┐"
echo "│ 已安装内容一览                            │"
echo "└──────────────────────────────────────────┘"
gp --list 2>&1
echo ""

# 系统参数汇总
echo "┌──────────────────────────────────────────┐"
echo "│ 汇总                                     │"
echo "└──────────────────────────────────────────┘"
echo " GP JAR:              $GP_JAR"
if [ -n "$FOUND_ISD" ]; then
  echo " ISD AID:             $FOUND_ISD"
  echo " GP 密钥:             ${FOUND_KEY:0:16}...${FOUND_KEY: -16}"
  echo " 密钥版本:            ${FOUND_KEY_VER:-缺省}"
else
  echo " ISD AID:             未连接（仅列出无认证信息）"
fi
echo " gp.jar 版本:         $(gp --version 2>&1 | head -1 || echo '?')"
echo "============================================"
