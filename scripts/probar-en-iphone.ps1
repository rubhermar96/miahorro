<#
.SYNOPSIS
  Arranca MiAhorro en local y lo publica temporalmente por HTTPS (túnel rápido de Cloudflare)
  para probarlo en el iPhone con Face ID.

.DESCRIPTION
  1. Si Docker no responde, reinicia Docker Desktop (ver Repair-DockerDesktop).
  2. Construye y arranca la plataforma (docker compose).
  3. Abre el túnel y reinicia la API en modo producción con la dirección del túnel.
  4. Muestra la dirección para abrirla en el iPhone.
  Pulsa Ctrl+C para terminar: cierra el túnel y deja la API otra vez en modo local.

  Uso:  powershell -ExecutionPolicy Bypass -File .\scripts\probar-en-iphone.ps1
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not (Test-Path $cloudflared)) {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $command) {
        throw 'Falta cloudflared. Instálalo con: winget install Cloudflare.cloudflared'
    }
    $cloudflared = $command.Source
}

function Test-DockerEngine {
    # `docker version` hangs forever when Docker Desktop died half-way: 15 seconds at most.
    $process = Start-Process -FilePath 'cmd.exe' -NoNewWindow -PassThru `
        -ArgumentList '/c', 'docker version --format {{.Server.Version}} >nul 2>&1'
    if (-not $process.WaitForExit(15000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Get-Process docker -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        return $false
    }
    return ($process.ExitCode -eq 0)
}

function Repair-DockerDesktop {
    # Workaround for a Docker Desktop bug on Windows: after a restart it cannot delete its old
    # AF_UNIX socket files ("El sistema no tiene acceso al archivo") and stops. Renaming the
    # folders that hold them lets it start cleanly; it recreates them.
    Write-Host 'Docker no responde: reiniciando Docker Desktop...'
    # Every Docker process: one left running recreates the locked files before the restart.
    Get-Process | Where-Object { $_.ProcessName -match 'docker' } | Stop-Process -Force -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 10 -and (Get-Process | Where-Object { $_.ProcessName -match 'docker' }); $i++) {
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 2
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    foreach ($dir in @("$env:LOCALAPPDATA\Docker\run", "$env:LOCALAPPDATA\docker-secrets-engine")) {
        if (Test-Path $dir) {
            Rename-Item -LiteralPath $dir -NewName ((Split-Path $dir -Leaf) + '.old-' + $stamp)
        }
    }
    Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        if (Test-DockerEngine) {
            Write-Host 'Docker listo.'
            return
        }
    }
    throw 'Docker Desktop no arranca. Ábrelo y mira si muestra algún aviso.'
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Ha fallado: docker compose $Arguments"
    }
}

if (-not (Test-DockerEngine)) {
    Repair-DockerDesktop
}

Write-Host 'Arrancando la plataforma...'
Invoke-Compose @('up', '-d', '--build', '--wait')

$log = Join-Path $env:TEMP 'miahorro-tunel.log'
Remove-Item $log -ErrorAction SilentlyContinue
$tunnel = Start-Process -FilePath $cloudflared -PassThru -NoNewWindow `
    -ArgumentList 'tunnel', '--no-autoupdate', '--url', 'http://localhost:8080' `
    -RedirectStandardError $log

try {
    Write-Host 'Abriendo el túnel...'
    $url = $null
    for ($i = 0; $i -lt 60 -and -not $url; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $log) {
            $match = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' |
                Select-Object -First 1
            if ($match) {
                $url = $match.Matches[0].Value
            }
        }
    }
    if (-not $url) {
        throw "No se ha podido abrir el túnel. Detalles en $log"
    }

    # Passkeys are bound to the address, and production mode uses secure cookies like the VPS.
    $env:MIAHORRO_ENVIRONMENT = 'production'
    $env:MIAHORRO_PUBLIC_URL = $url
    Invoke-Compose @('up', '-d', '--wait', 'api')

    Write-Host 'Esperando a que Cloudflare publique la dirección...'
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $health = Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 10
            if ($health.StatusCode -eq 200) {
                break
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }

    Write-Host ''
    Write-Host "  Abre en el iPhone:  $url" -ForegroundColor Green
    Write-Host ''
    Write-Host 'Deja esta ventana abierta mientras pruebas. Ctrl+C para terminar.'
    Wait-Process -Id $tunnel.Id
}
finally {
    if (-not $tunnel.HasExited) {
        Stop-Process -Id $tunnel.Id -Force
    }
    Remove-Item Env:MIAHORRO_ENVIRONMENT, Env:MIAHORRO_PUBLIC_URL -ErrorAction SilentlyContinue
    Write-Host 'Túnel cerrado. Volviendo a la configuración local...'
    & docker compose up -d --wait api
}
