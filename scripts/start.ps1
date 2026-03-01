# ============================================
#  StyleCorrector — Inicio con Docker Compose
# ============================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  StyleCorrector — Inicio del sistema" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que Docker Desktop esta corriendo
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Docker no responde" }
    Write-Host "[OK] Docker Desktop detectado." -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Docker Desktop no esta corriendo." -ForegroundColor Red
    Write-Host ""
    Write-Host "Pasos para iniciar:" -ForegroundColor Yellow
    Write-Host "  1. Reinicia el PC (necesario despues de instalar Docker Desktop)"
    Write-Host "  2. Abre Docker Desktop desde el menu de inicio"
    Write-Host "  3. Espera a que diga 'Docker Desktop is running'"
    Write-Host "  4. Ejecuta este script de nuevo"
    Write-Host ""
    Write-Host "Si tienes problemas de virtualizacion:" -ForegroundColor Yellow
    Write-Host "  - Reinicia y entra al BIOS (F2, F10, DEL segun tu placa)"
    Write-Host "  - Activa 'Intel VT-x' o 'AMD-V' en CPU/Virtualizacion"
    Write-Host "  - Guarda y reinicia"
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Ir al directorio del proyecto
Set-Location $PSScriptRoot\..

Write-Host ""
Write-Host "Construyendo e iniciando servicios..." -ForegroundColor Yellow
Write-Host "(Esto puede tardar varios minutos la primera vez)" -ForegroundColor DarkGray
Write-Host ""

# Construir e iniciar
docker compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Fallo al iniciar los servicios." -ForegroundColor Red
    Write-Host "Revisa los logs con: docker compose logs" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Servicios iniciados correctamente!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:      " -NoNewline; Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend API:   " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:      " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  MinIO Console: " -NoNewline; Write-Host "http://localhost:9001" -ForegroundColor Cyan
Write-Host "    (user: minioadmin / pass: minioadmin)"
Write-Host ""
Write-Host "  Para ver logs:   docker compose logs -f"
Write-Host "  Para detener:    docker compose down"
Write-Host "  Para reiniciar:  docker compose restart"
Write-Host ""
Write-Host "Esperando a que todos los servicios esten listos..." -ForegroundColor Yellow
Write-Host "(LanguageTool puede tardar ~60 segundos en iniciar)" -ForegroundColor DarkGray
Write-Host ""

# Esperar a que el backend responda
$maxWait = 120  # segundos
$elapsed = 0
while ($elapsed -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            break
        }
    }
    catch {
        # Backend aun no listo
    }
    Write-Host "  Esperando al backend... ($elapsed s)" -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
    $elapsed += 5
}

if ($elapsed -ge $maxWait) {
    Write-Host ""
    Write-Host "[AVISO] El backend tarda mas de lo esperado." -ForegroundColor Yellow
    Write-Host "Revisa con: docker compose logs backend" -ForegroundColor Yellow
}
else {
    Write-Host ""
    Write-Host "[OK] Backend listo!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Abre http://localhost:3000 en tu navegador." -ForegroundColor Green
Write-Host ""

# Abrir navegador automaticamente
Start-Process "http://localhost:3000"

Read-Host "Presiona Enter para salir (los servicios seguiran corriendo)"
