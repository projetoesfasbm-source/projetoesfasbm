@echo off
title SisGEn - Ambiente de Desenvolvimento
color 0B

:: Pega o caminho exato de onde este arquivo .bat esta rodando
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo ===================================================
echo      INICIANDO AUTOMACAO DO SISGEN...
echo ===================================================
echo.

:: MÁGICA DA BLINDAGEM: Restaura sua conexao local por cima da producao
if exist ".env.local" (
    echo [+] Restaurando configuracoes locais ^(.env.local --^> .env^)...
    copy /Y .env.local .env >nul
) else (
    echo [!] Arquivo .env.local nao encontrado. Crie para blindar sua conexao!
)

:: Verifica se o ambiente virtual existe. Se nao existir, cria do zero.
if not exist "venv\Scripts\activate.bat" (
    echo [!] Ambiente virtual nao encontrado.
    echo [+] Criando novo ambiente virtual ^(venv^)...
    python -m venv venv
    
    echo [+] Ativando ambiente e instalando dependencias...
    call venv\Scripts\activate.bat
    
    if exist "requirements.txt" (
        pip install -r requirements.txt
        echo [+] Dependencias instaladas com sucesso!
    )
) else (
    echo [+] Ambiente virtual encontrado. Ativando...
    call venv\Scripts\activate.bat
)

echo.
echo [+] Subindo o servidor Flask...
echo ===================================================

:: Inicia o flask 
flask run --debug

pause