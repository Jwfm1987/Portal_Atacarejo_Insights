@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Atacarejo Insights Portal - V15 - USUARIOS E PERFIS - 5070
cd /d "%~dp0"

if not exist logs mkdir logs
set LOGFILE=%CD%\logs\erro_inicializacao.txt
set APP_PORT=5070

echo ============================================================
echo   Atacarejo Insights - SITE PUBLICO + PORTAL + USUARIOS
echo ============================================================
echo.
echo Este inicializador fecha servidores antigos nas portas 5000, 5050,
echo 5060 e 5070, depois inicia o app limpo na porta 5070.
echo.
echo Pasta atual: %CD%
echo.

if not exist "app.py" (
    echo ERRO: app.py nao foi encontrado.
    echo Voce precisa EXTRAIR TODO O ZIP antes de executar.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERRO: requirements.txt nao foi encontrado.
    echo Voce provavelmente esta executando dentro do ZIP, sem extrair tudo.
    pause
    exit /b 1
)

echo Fechando servidores antigos que estejam ocupando as portas locais...
for %%P in (5000 5050 5060 5070) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo Encerrando processo na porta %%P - PID %%A
        taskkill /F /PID %%A >nul 2>nul
    )
)

echo.
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py -3
    ) else (
        echo ERRO: Python nao encontrado no Windows.
        echo Instale o Python em https://www.python.org/downloads/ e marque Add Python to PATH.
        pause
        exit /b 1
    )
)

echo Usando: %PYTHON_CMD%
%PYTHON_CMD% --version

echo.
if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual local...
    %PYTHON_CMD% -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERRO: nao foi possivel criar ambiente virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo.
echo Instalando/validando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERRO: falha ao instalar dependencias.
    echo Veja: %LOGFILE%
    pause
    exit /b 1
)

echo.
echo Iniciando o aplicativo na porta %APP_PORT%...
echo.
echo ============================================================
echo   ACESSE NO CHROME:
echo   http://localhost:5070
echo ============================================================
echo.
echo MANTENHA ESTA JANELA ABERTA enquanto usa o aplicativo.
echo.

start "" cmd /c "timeout /t 5 >nul & start http://localhost:5070?versao=v13"

echo ===== Nova execucao: %DATE% %TIME% ===== > "%LOGFILE%"
python app.py 2>> "%LOGFILE%"

echo.
echo O aplicativo foi encerrado ou ocorreu um erro.
echo Envie um print desta janela e do arquivo: %LOGFILE%
pause
