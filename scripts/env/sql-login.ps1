# Let the current Windows user use the local SQL Server WITHOUT elevation (so agents can run sqlcmd/pyodbc), or
# undo it. Granting needs a sysadmin connection, so run -Grant once in an ELEVATED PowerShell; -Status and
# -Revoke can run as the user that has the login.
#   scripts\env\sql-login.ps1 -Status            # does the login exist, is it sysadmin?
#   scripts\env\sql-login.ps1 -Grant             # CREATE LOGIN [DOMAIN\user] FROM WINDOWS + sysadmin
#   scripts\env\sql-login.ps1 -Grant -Role dbcreator   # narrower: can create databases only
#   scripts\env\sql-login.ps1 -Revoke            # cleanup: drop the login (run elevated)
# A sysadmin login is a lasting privilege on the machine: prefer -Role dbcreator for coursework, and -Revoke
# when it's no longer needed.
param([switch]$Grant, [switch]$Revoke, [switch]$Status, [string]$Server = 'localhost',
      [ValidateSet('sysadmin', 'dbcreator')][string]$Role = 'sysadmin')
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
function Q($sql) { sqlcmd -S $Server -E -C -b -h -1 -W -Q "SET NOCOUNT ON; $sql" }

if ($Grant) {
    Q "IF SUSER_ID(N'$user') IS NULL CREATE LOGIN [$user] FROM WINDOWS; ALTER SERVER ROLE [$Role] ADD MEMBER [$user];"
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Fallo. Ejecuta este script en una PowerShell como administrador.'; exit 1 }
}
if ($Revoke) {
    Q "IF SUSER_ID(N'$user') IS NOT NULL DROP LOGIN [$user];"
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Fallo. Ejecuta este script en una PowerShell como administrador.'; exit 1 }
}
Q "SELECT 'login=' + ISNULL((SELECT name FROM sys.server_principals WHERE name = N'$user'), '(no existe)') + '  sysadmin=' + CAST(ISNULL(IS_SRVROLEMEMBER('sysadmin', N'$user'), 0) AS varchar) + '  dbcreator=' + CAST(ISNULL(IS_SRVROLEMEMBER('dbcreator', N'$user'), 0) AS varchar);"
