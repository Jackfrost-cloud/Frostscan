@echo off
title FrostScan - Disk Analyzer
color 0B
cls

echo.
echo   ===================================
echo      Frost Scan  - Disk Analyzer
echo   ===================================
echo.
echo   Verification de Python...
echo.

:: 1) py launcher (le plus fiable sur Windows, jamais un stub Store)
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 --version >nul 2>&1
    if %errorlevel%==0 (
        echo   Python detecte via py launcher.
        set PYCMD=py -3
        goto run
    )
)

:: 2) Chemins directs (bypasse le stub Microsoft Store)
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python38\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
) do (
    if exist %%P (
        echo   Python trouve : %%P
        set PYCMD=%%P
        goto run
    )
)

:: 3) python dans PATH mais on verifie que c'est pas le stub Store
where python >nul 2>&1
if %errorlevel%==0 (
    python -c "print('ok')" >nul 2>&1
    if %errorlevel%==0 (
        echo   Python detecte dans PATH.
        set PYCMD=python
        goto run
    )
)

:: Rien trouve
echo.
echo   Python introuvable (ou bloque par le Microsoft Store).
echo.
echo   Solutions :
echo   [1] Ouvrir python.org pour telecharger Python
echo   [2] Desactiver le stub Store : Parametres ^> Applications ^> Alias d'execution d'application
echo       puis desactiver "python.exe" et "python3.exe"
echo   [3] Quitter
echo.
set /p choice=   Ton choix : 
if "%choice%"=="1" ( start https://www.python.org/downloads/ )
if "%choice%"=="2" ( start ms-settings:appsfeatures )
pause
exit

:run
echo.
%PYCMD% "%~dp0frostscan.py"
if %errorlevel% neq 0 (
    echo.
    echo   Erreur au lancement.
    echo   Essaie dans un terminal : py frostscan.py
    pause
)
