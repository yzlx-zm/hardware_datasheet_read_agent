@echo off
chcp 65001 >nul
echo ========================================
echo   硬件数据手册 Agent 打包脚本
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo [1/3] 清理旧的打包文件...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo.
echo [2/3] 开始打包...
pyinstaller hw_datasheet_agent.spec --clean

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 复制配置文件到输出目录...
copy config.yaml.example dist\config.yaml.example /Y >nul

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo 输出目录: dist\
echo 主程序:   dist\hw_datasheet_agent.exe
echo.
echo 分发步骤:
echo   1. 复制 dist\hw_datasheet_agent.exe
echo   2. 复制 config.yaml.example 并重命名为 config.yaml
echo   3. 创建 input_docs 目录放入待解析文档
echo   4. 修改 config.yaml 配置大模型 API
echo.
pause
