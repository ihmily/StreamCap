param(
    [string]$OutputName = "pack_windows_rel_streamget",
    [string]$ProductVersion = "1.0.2",
    [string]$FileVersion = "1.0.2.0",
    [switch]$SkipEditableInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$streamgetRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "..\Streamget"))
$streamgetPackageRoot = Join-Path $streamgetRoot "streamget"

if (-not (Test-Path $streamgetPackageRoot)) {
    throw "streamget package not found: $streamgetPackageRoot"
}

$distRoot = Join-Path $projectRoot "dist\$OutputName"
$flatRoot = Join-Path $projectRoot "dist\${OutputName}_flat"
$bundleRoot = Join-Path $distRoot "StreamCap"
$flatBundleRoot = Join-Path $flatRoot "StreamCap"
$dateTag = Get-Date -Format "yyyyMMdd"
$zipPath = Join-Path $flatRoot "StreamCap-windows-x64-$dateTag-$OutputName.zip"

Write-Host "Project root: $projectRoot"
Write-Host "Sibling streamget: $streamgetRoot"

Push-Location $projectRoot
try {
    if (-not $SkipEditableInstall) {
        Write-Host "Installing sibling streamget in editable mode..."
        & python -m pip install -e $streamgetRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Editable install failed."
        }
    }

    foreach ($path in @($distRoot, $flatRoot)) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path
        }
    }

    $streamgetJsPath = Join-Path $streamgetRoot "streamget\js"

    Write-Host "Running flet pack..."
    & flet pack .\main.py `
        -D `
        -y `
        -n StreamCap `
        -i .\assets\icon.ico `
        --distpath $distRoot `
        --product-name StreamCap `
        --file-description "Live Stream Recorder" `
        --product-version $ProductVersion `
        --file-version $FileVersion `
        --company-name "io.github.ihmily.streamcap" `
        --copyright "Copyright (C) 2025 by Hmily" `
        --add-data "assets;assets" `
        --add-data "config;config" `
        --add-data "locales;locales" `
        --add-data "$streamgetJsPath;streamget\js"

    if ($LASTEXITCODE -ne 0) {
        throw "flet pack failed."
    }

    Write-Host "Creating flat bundle..."
    New-Item -ItemType Directory -Path $flatRoot | Out-Null
    Copy-Item -Recurse -Force $bundleRoot $flatBundleRoot
    Copy-Item -Recurse -Force (Join-Path $projectRoot "assets") (Join-Path $flatBundleRoot "assets")
    Copy-Item -Recurse -Force (Join-Path $projectRoot "config") (Join-Path $flatBundleRoot "config")
    Copy-Item -Recurse -Force (Join-Path $projectRoot "locales") (Join-Path $flatBundleRoot "locales")

    New-Item -ItemType Directory -Path (Join-Path $flatBundleRoot "streamget") -Force | Out-Null
    Copy-Item -Recurse -Force $streamgetJsPath (Join-Path $flatBundleRoot "streamget\js")

    if (Test-Path $zipPath) {
        Remove-Item -Force $zipPath
    }

    Write-Host "Creating zip package..."
    Compress-Archive -Path $flatBundleRoot -DestinationPath $zipPath -CompressionLevel Optimal

    Write-Host ""
    Write-Host "Build completed successfully."
    Write-Host "Bundle: $flatBundleRoot"
    Write-Host "Zip:    $zipPath"
}
finally {
    Pop-Location
}
