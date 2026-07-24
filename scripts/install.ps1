#Requires -Version 5.1
<#
.SYNOPSIS
  Attach JarvisLab to local Hermes Agent (skill junction + MCP config fix).
  SoT stays in C:\Dev\JarvisLab - no hermes-agent source edits.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Hermes = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA 'hermes' }
$SkillsSrc = Join-Path $Root 'skills'
$SkillsDstRoot = Join-Path $Hermes 'skills'

Write-Host "== JarvisLab attach ==" -ForegroundColor Cyan
Write-Host "Repo:   $Root"
Write-Host "Hermes: $Hermes"

if (-not (Test-Path $Hermes)) {
  throw "Hermes home not found: $Hermes - install Hermes Agent first."
}
if (-not (Test-Path $SkillsSrc)) {
  throw "skills/ missing under $Root"
}

function Ensure-Junction($dst, $src) {
  $parent = Split-Path $dst -Parent
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $want = (Resolve-Path $src).Path
  if (Test-Path $dst) {
    $item = Get-Item $dst -Force
    $isLink = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    $target = $null
    if ($isLink -and $item.Target) { $target = @($item.Target)[0] }
    if ($isLink -and $target) {
      $resolved = Resolve-Path $target -ErrorAction SilentlyContinue
      if ($resolved -and $resolved.Path -eq $want) {
        Write-Host "Junction OK: $dst -> $src"
        return
      }
      Write-Host "Re-pointing junction: $dst"
      cmd /c "rmdir `"$dst`"" | Out-Null
    } else {
      Write-Host "Replacing non-junction path: $dst"
      Remove-Item -Recurse -Force $dst
    }
  }
  cmd /c mklink /J "$dst" "$src" | Write-Host
}

Get-ChildItem $SkillsSrc -Directory | ForEach-Object {
  $skillMd = Join-Path $_.FullName 'SKILL.md'
  if (-not (Test-Path $skillMd)) { return }
  $dst = Join-Path $SkillsDstRoot $_.Name
  Ensure-Junction $dst $_.FullName
}

$fixMcp = Join-Path $Root 'scripts\fix_hermes_mcp.py'
if (Test-Path $fixMcp) {
  $pyCandidates = @(
    (Join-Path $Hermes 'hermes-agent\venv\Scripts\python.exe'),
    (Join-Path $Hermes 'hermes-agent\.venv\Scripts\python.exe'),
    'python'
  )
  $py = $pyCandidates | Where-Object { $_ -eq 'python' -or (Test-Path $_) } | Select-Object -First 1
  Write-Host "Fixing Hermes mcp_servers.jarvislab via $fixMcp"
  & $py $fixMcp
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "fix_hermes_mcp.py failed (skill junction still attached)"
  }
}

Write-Host ""
Write-Host "OK. JarvisLab attached." -ForegroundColor Green
Write-Host "In Hermes chat: /jarvislab-voice  (or skill_view jarvislab-voice)"
Write-Host "MCP tools:      mcp__jarvislab__voice_*"
Write-Host "Detach:         powershell -File $Root\scripts\uninstall.ps1"
Write-Host "Smoke:          cd $Root; npm test; node scripts\mcp_list.js"
Write-Host "New Hermes session after MCP/skill attach."
