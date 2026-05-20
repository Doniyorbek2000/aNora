import os

installer_content = """@echo off
title NORA Personal AI - O'rnatish Dasturi
color 0B

echo ==================================================
echo      NORA - SHAXSIY SUN'IY INTELLEKT TIZIMI
echo ==================================================
echo [INFO] NORA shaxsiy yordamchisini o'rnatish boshlanmoqda...
echo.

set "TARGET_DIR=%LOCALAPPDATA%\\Nora"
echo [1/4] Maqsadli papkani yaratish...
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)
if not exist "%TARGET_DIR%\\core" mkdir "%TARGET_DIR%\\core"
if not exist "%TARGET_DIR%\\config" mkdir "%TARGET_DIR%\\config"
if not exist "%TARGET_DIR%\\memory" mkdir "%TARGET_DIR%\\memory"

echo [2/4] Fayl va kutubxonalarni nusxalash...
if exist "dist\\Nora.exe" (
    copy /Y "dist\\Nora.exe" "%TARGET_DIR%\\Nora.exe" >nul
) else (
    echo [ERROR] dist\\Nora.exe topilmadi! Iltimos, oldin loyihani build qiling.
    pause
    exit /b 1
)

if exist "core\\prompt.txt" copy /Y "core\\prompt.txt" "%TARGET_DIR%\\core\\prompt.txt" >nul
if exist "config\\api_keys.json" copy /Y "config\\api_keys.json" "%TARGET_DIR%\\config\\api_keys.json" >nul
if exist "memory\\long_term.json" copy /Y "memory\\long_term.json" "%TARGET_DIR%\\memory\\long_term.json" >nul
if exist "commands.txt" copy /Y "commands.txt" "%TARGET_DIR%\\commands.txt" >nul

echo [3/4] Ishchi stolga yorliq (Shortcut) yaratish...
powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\\"$HOME\\Desktop\\NORA Personal AI.lnk\\"); $Shortcut.TargetPath = \\"$env:LOCALAPPDATA\\Nora\\Nora.exe\\"; $Shortcut.WorkingDirectory = \\"$env:LOCALAPPDATA\\Nora\\"; $Shortcut.Description = \\"NORA - Intelligent Personal Assistant\\"; $Shortcut.Save();"

echo [4/4] Avtomatik ishga tushirish ro'yxatiga qo'shish (Startup)...
powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\\"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\NoraStartup.lnk\\"); $Shortcut.TargetPath = \\"$env:LOCALAPPDATA\\Nora\\Nora.exe\\"; $Shortcut.WorkingDirectory = \\"$env:LOCALAPPDATA\\Nora\\"; $Shortcut.Save();"

echo.
echo ==================================================
echo     TABRIKLAYMIZ! NORA MUVAFFAQIYATLI O'RNATILDI!
echo ==================================================
echo [INFO] NORA shaxsiy yordamchisi quyidagi manzilda joylashgan:
echo        %TARGET_DIR%\\Nora.exe
echo.
echo [INFO] Ishchi stolingizda 'NORA Personal AI' yorlig'i yaratildi.
echo [INFO] Kompyuteringiz yoqilganda NORA avtomatik ravishda ishga tushadi.
echo.
echo Ishga tushirish uchun istalgan tugmani bosing...
pause >nul
start "" "%TARGET_DIR%\\Nora.exe"
exit
"""

# Write as plain ANSI to prevent CMD encoding issues
with open("NoraInstaller.bat", "w", encoding="ansi") as f:
    f.write(installer_content)

print("[SUCCESS] NoraInstaller.bat written successfully in ANSI format.")
