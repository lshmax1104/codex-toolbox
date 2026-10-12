param(
    [string]$Name = 'codex-toolbox',
    [string]$PythonCommand = 'python',
    [string[]]$AllowedRoot,
    [switch]$SkipRegister
)
$ErrorActionPreference = 'Stop'
$toolboxRoot = $PSScriptRoot
$venvPython = Join-Path $toolboxRoot '.venv\Scripts\python.exe'
$serverPath = Join-Path $toolboxRoot 'server.py'
$settingsPath = Join-Path $toolboxRoot 'settings.json'

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $PythonCommand -m venv (Join-Path $toolboxRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 이상이 필요합니다.' }
}
& $venvPython -m pip install -r (Join-Path $toolboxRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw '의존성 설치 실패' }

if (-not (Test-Path -LiteralPath $settingsPath)) {
    Copy-Item -LiteralPath (Join-Path $toolboxRoot 'settings.example.json') -Destination $settingsPath
}
$toolboxSettings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$toolboxSettings.allowed_roots = @($toolboxSettings.allowed_roots | ForEach-Object {
    if ($_.StartsWith('~/') -or $_.StartsWith('~\')) { Join-Path $env:USERPROFILE $_.Substring(2) } else { $_ }
})
if ($AllowedRoot) {
    $toolboxSettings.allowed_roots = @($AllowedRoot | ForEach-Object {
        (Resolve-Path -LiteralPath $_).Path
    })
} elseif (@($toolboxSettings.allowed_roots | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Container) }).Count -gt 0) {
    $defaultRoot = Join-Path $env:USERPROFILE 'Documents\Codex'
    New-Item -ItemType Directory -Path $defaultRoot -Force | Out-Null
    $toolboxSettings.allowed_roots = @($defaultRoot)
}
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($gitCommand) {
    $toolboxSettings.git_executable = $gitCommand.Source
    $toolboxSettings.tasks.'git-version'.command = @($gitCommand.Source, '--version')
}
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $toolboxSettings.tasks.'node-version'.command = @($nodeCommand.Source, '--version')
}
$utf8Encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($settingsPath, ($toolboxSettings | ConvertTo-Json -Depth 20), $utf8Encoding)
& $venvPython $serverPath --check | Out-Null
if ($LASTEXITCODE -ne 0) { throw '서버 구성 검증 실패' }

if (-not $SkipRegister) {
    $codexCommand = Get-Command codex -ErrorAction Stop
    & $codexCommand.Source mcp add $Name -- $venvPython $serverPath
    if ($LASTEXITCODE -ne 0) { throw 'Codex MCP 등록 실패' }
    & $codexCommand.Source mcp get $Name
}
Write-Host '설치 완료. Codex를 재시작하거나 MCP 연결을 다시 로드하세요.'
