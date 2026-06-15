#!/usr/bin/env bash
set -euo pipefail

# download-isoapplet.sh — 将 IsoApplet 下载安装到智能卡
#
# 用法:
#   ./download-isoapplet.sh                              # 默认密钥 + 自动检测 ISD
#   ./download-isoapplet.sh <GP密钥HEX>                  # 指定密钥
#   ./download-isoapplet.sh <ISD_AID> <密钥>             # 指定 ISD AID + 密钥
#   ./download-isoapplet.sh --key-ver <N> <ISD_AID> <密钥>  # 指定密钥版本
#   ./download-isoapplet.sh --help                       # 帮助

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CAP_FILE="$(cd "$SCRIPT_DIR/../IsoApplet" && pwd)/IsoApplet.cap"
GP_JAR="$SCRIPT_DIR/tools/gp.jar"
PACKAGE_AID="F276A288BCFBA69D34F310"
APPLET_AID="F276A288BCFBA69D34F31001"

# ---- 参数解析 ----
ISD_AID=""
KEY="404142434445464748494A4B4C4D4E4F"
KEY_VER=""
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --key-ver)
      KEY_VER="$2"
      EXTRA+=("--key-ver" "$2")
      shift 2 ;;
    --help|-h)
      echo "用法: $0 [<GP密钥HEX>]"
      echo "  或: $0 [<ISD_AID> <GP密钥HEX>]"
      echo "  或: $0 --key-ver <版本> [<ISD_AID> <GP密钥HEX>]"
      echo ""
      echo "默认 ISD AID: A000000003000000 (NXP JCOP 2.x)"
      echo "默认密钥:    404142434445464748494A4B4C4D4E4F"
      echo ""
      echo "常见 ISD AID:"
      echo "  A000000003000000  — NXP JCOP 2.x"
      echo "  A000000151000000  — NXP JCOP 3/4"
      echo ""
      echo "示例:"
      echo "  $0                                          # 默认"
      echo "  $0 00112233445566778899AABBCCDDEEFF         # 自定义密钥"
      echo "  $0 A000000151000000 404142...               # JCOP 3/4"
      echo "  $0 --key-ver 32 A000000151000000 404142...  # JCOP 3/4 密钥版本 32"
      exit 0 ;;
    *)
      if [ -z "$ISD_AID" ]; then
        ISD_AID="$1"
      elif [ "$KEY" == "404142434445464748494A4B4C4D4E4F" ]; then
        KEY="$1"
      fi
      shift ;;
  esac
done

# 默认 ISD AID (JCOP 2.x)
if [ -z "$ISD_AID" ]; then
  ISD_AID="A000000003000000"
fi

# ---- 环境检查 ----
if [ ! -f "$CAP_FILE" ]; then
  echo "错误: 找不到 CAP 文件: $CAP_FILE" >&2
  echo "请先编译 IsoApplet: cd $SCRIPT_DIR/../IsoApplet && ant" >&2
  exit 1
fi

if [ ! -f "$GP_JAR" ]; then
  echo "错误: 找不到 gp.jar: $GP_JAR" >&2
  exit 1
fi

if ! command -v java &>/dev/null; then
  echo "错误: 未找到 Java，请安装 JDK 8+" >&2
  exit 1
fi

# ---- GP 命令函数 ----
gp() {
  local GP_OPTS=""
  if java -version 2>&1 | head -1 | grep -qE '^(openjdk|java) version "2[1-9]'; then
    GP_OPTS="--enable-native-access=ALL-UNNAMED"
  fi
  java $GP_OPTS -jar "$GP_JAR" "$@"
}

# ---- 打印参数 ----
echo "============================================"
echo " IsoApplet 安装脚本"
echo "============================================"
echo " CAP 文件:    $CAP_FILE"
echo " ISD AID:     $ISD_AID"
echo " GP 密钥:     ${KEY:0:16}...${KEY: -16}"
[ -n "$KEY_VER" ] && echo " 密钥版本:    $KEY_VER"
echo " Package AID: $PACKAGE_AID"
echo " Applet AID:  $APPLET_AID"
echo "--------------------------------------------"

# ---- 1. 检测卡片 ----
echo ""
echo ">>> [1/3] 扫描读卡器和卡片..."
gp --list 2>&1 || {
  echo "错误: 卡片检测失败。请确认读卡器已连接、卡片已插入。" >&2
  exit 1
}

# ---- 2. 连接并建立安全通道 ----
CONNECT_ARGS=("--connect" "$ISD_AID" "--key" "$KEY")
if [ -n "$KEY_VER" ]; then
  CONNECT_ARGS+=("--key-ver" "$KEY_VER")
fi

echo ""
echo ">>> [2/3] 建立 GP 安全通道 (${ISD_AID})..."
gp "${CONNECT_ARGS[@]}" --info 2>&1 || {
  echo ""
  echo "错误: 无法建立安全通道。可能原因:" >&2
  echo "  - ISD AID 不正确（常用: A000000003000000 / A000000151000000）" >&2
  echo "  - GP 密钥不正确" >&2
  echo "  - 密钥版本不对（JCOP 3/4 可能需要 --key-ver 32）" >&2
  echo "  - 请先运行: gp --list 查看卡片支持的参数" >&2
  exit 1
}

# ---- 3. 加载并安装 ----
INSTALL_ARGS=("${CONNECT_ARGS[@]}")
INSTALL_ARGS+=("--load" "$CAP_FILE")
INSTALL_ARGS+=("--install" "$CAP_FILE")
INSTALL_ARGS+=("--applet" "$APPLET_AID")
INSTALL_ARGS+=("--create")
INSTALL_ARGS+=("-v")

echo ""
echo ">>> [3/3] 加载 CAP 并安装 Applet..."
echo "  命令: gp --load IsoApplet.cap --install ..."
gp "${INSTALL_ARGS[@]}" 2>&1

# ---- 验证 ----
echo ""
echo "--------------------------------------------"
echo " 验证安装结果..."
echo "--------------------------------------------"
gp --list 2>&1

echo ""
if gp --list 2>&1 | grep -q "$APPLET_AID"; then
  echo "============================================"
  echo " ✓ IsoApplet 安装成功!"
  echo "   Applet:  $APPLET_AID"
  echo "   Package: $PACKAGE_AID"
  echo "============================================"
  echo ""
  echo "首次使用需要初始化 PUK 和 PIN:"
  echo "  cd $SCRIPT_DIR && ./scshr"
  echo "  scsh> select $APPLET_AID"
  echo "  scsh> send 00 24 01 02 10 <16字节PUK>"
  echo "  scsh> send 00 24 01 01 08 <8字节PIN>"
else
  echo "============================================"
  echo " ✗ 安装似乎未成功，请检查上方输出" >&2
  echo "============================================"
  exit 1
fi
