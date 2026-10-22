@echo off
rem One-click: read the game's schematic folder, render previews, commit, push.
rem Usage: double-click, or  import-schematics.cmd --no-push  /  import-schematics.cmd --src "D:\other\folder"
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

set "DEFAULT_SRC=E:\Program Files (x86)\Steam\steamapps\common\Mindustry\saves\schematics"

if "%~1"=="" (
  set "ARGS=--src "%DEFAULT_SRC%""
) else (
  set "ARGS=%*"
)

echo == 导入蓝图 ==
echo 参数: %ARGS%
echo.
where py >nul 2>nul
if errorlevel 1 (
  python "tools\import_schematics.py" %ARGS%
) else (
  py -3 "tools\import_schematics.py" %ARGS%
)

echo.
echo 退出码: %ERRORLEVEL%
pause
