@echo off
REM ============================================
REM  StyleCorrector — Inicio con Docker Compose
REM ============================================

echo.
echo ========================================
echo   StyleCorrector — Inicio del sistema
echo ========================================
echo.

REM Verificar que Docker Desktop esta corriendo
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop no esta corriendo.
    echo.
    echo Pasos para iniciar:
    echo   1. Reinicia el PC (necesario despues de instalar Docker Desktop)
    echo   2. Abre Docker Desktop desde el menu de inicio
    echo   3. Espera a que el icono de Docker en la barra de tareas diga "Docker Desktop is running"
    echo   4. Ejecuta este script de nuevo
    echo.
    echo NOTA: Si tienes problemas de virtualizacion:
    echo   - Reinicia el PC y entra al BIOS (F2, F10, DEL segun tu placa)
    echo   - Activa "Intel VT-x" o "AMD-V" en la seccion de CPU/Virtualizacion
    echo   - Guarda y reinicia
    echo.
    pause
    exit /b 1
)

echo [OK] Docker Desktop detectado.
echo.

REM Construir e iniciar todos los servicios
echo Construyendo e iniciando servicios...
echo (Esto puede tardar varios minutos la primera vez)
echo.

cd /d "%~dp0"
docker compose up --build -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Fallo al iniciar los servicios.
    echo Revisa los logs con: docker compose logs
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Servicios iniciados correctamente!
echo ========================================
echo.
echo   Frontend:     http://localhost:3000
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
echo.
echo   Para ver logs:     docker compose logs -f
echo   Para detener:      docker compose down
echo   Para reiniciar:    docker compose restart
echo.
echo Esperando a que todos los servicios esten listos...
echo (LanguageTool puede tardar ~60 segundos en iniciar)
echo.

REM Esperar a que el backend responda
:wait_backend
timeout /t 5 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo   Esperando al backend...
    goto wait_backend
)

echo.
echo [OK] Backend listo!
echo [OK] Abre http://localhost:3000 en tu navegador.
echo.
pause
