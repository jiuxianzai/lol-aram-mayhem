# lol-aram-mayhem · Windows 安装自检
#
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1         # 只做命令行自检
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Web    # 顺带安装网页依赖
#
param(
  [switch]$Web,
  [switch]$SkipCheck
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "== lol-aram-mayhem 安装自检 ==" -ForegroundColor Cyan
Write-Host "目录: $root"
Write-Host ""

# ---------- Python ----------
$py = $null
foreach ($cand in @(@('py', '-3'), @('python', $null), @('python3', $null))) {
  $exe = $cand[0]
  $pre = $cand[1]
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
  $args = if ($pre) { @($pre, '-c', 'import sys;print(sys.version_info[0]*100+sys.version_info[1])') } else { @('-c', 'import sys;print(sys.version_info[0]*100+sys.version_info[1])') }
  try {
    $out = & $exe @args 2>$null
    if ($LASTEXITCODE -eq 0 -and [int]$out -ge 310) {
      $py = @($exe) + $(if ($pre) { @($pre) } else { @() })
      Write-Host "[OK] Python: $exe $pre (3.10+)" -ForegroundColor Green
      break
    }
  } catch { }
}

if (-not $py) {
  Write-Host "[X] 没找到 Python 3.10+" -ForegroundColor Red
  Write-Host "    去 https://www.python.org/downloads/windows/ 装一个，安装时勾选 'Add python.exe to PATH'"
  Write-Host "    或者：winget install --id Python.Python.3.12 -e"
  exit 1
}

$pyExe = $py[0]
$pyArgs = @()
if ($py.Length -gt 1) { $pyArgs = @($py[1..($py.Length - 1)]) }

# ---------- 数据文件 ----------
$dbPtr = Join-Path $root 'data\current.json'
if (-not (Test-Path $dbPtr)) {
  Write-Host "[X] 缺少 data\current.json，仓库不完整" -ForegroundColor Red
  exit 1
}

$current = Get-Content $dbPtr -Raw | ConvertFrom-Json
$dbFile = Join-Path $root ("data\" + ($current.db -replace '/', '\'))
if (-not (Test-Path $dbFile)) {
  Write-Host "[X] 缺少数据库文件: $dbFile" -ForegroundColor Red
  exit 1
}
Write-Host "[OK] 数据库: $($current.db)" -ForegroundColor Green

# ---------- 跑一次 status ----------
if (-not $SkipCheck) {
  Write-Host ""
  Write-Host "-- 运行 scripts\lol.py status --"
  & $pyExe @pyArgs 'scripts\lol.py' 'status'
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] status 执行失败" -ForegroundColor Red
    exit 1
  }
  Write-Host ""
  Write-Host "-- 试解析一个英雄（狐狸）--"
  & $pyExe @pyArgs 'scripts\lol.py' 'resolve' '狐狸'
}

# ---------- 网页（可选） ----------
if ($Web) {
  Write-Host ""
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[X] 没找到 npm，先装 Node.js 20+：winget install --id OpenJS.NodeJS.LTS -e" -ForegroundColor Red
    exit 1
  }
  Push-Location (Join-Path $root 'web')
  try {
    Write-Host "-- npm install（第一次会下载依赖，约 1-2 分钟）--"
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
    Write-Host "[OK] 网页依赖已安装" -ForegroundColor Green
    Write-Host "    启动：cd web; npm run dev   →  http://127.0.0.1:5178/"
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "完成。常用命令（Windows 用 python，不用 python3）：" -ForegroundColor Cyan
Write-Host "  python scripts\lol.py report `"Ahri`" --styles all"
Write-Host "  cd web; npm run dev"
Write-Host ""
