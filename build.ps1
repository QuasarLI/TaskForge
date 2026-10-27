# Builds four edition-specific executables in one release pass.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt pyinstaller pillow
python tools\make_icon.py
$version = '2.4.0-beta.1'
$requiredProductIds = @(
  $env:TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID,
  $env:TASKFORGE_GUMROAD_PRO_PRODUCT_ID
)
if ($requiredProductIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }) {
  throw 'Set both TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID and TASKFORGE_GUMROAD_PRO_PRODUCT_ID before building all production editions.'
}
$outputRoot = $env:TASKFORGE_OUTPUT_ROOT
if ([string]::IsNullOrWhiteSpace($outputRoot)) {
  $outputRoot = Join-Path $PSScriptRoot "dist"
}
New-Item -ItemType Directory -Force $outputRoot | Out-Null
$release = Join-Path $outputRoot "TaskForge-$version"
$packages = Join-Path $outputRoot "TaskForge-$version-Packages"
$buildRoot = Join-Path $env:TEMP "TaskForgeBuild\$version"
if ((Test-Path -LiteralPath $release) -or (Test-Path -LiteralPath $packages) -or
    (Test-Path -LiteralPath $buildRoot)) {
  throw "Build outputs already exist for $version; inspect them before rebuilding."
}
New-Item -ItemType Directory -Force $release | Out-Null
New-Item -ItemType Directory -Force $buildRoot | Out-Null
$editions = @(
  @{ Id='free'; Name="TaskForge-$version-Free"; ProductId=''; TestBuild=$false },
  @{ Id='free-ads'; Name="TaskForge-$version-Free-with-Ads"; ProductId=''; TestBuild=$false },
  @{ Id='supporter'; Name="TaskForge-$version-Supporter"; ProductId=$env:TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID; TestBuild=$false },
  @{ Id='pro'; Name="TaskForge-$version-Pro"; ProductId=$env:TASKFORGE_GUMROAD_PRO_PRODUCT_ID; TestBuild=$false }
)
foreach ($edition in $editions) {
  $manifestDir = Join-Path $env:TEMP "taskforge-$version-$($edition.Id)-$([guid]::NewGuid().ToString('N'))"
  New-Item -ItemType Directory -Force $manifestDir | Out-Null
  $manifest = Join-Path $manifestDir "edition.json"
  @{ edition=$edition.Id; product_id=$edition.ProductId; test_build=$edition.TestBuild } |
    ConvertTo-Json | Set-Content -Encoding UTF8 $manifest
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name $edition.Name `
    --distpath $release --workpath "$buildRoot\$($edition.Id)" `
    --specpath "$buildRoot\$($edition.Id)" --add-data "$manifest;." `
    --icon "$PSScriptRoot\assets\taskforge.ico" --version-file "$PSScriptRoot\tools\version_info.txt" `
    "$PSScriptRoot\run.py"
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $($edition.Id) with exit code $LASTEXITCODE" }
  Remove-Item $manifest -Force
  Remove-Item $manifestDir -Force
}
$built = @(Get-ChildItem "$release\*.exe")
if ($built.Count -ne 4) { throw "Expected four edition executables, found $($built.Count)" }
Get-FileHash "$release\*.exe" -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
  Set-Content -Encoding ASCII "$release\SHA256SUMS.txt"
Copy-Item README.md,LICENSING.md,PRIVACY.md,SECURITY.md "$release"
New-Item -ItemType Directory -Force $packages | Out-Null
foreach ($edition in $editions) {
  $packageName = $edition.Name
  $stage = Join-Path $env:TEMP "taskforge-package-$($edition.Id)-$([guid]::NewGuid().ToString('N'))"
  New-Item -ItemType Directory -Force $stage | Out-Null
  Copy-Item (Join-Path $release "$packageName.exe") $stage
  Copy-Item LICENSING.md $stage
  @"
TaskForge $version — $($edition.Name)

This production package contains only its matching edition executable.
Supporter and Pro require a valid matching Gumroad customer license.
No license key is included. Keep this package's SHA256SUMS.txt with the executable.

Source: https://github.com/QuasarLI/TaskForge
Security/privacy: https://github.com/QuasarLI/TaskForge
"@ | Set-Content -Encoding UTF8 (Join-Path $stage "README.txt")
  $hashFiles = @((Join-Path $stage "$packageName.exe"), (Join-Path $stage "LICENSING.md"),
    (Join-Path $stage "README.txt"))
  Get-FileHash -Path $hashFiles -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
    Set-Content -Encoding ASCII (Join-Path $stage "SHA256SUMS.txt")
  Compress-Archive -Force -Path (Join-Path $stage "*") -DestinationPath (Join-Path $packages "$packageName.zip")
  Remove-Item $stage -Recurse -Force
}
Write-Host "Built four production editions: $release"
Write-Host "Built edition ZIPs: $packages"

$testName = "TaskForge-$version-UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION"
$testManifestDir = Join-Path $env:TEMP "taskforge-$version-pro-test-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force $testManifestDir | Out-Null
$testManifest = Join-Path $testManifestDir "edition.json"
@{ edition='pro-test'; product_id=''; test_build=$true } |
  ConvertTo-Json | Set-Content -Encoding UTF8 $testManifest
python -m PyInstaller --noconfirm --clean --onefile --windowed --name $testName `
  --distpath $release --workpath "$buildRoot\pro-test" `
  --specpath "$buildRoot\pro-test" --add-data "$testManifest;." `
  --icon "$PSScriptRoot\assets\taskforge.ico" --version-file "$PSScriptRoot\tools\version_info.txt" `
  "$PSScriptRoot\run.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for the owner-only unlocked Pro test build" }
Remove-Item $testManifest -Force
Remove-Item $testManifestDir -Force

$testStage = Join-Path $env:TEMP "taskforge-package-pro-test-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force $testStage | Out-Null
Copy-Item (Join-Path $release "$testName.exe") $testStage
Copy-Item LICENSING.md $testStage
@"
TaskForge $version — UNLOCKED BETA TEST BUILD — NOT FOR DISTRIBUTION

Owner-only local evaluation build. This test binary is visibly watermarked, does not verify or accept production
license keys, and must never be uploaded to Gumroad, attached to a public release, or distributed.
"@ | Set-Content -Encoding UTF8 (Join-Path $testStage "UNLOCKED-TEST-NOT-FOR-DISTRIBUTION.txt")
$testFiles = @((Join-Path $testStage "$testName.exe"), (Join-Path $testStage "LICENSING.md"),
  (Join-Path $testStage "UNLOCKED-TEST-NOT-FOR-DISTRIBUTION.txt"))
Get-FileHash -Path $testFiles -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
  Set-Content -Encoding ASCII (Join-Path $testStage "SHA256SUMS.txt")
Compress-Archive -Force -Path (Join-Path $testStage "*") `
  -DestinationPath (Join-Path $packages "$testName.zip")
Remove-Item $testStage -Recurse -Force
Write-Host "Built owner-only unlocked Pro test build (never distribute): $release\$testName.exe"
$packageZips = @(Get-ChildItem (Join-Path $packages "*.zip"))
Get-FileHash -Path $packageZips.FullName -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
  Set-Content -Encoding ASCII (Join-Path $packages "SHA256SUMS.txt")
