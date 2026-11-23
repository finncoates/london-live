<#
  Connects a new Oracle Cloud machine to London Live in one go (run it on this PC, in PowerShell):

    .\rail\darwin\connect.ps1 -Ip 1.2.3.4 -Key C:\Users\you\.ssh\oracle.key

  1. installs (or updates) the London Live server on the machine over SSH
  2. makes a new secret token and gives it to both the server and the Cloudflare relay (it's never shown)
  3. asks for your keys (Darwin, AISStream, NTA, ODPT) in hidden prompts: press Enter to skip any you don't have yet
  4. points the relay at the machine (DARWIN_URL) and checks everything answers

  Run it again any time: -KeysOnly just asks for keys; -NoPrompt skips the key questions.
  Keys typed here go straight to the machine's settings file over SSH; they're never saved on this PC or in the code.
#>
param(
  [Parameter(Mandatory = $true)][string]$Ip,
  [string]$Key = "$HOME\.ssh\id_rsa",
  [string]$User = 'opc',      # Oracle Linux; 'ubuntu' on Ubuntu images
  [switch]$KeysOnly,
  [switch]$NoPrompt
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)       # london-live
$rail = Join-Path $repo 'rail'
$target = "$User@$Ip"
$sshArgs = @('-i', $Key, '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20', $target)
function Invoke-Remote([string]$cmd, [string]$stdin = $null){
  if($null -ne $stdin){ $stdin | & ssh @sshArgs $cmd } else { & ssh @sshArgs $cmd }
  if($LASTEXITCODE -ne 0){ throw "The command on the machine failed ($LASTEXITCODE): $cmd" } }
function Set-RelaySecret([string]$name, [string]$value){
  Push-Location $rail; try{ $value | & npx.cmd --yes wrangler@4 secret put $name | Out-Null; if($LASTEXITCODE -ne 0){ throw "Couldn't set $name on Cloudflare" } } finally { Pop-Location } }
function Read-Secret([string]$label){
  $s = Read-Host -AsSecureString $label
  [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)) }

Write-Host "Checking SSH to $target ..." -ForegroundColor Cyan
Invoke-Remote 'echo connected'

if(-not $KeysOnly){
  Write-Host 'Installing / updating the server (a few minutes the first time) ...' -ForegroundColor Cyan
  Invoke-Remote 'curl -fsSL https://raw.githubusercontent.com/finncoates/london-live/main/rail/darwin/install.sh -o install.sh && bash install.sh'

  Write-Host 'Making a new relay token and giving it to the server and Cloudflare ...' -ForegroundColor Cyan
  $bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $token = -join ($bytes | ForEach-Object { $_.ToString('x2') })
  Invoke-Remote 'bash ~/london-live/rail/darwin/setenv.sh' "RELAY_TOKEN=$token"
  Set-RelaySecret 'RELAY_TOKEN' $token
  Set-RelaySecret 'DARWIN_URL' "http://$Ip.sslip.io"
  Remove-Variable token
}

if(-not $NoPrompt){
  Write-Host ''
  Write-Host 'Your keys (hidden as you type; Enter skips one). They go straight to the machine.' -ForegroundColor Cyan
  Write-Host '  Darwin: Rail Data Marketplace -> My Subscriptions -> Darwin Real Time Train Information (Kafka) -> connection details'
  $lines = @()
  $boot = Read-Host '  Darwin "Kafka bootstrap server"'
  if($boot){
    $lines += "DARWIN_BOOTSTRAP=$($boot.Trim())"
    $mech = Read-Host '  Darwin "SASL mechanism" (e.g. PLAIN)'
    if($mech){ $lines += "DARWIN_SASL=$($mech.Trim())" }
    # The Kafka login is inside the "SASL config" line: ... username='…' password='…';  (NOT the website login)
    $cfg = Read-Secret '  Darwin "SASL config" (copy the whole box and paste; hidden)'
    $u = [regex]::Match($cfg, 'username\s*=\s*["'']([^"'']+)["'']').Groups[1].Value
    $p = [regex]::Match($cfg, 'password\s*=\s*["'']([^"'']+)["'']').Groups[1].Value
    if($u -and $p){ $lines += "DARWIN_USERNAME=$u"; $lines += "DARWIN_PASSWORD=$p"; Write-Host "    found the login in it ($($u.Length)-character username)" -ForegroundColor Green }
    else { Write-Host "    No login in that, so it'll be the page's Consumer key and Consumer secret:" -ForegroundColor Yellow
      $u = (Read-Host '  Darwin "Consumer key" (the username)').Trim()
      $p = (Read-Secret '  Darwin "Consumer secret" (the password; often behind a show/copy button; hidden)').Trim()
      if($u -and $p){ $lines += "DARWIN_USERNAME=$u"; $lines += "DARWIN_PASSWORD=$p"; Write-Host "    ok ($($u.Length)-character key, $($p.Length)-character secret)" -ForegroundColor Green } }
    Remove-Variable cfg, u, p -ErrorAction SilentlyContinue
  }
  foreach($k in @(
      @('DARWIN_TOPIC', 'Darwin "Topic" (needed: on the same page)', $false),
      @('DARWIN_GROUP', 'Darwin "Consumer group" (Enter if the page shows none)', $false),
      @('AISSTREAM_KEY', 'AISStream key (live ferries; aisstream.io)', $true),
      @('NTA_KEY', 'NTA key (Ireland live buses; developer.nationaltransport.ie)', $true),
      @('ODPT_KEY', 'ODPT key (Tokyo live trains; developer.odpt.org)', $true))){
    $v = if($k[2]){ Read-Secret "  $($k[1])" } else { Read-Host "  $($k[1])" }
    if($v){ $lines += "$($k[0])=$v" } }
  if($lines.Count){ Invoke-Remote 'bash ~/london-live/rail/darwin/setenv.sh' ($lines -join "`n") }
  Remove-Variable lines, v -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host 'Checking ...' -ForegroundColor Cyan
Start-Sleep -Seconds 8
try{ $h = Invoke-RestMethod "http://$Ip.sslip.io/health" -TimeoutSec 15
  Write-Host ("Server: Darwin {0} ({1} messages) - ferries {2} - live feeds: {3}" -f ($(if($h.darwin){'on'}else{'off'})), $h.messages, $h.ferries.status, (($h.feeds.PSObject.Properties | ForEach-Object { "$($_.Name) $($_.Value.vehicles)" }) -join ', ')) -ForegroundColor Green }
catch{ Write-Host "The server didn't answer on port 80. Check Oracle's Security List allows TCP port 80 (SETUP.md step 3)." -ForegroundColor Yellow }
try{ $r = Invoke-RestMethod 'https://london-rail.londonlivemap.workers.dev/srv/health' -TimeoutSec 20
  Write-Host ("Relay -> server: OK ({0} live feeds)" -f @($r.feeds.PSObject.Properties).Count) -ForegroundColor Green }
catch{ Write-Host "The relay can't reach the server yet: $($_.Exception.Message)" -ForegroundColor Yellow }
