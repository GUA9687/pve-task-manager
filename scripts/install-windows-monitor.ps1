param([Parameter(Mandatory=$true)][System.Net.IPAddress]$MonitorAddress)
$ErrorActionPreference = 'Stop'
$stage = $PSScriptRoot
Start-Transcript -Path (Join-Path $stage 'windows-install.log') -Force
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator elevation is required.' }
    $msi = Join-Path $stage 'windows_exporter-0.31.9-amd64.msi'
    if ((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ne '1E8A3898E8FEBAA475E008FFD2E729E1BEF84ECBCB6875910546EE0798E96126') { throw 'Installer checksum mismatch' }
    $argsList = @('/i', ('"' + $msi + '"'), '/qn', '/norestart', 'ENABLED_COLLECTORS=cpu,logical_disk,memory,net,os,physical_disk,system', 'LISTEN_PORT=9182', 'ADDLOCAL=ALL', ('REMOTE_ADDR='+$MonitorAddress.ToString()), '/L*v', ('"'+(Join-Path $stage 'windows-msi.log')+'"'))
    $result = Start-Process msiexec.exe -ArgumentList $argsList -Wait -PassThru -WindowStyle Hidden
    if ($result.ExitCode -notin @(0,3010)) { throw "MSI exit code $($result.ExitCode)" }
    Start-Service windows_exporter
    (Invoke-WebRequest 'http://127.0.0.1:9182/health' -UseBasicParsing).Content | Out-File (Join-Path $stage 'windows-install-success.txt')
} catch {
    $_ | Out-String | Out-File (Join-Path $stage 'windows-install-error.txt')
    throw
} finally { Stop-Transcript }

