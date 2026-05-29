@echo off
cd /d "%~dp0"
echo Testando acesso local ao aplicativo...
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (set PYTHON_CMD=python) else (set PYTHON_CMD=py -3)
%PYTHON_CMD% - <<PY
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:5000', timeout=3)
    print('OK: o servidor respondeu. Status:', r.status)
except Exception as e:
    print('ERRO: nao consegui conectar em http://127.0.0.1:5000')
    print(type(e).__name__ + ': ' + str(e))
PY
pause
