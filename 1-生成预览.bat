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
echo   1. 生成排版并预览
echo ==========================================
echo.

"%PY%" build_gonggao.py
if errorlevel 1 goto fail

echo.
echo 正在用浏览器打开预览...
start "" "%~dp0layout_final.html"
echo.
echo 预览已打开。改内容就编辑 gonggao_data.json，然后重跑本文件。
pause
exit /b 0

:fail
echo.
echo [失败] 生成出错了，请把上面的报错发给我。
pause
exit /b 1
