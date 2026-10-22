@echo off
chcp 936 >nul
set PYTHONUTF8=0
set PYTHONIOENCODING=gbk
cd /d "%~dp0"
set PY=C:\Users\weitian\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo [错误] 没找到可用的 Python，请先安装 Python 3.10 以上版本
  echo        下载：https://www.python.org/downloads/
  pause
  exit /b 1
)

echo ==========================================
echo   2. 检查还有哪些没填
echo ==========================================
echo.

"%PY%" build_gonggao.py --check
echo.
pause
