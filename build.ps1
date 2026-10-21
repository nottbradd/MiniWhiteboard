param([string]$Python = "$PSScriptRoot\.venv\Scripts\python.exe",
      [string]$DistPath = 'dist\windows-v131-candidate')
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw 'Create .venv and install requirements-dev.txt first. See CONTRIBUTING.md.'
    }
    & $Python -m scripts.check_documentation
    if ($LASTEXITCODE -ne 0) { throw 'Documentation links failed.' }
    & $Python -m scripts.package_notices
    if ($LASTEXITCODE -ne 0) { throw 'License notice staging failed.' }
    & $Python -m scripts.make_icon
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $Python -m scripts.make_version
    if ($LASTEXITCODE -ne 0) { throw 'Version resource generation failed.' }
    & $Python -m scripts.run_tests
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    # OneDrive can mark generated directories read-only. PowerShell's -Force
    # handles those attributes when replacing a previous distribution.
    # Keep the currently distributed build and tester ZIP intact.
    $distributionRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $DistPath))
    $workspaceRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path.TrimEnd('\') + '\'
    if (-not $distributionRoot.StartsWith($workspaceRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The distribution directory must stay inside this project.'
    }
    $buildOutput = Join-Path $distributionRoot 'Mini Whiteboard'
    if (Test-Path -LiteralPath $buildOutput) {
        $resolvedOutput = (Resolve-Path -LiteralPath $buildOutput).Path
        $resolvedWorkspace = (Resolve-Path -LiteralPath $PSScriptRoot).Path.TrimEnd('\') + '\'
        if (-not $resolvedOutput.StartsWith($resolvedWorkspace, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to replace build output outside this project.'
        }
        Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
    }
    $buildWorkOutput = Join-Path $PSScriptRoot 'build\windows-v131-candidate'
    if (Test-Path -LiteralPath $buildWorkOutput) {
        $resolvedBuildWork = (Resolve-Path -LiteralPath $buildWorkOutput).Path
        if (-not $resolvedBuildWork.StartsWith($workspaceRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to clear build work outside this project.'
        }
        Remove-Item -LiteralPath $resolvedBuildWork -Recurse -Force
    }
    # Keep unrelated tools' DLLs out of PyInstaller's dependency search. In
    # particular, Qt uses Windows' ICU library, not an ICU DLL from a PDF tool.
    $buildRuntimeRoot = & $Python -c 'import sys; print(sys.base_prefix)'
    if ($LASTEXITCODE -ne 0) { throw 'Python runtime lookup failed.' }
    $originalBuildPath = $env:PATH
    $buildLibraryPath = @(
        (Split-Path -Parent $Python),
        $buildRuntimeRoot,
        (Join-Path $buildRuntimeRoot 'DLLs'),
        (Join-Path $env:SystemRoot 'System32'),
        $env:SystemRoot,
        (Join-Path $env:SystemRoot 'System32\Wbem')
    )
    try {
        $env:PATH = $buildLibraryPath -join [System.IO.Path]::PathSeparator
        & $Python -m PyInstaller --noconfirm --distpath $distributionRoot --workpath $buildWorkOutput 'Mini Whiteboard.spec'
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    } finally {
        $env:PATH = $originalBuildPath
    }
    Write-Output "Built $buildOutput\Mini Whiteboard.exe. Distribute the entire folder."
} finally {
    Pop-Location
}
