$zipPath = "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\handoffs\sourcehealth-final-visual-review.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$tempDir = Join-Path $env:TEMP ("sh-zip-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null

Write-Host "Staging frontend..."
$feDest = Join-Path $tempDir "frontend"
New-Item -ItemType Directory -Path $feDest | Out-Null
Get-ChildItem -Path "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\frontend" -Recurse | Where-Object {
    $_.FullName -notmatch '[\\/](node_modules|dist|\.git|\.env)'
} | ForEach-Object {
    $rel = $_.FullName.Substring("D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\frontend".Length).TrimStart('\/')
    $target = Join-Path $feDest $rel
    if ($_.PSIsContainer) {
        if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target | Out-Null }
    } else {
        $parent = Split-Path $target -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
        Copy-Item $_.FullName -Destination $target
    }
}

Write-Host "Staging screenshots and docs..."
$ssDest = Join-Path $tempDir "docs\screenshots"
New-Item -ItemType Directory -Path $ssDest -Force | Out-Null
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\docs\screenshots\*" -Destination $ssDest

$refDest = Join-Path $tempDir "docs\sourcecraft-reference-manual"
New-Item -ItemType Directory -Path $refDest -Force | Out-Null
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\docs\sourcecraft-reference-manual\*" -Destination $refDest

Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\docs\PRODUCT_BROWSER_ACCEPTANCE.md" -Destination (Join-Path $tempDir "docs")

Write-Host "Staging scripts..."
$scDest = Join-Path $tempDir "scripts"
New-Item -ItemType Directory -Path $scDest -Force | Out-Null
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\SourceHealth\scripts\*" -Destination $scDest

Write-Host "Staging handoff markdown files..."
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\handoffs\HANDOFF.md" -Destination $tempDir
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\CURRENT_STATE.md" -Destination $tempDir
Copy-Item "D:\IMPORTANT\AIProjects\AntigravitiProject\XakatonLTC\AGENT_LOG.md" -Destination $tempDir

Write-Host "Compressing archive to $zipPath..."
Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
Remove-Item $tempDir -Recurse -Force

$item = Get-Item $zipPath
Write-Host "Successfully created $($item.Name) with size $($item.Length) bytes."
