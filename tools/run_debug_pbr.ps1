# Lanca o RangeEngine com log de debug para investigar travamento/fechamento
# ao ligar PBR Shading Nodes e mudar a 3D view para Material.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File tools\run_debug_pbr.ps1 [caminho.blend]
#
# Os arquivos ficam em debug-logs\RangeEngine-pbr-<data>.{log,stdout,stderr}.txt

param(
    [string]$BlendFile = "",
    [string]$Tag = "pbr"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $repo "build\bin\AnastacioEngine.exe"
if (-not (Test-Path $exe)) {
    throw "AnastacioEngine.exe nao encontrado em $exe - compile antes (skill build-anastacio)."
}

$logDir = Join-Path $repo "debug-logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory $logDir | Out-Null }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$base = Join-Path $logDir "RangeEngine-$Tag-$stamp"

# gpu.* e o caminho de compilacao de shader; wm/handlers mostram o ultimo
# operador antes do fechamento; -1 loga todos os niveis.
$ArgsList = @(
    "--debug",
    "--debug-gpu-shaders",
    "--debug-wm",
    "--log", "*",
    "--log-level", "-1",
    "--log-show-basename",
    "--log-file", "$base.log.txt"
)
if ($BlendFile -ne "") { $ArgsList = @($BlendFile) + $ArgsList }

Write-Output "Log:    $base.log.txt"
Write-Output "stdout: $base.stdout.txt"
Write-Output "stderr: $base.stderr.txt"
Write-Output ""
Write-Output "Reproduza agora: ligue PBR Shading Nodes e mude a 3D view para Material."
Write-Output "Quando fechar/travar, feche esta janela e me avise o nome do log."

$p = Start-Process -FilePath $exe -ArgumentList $ArgsList `
    -RedirectStandardOutput "$base.stdout.txt" `
    -RedirectStandardError "$base.stderr.txt" `
    -PassThru -Wait

Write-Output ""
Write-Output "Saiu com codigo $($p.ExitCode)."
