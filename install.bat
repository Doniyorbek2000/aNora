@echo off
title NORA Premium Installer
color 0B

echo ====================================================================
echo                   NORA AI - PREMIUM AGENT INSTALLER                 
echo ====================================================================
echo.
echo [*] Tizim muhitini tekshirilmoqda...

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [X] Xato: Python o'rnatilmagan!
    echo Iltimos, Python-ni o'rnating va PATH-ga qo'shing.
    echo Yuklab olish: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Virtual environment creation
if not exist ".venv" (
    echo [*] Yangi virtual muhit yaratilmoqda (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        color 0C
        echo [X] Xato: Virtual muhit yaratib bo'lmadi!
        pause
        exit /b 1
    )
    echo [OK] Virtual muhit muvaffaqiyatli yaratildi.
) else (
    echo [OK] Virtual muhit (.venv) allaqachon mavjud.
)

:: Activate virtual environment and install requirements
echo [*] Virtual muhit faollashtirilmoqda va kutubxonalar o'rnatilmoqda...
call .venv\Scripts\activate.bat

echo [*] Pip yangilanmoqda...
python -m pip install --upgrade pip

echo [*] requirements.txt kutubxonalari o'rnatilmoqda...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo [X] Xato: Kutubxonalarni o'rnatishda xatolik yuz berdi!
    pause
    exit /b 1
)
echo [OK] Barcha kutubxonalar muvaffaqiyatli o'rnatildi.

:: Setup startup
echo [*] Avtomatik ishga tushish sozlamalari (Windows Startup) faollashtirilmoqda...
python setup_startup.py
if %errorlevel% neq 0 (
    echo [!] Ogohlantirish: Avtomatik ishga tushishni sozlab bo'lmadi, lekin dastur o'rnatildi.
)

color 0A
echo.
echo ====================================================================
echo    NORA PREMIUM SOZLAMALARI MUVAFFAQIYATLI YAKUNLANDI!               
echo ====================================================================
echo.
echo [*] Har safar kompyuteringiz yonganda NORA avtomatik orqa fonda faollashadi.
echo [*] Cloud boshqaruv paneli: web_server.py (FastAPI) Alwaysdata-ga yuklashga tayyor.
echo [*] NORA-ni hoziroq ishga tushirish...
echo.
pause

start "" ".venv\Scripts\pythonw.exe" "main.py"
exit /b 0
