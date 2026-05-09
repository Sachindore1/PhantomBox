@echo off
echo Starting PhantomBox System...
echo.

echo 1. Starting Genesis Node (Port 5001)...
start cmd /k "cd phantomnet && python node.py genesis 5001 genesis"
timeout /t 3

echo 2. Starting Peer Node (Port 5002)...
start cmd /k "cd phantomnet && python node.py peer 5002 http://127.0.0.1:5001"
timeout /t 3

echo 3. Starting Noise Node A (Port 9001)...
start cmd /k "cd phantombox/adapters && python noise_node_A.py"
timeout /t 2

echo 4. Starting Noise Node B (Port 9002)...
start cmd /k "cd phantombox/adapters && python noise_node_B.py"
timeout /t 2

echo 5. Starting PhantomBox App (Port 8000)...
start cmd /k "cd phantombox && python app.py"
timeout /t 3

echo.
echo ✅ All components started!
echo.
echo 🌐 Access Points:
echo    PhantomBox UI: http://127.0.0.1:8000
echo    Genesis Node:  http://127.0.0.1:5001
echo    Peer Node:     http://127.0.0.1:5002
echo    Noise Node A:  http://127.0.0.1:9001
echo    Noise Node B:  http://127.0.0.1:9002
echo.
echo 📋 Test URLs:
echo    Genesis Status: http://127.0.0.1:5001/status
echo    PhantomBox:     http://127.0.0.1:8000/health
echo.
pause