@echo off
echo Starting PhantomNet Genesis Node...
cd /d %~dp0..
python phantomnet/node.py genesis 5001 genesis
echo Genesis node started on http://localhost:5001
pause