@echo off
chcp 65001 >nul
title Voz Livre - Instalador
echo.
echo   ====================================
echo      Voz Livre - instalando...
echo   ====================================
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo   Python nao encontrado. Instale o Python 3.10 ou mais novo em https://www.python.org/downloads/
    echo   ^(marque a opcao "Add Python to PATH" na instalacao^) e rode este arquivo de novo.
    pause
    exit /b 1
)
echo   Instalando as bibliotecas ^(pode levar alguns minutos^)...
python -m pip install --upgrade -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo   Deu erro ao instalar as bibliotecas. Veja a mensagem acima.
    pause
    exit /b 1
)
echo.
echo   Criando atalhos na Area de Trabalho e no Menu Iniciar...
python "%~dp0criar_atalhos.py"
echo.
echo   Pronto! Abrindo o Voz Livre...
start "" pythonw "%~dp0voz_livre.py"
timeout /t 5 >nul
