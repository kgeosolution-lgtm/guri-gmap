$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'KGO-GIS') { throw 'Unexpected deployment host' }
$result = [ordered]@{}
$system = Get-CimInstance Win32_ComputerSystem
$result.memory_gb = [Math]::Round($system.TotalPhysicalMemory / 1GB, 1)
$result.logical_processors = $system.NumberOfLogicalProcessors
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$result.is_administrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$result.gpu = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
$result.python_commands = @(Get-Command python,python3,py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
$result.python_registry = @()
foreach ($registryRoot in @('HKLM:\SOFTWARE\Python\PythonCore','HKCU:\SOFTWARE\Python\PythonCore')) {
 if (Test-Path -LiteralPath $registryRoot) {
  foreach ($version in Get-ChildItem -LiteralPath $registryRoot) {
   $install = Get-ItemProperty -LiteralPath (Join-Path $version.PSPath 'InstallPath') -ErrorAction SilentlyContinue
   if ($install) { $result.python_registry += [ordered]@{version=$version.PSChildName;path=$install.'(default)';executable=$install.ExecutablePath} }
  }
 }
}
$result.oda = @()
foreach ($odaRoot in @('C:\Program Files\ODA','D:\Program Files\ODA')) {
 if (Test-Path -LiteralPath $odaRoot) { $result.oda += @(Get-ChildItem -LiteralPath $odaRoot -Filter ODAFileConverter.exe -File -Recurse | Select-Object -ExpandProperty FullName) }
}
$result.poppler_commands = @(Get-Command pdftoppm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
$result.tool_directories = @()
foreach ($toolRoot in @('D:\services','D:\tools','C:\tools','D:\codesolution')) {
 if (Test-Path -LiteralPath $toolRoot) { $result.tool_directories += @(Get-ChildItem -LiteralPath $toolRoot -Directory | Where-Object { $_.Name -match 'python|poppler|drawing|kgeo|oda|tool' } | Select-Object -ExpandProperty FullName) }
}
$result.target_exists = Test-Path -LiteralPath 'D:\codesolution\kgeodata\archdrawing'
$result.service_root_exists = Test-Path -LiteralPath 'D:\services\archdrawing'
$result.free_gb = [Math]::Round((Get-PSDrive D).Free / 1GB,1)
$result.iis_modules = @()
try {
 Import-Module WebAdministration -ErrorAction Stop
 $result.iis_modules = @(Get-WebGlobalModule | Where-Object { $_.Name -match 'Rewrite|Platform|FastCgi|ApplicationRequest' } | Select-Object -ExpandProperty Name)
} catch { $result.iis_module_read_available = $false }
$result.routing = @()
foreach ($configPath in @('D:\codesolution\kgeodata\web.config','D:\codesolution\kgeodata\kgeomcp\web.config')) {
 if (Test-Path -LiteralPath $configPath) {
  [xml]$configuration = Get-Content -LiteralPath $configPath -Raw
  $result.routing += [ordered]@{path=$configPath;rules=@($configuration.SelectNodes('//rewrite/rules/rule') | ForEach-Object { [ordered]@{name=$_.name;match=$_.match.url;action=$_.action.type;url=$_.action.url} })}
 }
}
$result.ports = @(Get-NetTCPConnection -State Listen -LocalPort 4193,8766 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort)
Write-Output ('ARCHDRAWING_PREFLIGHT ' + ($result | ConvertTo-Json -Depth 7 -Compress))
