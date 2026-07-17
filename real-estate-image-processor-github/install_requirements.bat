@echo off
chcp 65001 >nul
cd /d %~dp0

echo ========================================
echo Real Estate Image Processor - Install
echo ========================================
echo.

echo [1/2] pip を更新します...
py -m pip install --upgrade pip

echo.
echo [2/2] 必要ライブラリをインストールします...
py -m pip install -r requirements.txt

echo.
echo 完了しました。
echo opencv-python のインストールに失敗する場合は、Python 3.12 または 3.13 を試してください。
pause
