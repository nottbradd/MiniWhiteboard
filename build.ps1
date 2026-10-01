param([string]$Python = "$PSScriptRoot\.venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw 'Create .venv and install requirements-dev.txt first. See README.md.'
    }
    & $Python -m scripts.make_icon
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $Python -m scripts.make_version
    if ($LASTEXITCODE -ne 0) { throw 'Version resource generation failed.' }
    & $Python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    # OneDrive can mark generated directories read-only. PowerShell's -Force
    # handles those attributes when replacing a previous distribution.
    # Keep the currently distributed build and tester ZIP intact.
    $buildOutput = Join-Path $PSScriptRoot 'dist\windows-v11\Mini Whiteboard'
    if (Test-Path -LiteralPath $buildOutput) {
        $resolvedOutput = (Resolve-Path -LiteralPath $buildOutput).Path
        $resolvedWorkspace = (Resolve-Path -LiteralPath $PSScriptRoot).Path.TrimEnd('\') + '\'
        if (-not $resolvedOutput.StartsWith($resolvedWorkspace, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to replace build output outside this project.'
        }
        Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
    }
    & $Python -m PyInstaller --noconfirm --distpath 'dist\windows-v11' --workpath 'build\windows-v11' 'Mini Whiteboard.spec'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    Write-Output 'Built dist\windows-v11\Mini Whiteboard\Mini Whiteboard.exe. Distribute the entire folder.'
} finally {
    Pop-Location
}
