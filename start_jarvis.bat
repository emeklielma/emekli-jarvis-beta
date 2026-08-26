@echo off
echo ===================================
echo Starting JARVIS - MARK XLIX
echo ===================================

echo [1/3] Starting Backend Server (server.py)...
start /min "JARVIS Backend" cmd /k "python server.py"

echo [2/3] Starting Frontend Dev Server (Vite)...
start /min "JARVIS Frontend" cmd /k "cd frontend && npm run dev"

echo Waiting 5 seconds for servers to initialize...
timeout /t 5 /nobreak >nul

echo [3/3] Launching JARVIS App Window...
start "JARVIS UI" cmd /c "python jarvis_app.py"

echo All services started! You can close this terminal.
exit
