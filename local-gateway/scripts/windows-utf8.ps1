$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

try {
    chcp 65001 | Out-Null
} catch {
}

Write-Output "UTF-8 console mode enabled for this PowerShell session."
