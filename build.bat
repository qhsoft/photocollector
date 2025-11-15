@echo off
REM Nuitka 打包示例脚本 (Windows)
REM 在运行此脚本前请在虚拟环境中安装依赖：
REM pip install -r requirements.txt
REM pip install nuitka

REM 可选：为避免控制台窗口显示，使用 --windows-console-mode=disable
python -m nuitka --standalone --onefile --enable-plugin=pyside6 --windows-console-mode=disable --windows-icon-from-ico=app_icon.ico --output-dir=dist main.py

echo 打包完成，输出在 dist 目录
pause
