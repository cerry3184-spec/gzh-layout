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
echo   3. 注入秀米（演练：只看，不保存）
echo ==========================================
echo.
echo 会弹出浏览器窗口，把排版灌进秀米编辑器。
echo 不会保存，看完直接关掉浏览器即可。
echo.
pause

"%PY%" build_gonggao.py --inject
echo.
pause
