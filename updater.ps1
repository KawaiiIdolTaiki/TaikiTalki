$repo     = "KawaiiIdolTaiki/TaikiTalki"
$apiUrl   = "https://api.github.com/repos/$repo/commits/main"
$shaFile  = Join-Path $PSScriptRoot ".last_commit"
$tmpZip   = Join-Path $env:TEMP "TaikiTalki.zip"
$tmpDir   = Join-Path $env:TEMP "TaikiTalki_update"

Write-Host "Checking for updates..."

try {
    $latest = (Invoke-RestMethod -Uri $apiUrl).sha
    $local  = if (Test-Path $shaFile) { Get-Content $shaFile } else { "" }

    if ($latest -ne $local) {
        Write-Host "Update found, downloading..."

        Invoke-WebRequest -Uri "https://github.com/$repo/archive/refs/heads/main.zip" -OutFile $tmpZip
        if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

        $src = Join-Path $tmpDir "TaikiTalki-main"
        $dst = $PSScriptRoot

        # Only update these files — requirements.txt and dumps folder are preserved
        foreach ($file in @("taikitalki.py", "events.json")) {
            $srcFile = Join-Path $src $file
            if (Test-Path $srcFile) {
                Copy-Item $srcFile $dst -Force
                Write-Host "Updated $file"
            }
        }

        $latest | Set-Content $shaFile
        Write-Host "Update complete."
    } else {
        Write-Host "Already up to date."
    }
} catch {
    Write-Host "Update check failed, continuing anyway..."
}