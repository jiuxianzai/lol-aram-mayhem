<#
  MAYHEM LAB · 海克斯大乱斗 网页启动器（Windows）

  用法：双击 start-web.bat
  行为：启动本地服务 → 自动打开浏览器 → 关闭这个窗口即停止服务
#>
param(
  [int]$Port = 5178,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$web  = Join-Path $root 'web'
Set-Location $web

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { $Host.UI.RawUI.WindowTitle = 'MAYHEM LAB 网页 - 关闭窗口即停止服务' } catch {}

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Bad($msg)  { Write-Host "[X] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------- 环境检查
Write-Host ''
Write-Host 'MAYHEM LAB · 海克斯大乱斗' -ForegroundColor White
Write-Host "目录: $web"
Write-Host ''

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Bad '没找到 Node.js。请先安装 Node.js 20+：'
  Write-Host '    winget install --id OpenJS.NodeJS.LTS -e'
  Write-Host '    或 https://nodejs.org/zh-cn/download'
  Write-Host ''
  Read-Host '按回车退出'
  exit 1
}
$nodeVer = (& node -v) -replace '^v', ''
Write-Ok "Node.js v$nodeVer"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Bad '找到 node 但没找到 npm，建议重装 Node.js'
  Read-Host '按回车退出'
  exit 1
}

# ---------------------------------------------------------------- 依赖检查
$viteJs = Join-Path $web 'node_modules\vite\bin\vite.js'
if (-not (Test-Path $viteJs)) {
  Write-Step '首次运行，安装网页依赖（约 1-2 分钟，只需一次）'
  & npm install
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $viteJs)) {
    Write-Bad 'npm install 失败，请检查网络（国内可先执行 npm config set registry https://registry.npmmirror.com）'
    Read-Host '按回车退出'
    exit 1
  }
  Write-Ok '依赖安装完成'
}

# ---------------------------------------------------------------- 端口检查
function Get-PortOwner([int]$p) {
  try {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop
    return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
  } catch {
    $pids = @()
    foreach ($line in (netstat -ano 2>$null | Select-String "LISTENING")) {
      $cols = ($line.ToString().Trim() -split '\s+')
      if ($cols.Length -ge 5 -and $cols[1] -match ":$p$") { $pids += [int]$cols[-1] }
    }
    return @($pids | Select-Object -Unique)
  }
}

$owners = Get-PortOwner $Port
if ($owners.Count -gt 0) {
  Write-Step "端口 $Port 已被占用，先结束旧进程"
  foreach ($procId in $owners) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
      Write-Host "    结束 $($proc.ProcessName) (PID $procId)"
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep -Milliseconds 800
}

# ---------------------------------------------------------------- 启动服务
$url = "http://127.0.0.1:$Port/"

if (-not $NoBrowser) {
  $browserJob = Start-Job -ScriptBlock {
    param($p, $u)
    for ($i = 0; $i -lt 80; $i++) {
      try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $p)
        $c.Close()
        Start-Process $u
        return
      } catch { Start-Sleep -Milliseconds 350 }
    }
  } -ArgumentList $Port, $url
}

Write-Step "启动服务  $url"
Write-Host '    浏览器会自动打开；要停止服务，直接关闭这个窗口。' -ForegroundColor DarkGray
Write-Host ''

try {
  & node $viteJs --host 127.0.0.1 --port $Port --strictPort
} finally {
  if ($browserJob) {
    Stop-Job $browserJob -ErrorAction SilentlyContinue
    Remove-Job $browserJob -Force -ErrorAction SilentlyContinue
  }
  Write-Host ''
  Write-Host '服务已停止。' -ForegroundColor Yellow
}
