@echo off
echo Starting Noise Storage Nodes...
cd /d %~dp0..
start python phantombox/adapters/noise_node_A.py
timeout /t 2
start python phantombox/adapters/noise_node_B.py
echo Noise nodes started on http://localhost:9001 and http://localhost:9002
pause