# AlphaCycle X Bot — SSH vom Windows-PC (PowerShell)
#
# 1) Trage deine Server-IP unten ein (oder nutze einen Hostnamen).
# 2) Rechtsklick "Mit PowerShell ausfuehren" oder in PowerShell:  .\ssh-from-windows.ps1
# 3) Passwort wird gefragt — das ist normal (du loggst dich bei Hetzner o.ae. ein).
#
# OpenSSH-Client: Windows 10/11 unter "Optionale Features" -> OpenSSH-Client, falls ssh unbekannt.

param(
    [string]$ServerIp = "DEINE_SERVER_IP_HIER"
)

if ($ServerIp -eq "DEINE_SERVER_IP_HIER") {
    Write-Host "Bitte oeffne diese Datei und setze ServerIp auf deine VPS-IP." -ForegroundColor Yellow
    exit 1
}

Write-Host "Verbinde mit root@${ServerIp} ... (Passwort eingeben wenn gefragt)" -ForegroundColor Cyan
ssh "root@${ServerIp}"

# Nach dem Login auf dem Server z. B.:
#   cd ~/alphacycle-repo/alphacycle-x-bot
#   python3 test_telegram_approval.py
