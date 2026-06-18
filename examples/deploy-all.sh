#!/bin/bash
# ============================================================
# scsh 自动化部署脚本示例
# 文件名: examples/deploy-all.sh
# 用途: 批量部署 Profile 中定义的所有 Applet
# 用法: ./deploy-all.sh [--dry-run]
# ============================================================

set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="--dry-run"
  echo "[DRY RUN] 仅预览，不执行实际操作"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo " scsh 自动化部署脚本"
echo " 项目目录: $PROJECT_DIR"
echo " 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# --- 检查依赖 ---
if ! command -v python3 &>/dev/null; then
  echo "❌ 未找到 python3，请先安装 Python 3.10+"
  exit 1
fi

if [[ ! -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
  echo "⚠️  未找到虚拟环境，使用系统 Python"
  PYTHON="python3"
else
  source "$PROJECT_DIR/.venv/bin/activate"
  PYTHON="$PROJECT_DIR/.venv/bin/python3"
fi

# --- 启动 scsh 并执行部署 ---
echo ""
echo "[1/4] 检查读卡器..."
$PYTHON -m scsh <<EOF
session readers
EOF

echo ""
echo "[2/4] 连接卡片..."
$PYTHON -m scsh <<EOF
session connect 1
card info
EOF

echo ""
echo "[3/4] 预览部署计划..."
$PYTHON -m scsh <<EOF
deploy plan
EOF

if [[ -z "$DRY_RUN" ]]; then
  echo ""
  echo "[4/4] 执行部署..."
  $PYTHON -m scsh <<EOF
deploy provision --step
EOF
else
  echo ""
  echo "[4/4] 跳过执行 (DRY RUN)"
fi

echo ""
echo "=========================================="
echo " 部署完成！"
echo "=========================================="
echo ""
echo "查看卡片状态："
echo "  $PYTHON -m scsh"
echo "  >>> card list"
echo ""
