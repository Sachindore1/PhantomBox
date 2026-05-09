@echo off
echo Starting PhantomBox Application...
cd /d %~dp0..
python phantombox/app.py
echo PhantomBox started on http://localhost:8000
pause