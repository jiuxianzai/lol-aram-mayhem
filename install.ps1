# lol-aram-mayhem · Windows 安装自检
#
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1          # 只做命令行自检
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Web     # 顺带安装网页依赖
#
param(
  [switch]$Web
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 让 Python 统一用 UTF-8 输出，避免中文在 cp437 控制台报错
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host ""
Write-Host "== lol-aram-mayhem 安装自检 ==" -ForegroundColor Cyan
Write-Host "目录: $root"
Write-Host ""

# ---------- 找到 Python 3.10+ ----------
$pyExe = $null
$pyPrefix = @()
$candidates = @(
  @{ Exe = 'py';      Prefix = @('-3') },
  @{ Exe = 'python';  Prefix = @() },
  @{ Exe = 'python3'; Prefix = @() }
)

foreach ($c in $candidates) {
  if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
  $probeArgs = @($c.Prefix) + @('-c', 'import sys;print(sys.version_info[0]*100+sys.version_info[1])')
  try {
    $out = & $c.Exe @probeArgs 2>$null
    $code = $LASTEXITCODE
    $ver = 0
    if ($code -eq 0 -and $out) {
      $last = @($out)[-1]
      [void][int]::TryParse(([string]$last).Trim(), [ref]$ver)
    }
    if ($ver -ge 310) {
      $pyExe = $c.Exe
      $pyPrefix = @($c.Prefix)
      Write-Host ("[OK] Python: {0} {1} (>=3.10)" -f $c.Exe, ($c.Prefix -join ' ')) -ForegroundColor Green
      break
    }
  } catch { }
}

if (-not $pyExe) {
  Write-Host "[X] 没找到 Python 3.10+" -ForegroundColor Red
  Write-Host "    安装：winget install --id Python.Python.3.12 -e"
  Write-Host "    或 https://www.python.org/downloads/windows/ （勾选 Add python.exe to PATH）"
  exit 1
}

$pyOk = @($pyPrefix) + @('scripts\lol.py', 'status')

# ---------- 数据文件检查 ----------
$ptr = Join-Path $root 'data\current.json'
if (-not (Test-Path $ptr)) {
  Write-Host "[X] 缺少 data\current.json，仓库不完整" -ForegroundColor Red
  exit 1
}
$current = Get-Content $ptr -Raw -Encoding UTF8 | ConvertFrom-Json
$dbRel = [string]$current.db
$dbPath = Join-Path $root ('data\' + ($dbRel -replace '/', '\'))
if (-not (Test-Path $dbPath)) {
  Write-Host "[X] 缺少数据库文件: $dbPath" -ForegroundColor Red
  exit 1
}
Write-Host "[OK] 数据库: data\$($dbRel -replace '/', '\')" -ForegroundColor Green

# ---------- 跑一次 status + resolve ----------
Write-Host ""
Write-Host "-- scripts\lol.py status --"
& $pyExe @pyOk
if ($LASTEXITCODE -ne 0) {
  Write-Host "[X] status 执行失败（看上面的报错）" -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "-- 试解析一个英雄（狐狸）--"
& $pyExe @($pyPrefix) @('scripts\lol.py', 'resolve', '狐狸')
if ($LASTEXITCODE -ne 0) {
  Write-Host "[!] resolve 返回非 0，通常是控制台编码问题，可先执行：chcp 65001" -ForegroundColor Yellow
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
    Write-Host "-- npm install（首次约 1-2 分钟）--"
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
    Write-Host "[OK] 网页依赖已安装" -ForegroundColor Green
  } finally {
    Pop-Location
  }
  Write-Host "    启动网页：cd web; npm run dev   ->  http://127.0.0.1:5178/"
}

Write-Host ""
Write-Host "完成。常用命令（Windows 用 python，不用 python3）：" -ForegroundColor Cyan
Write-Host '  python scripts\lol.py report "Ahri" --styles all'
Write-Host "  cd web; npm run dev"
Write-Host ""
