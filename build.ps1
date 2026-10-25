# Builds four edition-specific executables in one release pass.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt pyinstaller pillow
python tools\make_icon.py
$version = '2.3.0-beta.1'
$requiredProductIds = @(
  $env:TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID,
  $env:TASKFORGE_GUMROAD_PRO_PRODUCT_ID
)
if ($requiredProductIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }) {
  throw 'Set both TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID and TASKFORGE_GUMROAD_PRO_PRODUCT_ID before building all production editions.'
}
$release = Join-Path $PSScriptRoot "dist\TaskForge-$version"
New-Item -ItemType Directory -Force $release | Out-Null
$editions = @(
  @{ Id='free'; Name="TaskForge-$version-Free"; ProductId='' },
  @{ Id='free-ads'; Name="TaskForge-$version-Free-with-Ads"; ProductId='' },
  @{ Id='supporter'; Name="TaskForge-$version-Supporter"; ProductId=$env:TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID },
  @{ Id='pro'; Name="TaskForge-$version-Pro"; ProductId=$env:TASKFORGE_GUMROAD_PRO_PRODUCT_ID }
)
foreach ($edition in $editions) {
  $manifestDir = Join-Path $env:TEMP "taskforge-$($edition.Id)"
  New-Item -ItemType Directory -Force $manifestDir | Out-Null
  $manifest = Join-Path $manifestDir "edition.json"
  @{ edition=$edition.Id; product_id=$edition.ProductId } | ConvertTo-Json | Set-Content -Encoding UTF8 $manifest
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name $edition.Name `
    --distpath $release --workpath "$PSScriptRoot\build\$($edition.Id)" `
    --specpath "$PSScriptRoot\build\$($edition.Id)" --add-data "$manifest;." `
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
$packages = Join-Path $PSScriptRoot "dist\TaskForge-$version-Packages"
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
Write-Host "Built four editions: $release"
Write-Host "Built edition ZIPs: $packages"
