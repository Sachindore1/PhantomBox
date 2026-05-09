@echo off
echo ============================================================
echo 🧹 PhantomBox Complete Cleanup
echo ============================================================

cd /d %~dp0..

echo.
echo ⚠️  This will DELETE:
echo    • All test files from storage nodes
echo    • All MySQL test data (audit logs, file registry, etc.)
echo    • Admin users will be preserved
echo.

set /p confirm="Continue? (y/N): "
if /i not "%confirm%"=="y" (
    echo ❌ Cancelled.
    exit /b 1
)

REM 1. Clear storage nodes
echo.
echo 📦 Step 1: Clearing storage nodes...
python scripts/clear_storage_nodes.py

REM 2. Clear MySQL data
echo.
echo 🗄️  Step 2: Clearing MySQL database...
python scripts/clear_mysql_data.py

REM 3. Optional: Restart services
echo.
set /p restart="Restart all PhantomBox services? (y/N): "
if /i "%restart%"=="y" (
    echo 🔄 Restarting services...
    
    REM Kill existing processes
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq genesis*" 2>nul
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq peer*" 2>nul
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq noise*" 2>nul
    
    REM Start new processes
    start "genesis" python phantomnet/node.py genesis 5001 genesis
    timeout /t 2 /nobreak >nul
    start "peer" python phantomnet/node.py peer 5002 http://localhost:5001
    timeout /t 2 /nobreak >nul
    start "noiseA" python phantombox/adapters/noise_node_A.py
    start "noiseB" python phantombox/adapters/noise_node_B.py
    timeout /t 2 /nobreak >nul
    start "phantombox" python phantombox/app.py
    
    echo    Services started in new windows
)

echo.
echo ============================================================
echo ✅ Cleanup complete!
echo.
echo 💡 Next steps:
echo    1. Start PhantomBox: python phantombox/app.py
echo    2. Visit: http://localhost:8000/auth
echo    3. Login: admin@phantombox.local / Admin@2024
echo ============================================================
pause