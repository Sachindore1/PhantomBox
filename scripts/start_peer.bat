@echo off
echo Starting PhantomNet Peer Node...
cd /d %~dp0..
python phantomnet/node.py peer 5002 http://localhost:5001
echo Peer node started on http://localhost:5002
pause