Set-Location -Path $PSScriptRoot
Write-Host "==============================================="
Write-Host "  Atacarejo Insights Portal - Inicializador"
Write-Host "==============================================="
Write-Host ""

if (-not (Test-Path "app.py")) {
    Write-Host "ERRO: O arquivo app.py nao foi encontrado nesta pasta." -ForegroundColor Red
    Write-Host "Isso geralmente acontece quando voce executa o arquivo direto de dentro do ZIP."
    Write-Host "Extraia todo o ZIP, abra a pasta extraida e execute novamente."
    Read-Host "Pressione Enter para sair"
    exit 1
}

if (-not (Test-Path "requirements.txt")) {
    Write-Host "ERRO: O arquivo requirements.txt nao foi encontrado nesta pasta." -ForegroundColor Red
    Write-Host "Extraia todo o ZIP antes de iniciar o aplicativo."
    Read-Host "Pressione Enter para sair"
    exit 1
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "ERRO: Python nao encontrado. Instale o Python e marque 'Add Python to PATH'." -ForegroundColor Red
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    $py = "py -3"
} else {
    $py = "python"
}

Write-Host "Pasta do aplicativo: $PWD"

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Criando ambiente virtual..."
    Invoke-Expression "$py -m venv .venv"
}

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
. ".\.venv\Scripts\Activate.ps1"

Write-Host "Instalando/validando dependencias..."
python -m pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao instalar dependencias. Verifique sua conexao com a internet." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

Write-Host ""
Write-Host "Iniciando o aplicativo..."
Write-Host "Aguarde aparecer: Running on http://127.0.0.1:5050"
Start-Job -ScriptBlock { Start-Sleep -Seconds 4; Start-Process "http://localhost:5050/login" } | Out-Null
python app.py
