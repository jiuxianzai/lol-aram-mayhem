#!/usr/bin/env bash
# lol-aram-mayhem · macOS / Linux 安装自检
#
#   ./install.sh          # 只做命令行自检
#   ./install.sh --web    # 顺带安装网页依赖
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

WITH_WEB=0
for arg in "$@"; do
  case "$arg" in
    --web|-w) WITH_WEB=1 ;;
    *) echo "未知参数: $arg"; exit 2 ;;
  esac
done

echo
echo "== lol-aram-mayhem 安装自检 =="
echo "目录: $ROOT"
echo

# ---------- Python ----------
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "[X] 没找到 Python 3.10+"
  echo "    macOS: brew install python@3.12   Linux: apt install python3"
  exit 1
fi
echo "[OK] Python: $($PY -V 2>&1)"

# ---------- 数据文件 ----------
if [ ! -f data/current.json ]; then
  echo "[X] 缺少 data/current.json，仓库不完整"; exit 1
fi
DB=$($PY -c "import json;print(json.load(open('data/current.json'))['db'])")
if [ ! -f "data/$DB" ]; then
  echo "[X] 缺少数据库文件: data/$DB"; exit 1
fi
echo "[OK] 数据库: data/$DB"

# ---------- status ----------
echo
echo "-- 运行 scripts/lol.py status --"
$PY scripts/lol.py status
echo
echo "-- 试解析一个英雄（狐狸）--"
$PY scripts/lol.py resolve "狐狸" || true

# ---------- 网页（可选） ----------
if [ "$WITH_WEB" = "1" ]; then
  echo
  if ! command -v npm >/dev/null 2>&1; then
    echo "[X] 没找到 npm，先装 Node.js 20+"
    exit 1
  fi
  echo "-- npm install（第一次会下载依赖）--"
  ( cd web && npm install )
  echo "[OK] 网页依赖已安装"
  echo "    启动：cd web && npm run dev   →  http://127.0.0.1:5178/"
fi

echo
echo "完成。常用命令："
echo '  python3 scripts/lol.py report "Ahri" --styles all'
echo '  cd web && npm run dev'
echo
