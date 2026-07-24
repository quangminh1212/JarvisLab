#Requires -Version 5.1
<#
.SYNOPSIS
  Detach JarvisLab skill junctions from local Hermes Agent.
  Does not remove mcp_servers.jarvislab (disable manually if needed).
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Hermes = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA 'hermes' }
$SkillsDstRoot = Join-Path $Hermes 'skills'
$SkillsSrc = Join-Path $Root 'skills'

Write-Host "== JarvisLab detach ==" -ForegroundColor Cyan
Write-Host "Hermes: $Hermes"

function Remove-JunctionOrWarn($path) {
  if (-not (Test-Path $path)) {
    Write-Host "missing (ok): $path"
    return
  }
  $item = Get-Item $path -Force
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    cmd /c "rmdir `"$path`"" | Out-Null
    Write-Host "removed junction: $path"
  } else {
    throw "Path exists and is not a junction (refusing delete): $path"
  }
}

$names = @()
if (Test-Path $SkillsSrc) {
  Get-ChildItem $SkillsSrc -Directory | ForEach-Object {
    if (Test-Path (Join-Path $_.FullName 'SKILL.md')) { $names += $_.Name }
  }
}
if ($names.Count -eq 0) { $names = @('jarvislab-voice') }

foreach ($n in $names) {
  Remove-JunctionOrWarn (Join-Path $SkillsDstRoot $n)
}

Write-Host ""
Write-Host "OK. JarvisLab skill detached." -ForegroundColor Green
Write-Host "MCP config left intact; remove mcp_servers.jarvislab in Hermes config if desired."
