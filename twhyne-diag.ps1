# Twhyne crash diagnostic - collects everything needed to explain a crash in
# one paste. Read-only: changes nothing. Run in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\twhyne-diag.ps1
$ErrorActionPreference = "SilentlyContinue"
function H($t) { Write-Host ""; Write-Host "=== $t ===" }

H "Time"; Get-Date -Format "yyyy-MM-dd HH:mm:ss"

H "Host memory (MB)"
$os = Get-CimInstance Win32_OperatingSystem
"total={0} free={1}" -f [int]($os.TotalVisibleMemorySize/1024), [int]($os.FreePhysicalMemory/1024)

H "Disk C: (GB)"
$d = Get-PSDrive C; "free={0:N1} used={1:N1}" -f ($d.Free/1GB), ($d.Used/1GB)

H "Docker VM virtual disks (GB) - grows with images + model cache"
Get-ChildItem "$env:LOCALAPPDATA\Docker\wsl" -Recurse -Filter *.vhdx |
  ForEach-Object { "{0}  {1:N1}" -f $_.FullName, ($_.Length/1GB) }

H ".wslconfig (and when it was last changed)"
$w = "$env:USERPROFILE\.wslconfig"
if (Test-Path $w) { (Get-Item $w).LastWriteTime; Get-Content $w } else { "(none)" }

H "Docker Desktop / engine versions"
docker version --format "client={{.Client.Version}} server={{.Server.Version}}"
(Get-Item "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe").VersionInfo.ProductVersion
(Get-Item "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe").LastWriteTime
wsl --version

H "Docker VM resources as the engine sees them"
docker info --format "mem={{.MemTotal}} cpus={{.NCPU}} driver={{.Driver}} os={{.OperatingSystem}}"

H "Docker disk usage"
docker system df

H "Twhyne image"
docker image inspect twhyne/twhyne:cpu --format "created={{.Created}} id={{.Id}}"

H "Last container state"
docker inspect twhyne-ai --format "status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} memlimit={{.HostConfig.Memory}}"

H "Last 40 container log lines"
docker logs --tail 40 twhyne-ai 2>&1

H "Windows events from Docker / WSL / Hyper-V in the last 24h"
Get-WinEvent -FilterHashtable @{LogName='Application','System'; StartTime=(Get-Date).AddHours(-24)} |
  Where-Object { $_.ProviderName -match 'Docker|WSL|Hyper-V|LxssManager|vmcompute' -or $_.Message -match 'docker|wsl|vmmem' } |
  Select-Object -First 25 TimeCreated, ProviderName, Id, @{n='Msg';e={$_.Message.Substring(0,[Math]::Min(160,$_.Message.Length))}} |
  Format-Table -AutoSize -Wrap

H "Recent unexpected shutdowns / kernel power events (last 7 days)"
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1001,6008; StartTime=(Get-Date).AddDays(-7)} |
  Select-Object -First 10 TimeCreated, Id, ProviderName | Format-Table -AutoSize

H "Windows updates installed in the last 30 days"
Get-HotFix | Where-Object { $_.InstalledOn -gt (Get-Date).AddDays(-30) } | Sort-Object InstalledOn | Format-Table -AutoSize HotFixID, InstalledOn

Write-Host ""; Write-Host "Done. Paste everything above."
