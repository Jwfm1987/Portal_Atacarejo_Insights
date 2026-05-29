@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Parar servidores locais antigos - Atacarejo Insights

echo Fechando processos que estejam usando as portas 5000, 5050, 5060 e 5070...
for %%P in (5000 5050 5060 5070) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo Encerrando porta %%P - PID %%A
        taskkill /F /PID %%A
    )
)

echo.
echo Concluido. Agora execute INICIAR_APP_CORRIGIDO_PORTA_5070.bat
pause
