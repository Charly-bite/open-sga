$ErrorActionPreference = "Continue"
Start-Transcript -Path "C:\setup_sql_log.txt"

Write-Host "Setting up SQL Server..."

# Enable TCP/IP
$wmiNamespace = (Get-WmiObject -Namespace "root\Microsoft\SqlServer" -Class "__NAMESPACE" | Where-Object Name -like "ComputerManagement*").Name
if ($wmiNamespace) {
    Write-Host "Found WMI Namespace: $wmiNamespace"
    $fullNamespace = "root\Microsoft\SqlServer\$wmiNamespace"
    $protocol = Get-WmiObject -Namespace $fullNamespace -Class ServerNetworkProtocol -Filter "InstanceName='SQLEXPRESS' and ProtocolName='Tcp'"
    if ($protocol) {
        $protocol.SetEnable()
        Write-Host "Enabled TCP Protocol."
        
        # Set TCP Dynamic Ports to empty and Port to 1433 for IPAll
        $ipAllPort = Get-WmiObject -Namespace $fullNamespace -Class ServerNetworkProtocolProperty -Filter "InstanceName='SQLEXPRESS' and ProtocolName='Tcp' and IPAddressName='IPAll' and PropertyName='TcpPort'"
        if ($ipAllPort) { $ipAllPort.SetStringValue("1433") }
        
        $ipAllDynPort = Get-WmiObject -Namespace $fullNamespace -Class ServerNetworkProtocolProperty -Filter "InstanceName='SQLEXPRESS' and ProtocolName='Tcp' and IPAddressName='IPAll' and PropertyName='TcpDynamicPorts'"
        if ($ipAllDynPort) { $ipAllDynPort.SetStringValue("") }
        
        Write-Host "Restarting SQL Server..."
        Restart-Service -Name "MSSQL`$SQLEXPRESS" -Force
    }
} else {
    Write-Host "Could not find WMI Namespace for SQL."
}

# Create User and Database
$sql = @"
IF NOT EXISTS (SELECT name FROM master.sys.databases WHERE name = N'SGA_Database')
BEGIN
    CREATE DATABASE SGA_Database;
END
GO
USE SGA_Database;
GO
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = N'sga_app_user')
BEGIN
    CREATE LOGIN sga_app_user WITH PASSWORD = 'Qu1m1c4B055', CHECK_POLICY = OFF;
END
GO
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'sga_app_user')
BEGIN
    CREATE USER sga_app_user FOR LOGIN sga_app_user;
END
GO
ALTER ROLE db_owner ADD MEMBER sga_app_user;
GO
ALTER SERVER ROLE sysadmin ADD MEMBER sga_app_user;
GO
EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;
EXEC sp_configure 'mixed mode authentication', 1;
RECONFIGURE;
"@

$sql | Out-File -FilePath "C:\setup_sql.sql" -Encoding ascii
Write-Host "Executing SQLCMD..."
& sqlcmd -S .\SQLEXPRESS -E -i "C:\setup_sql.sql"

# Enable SQL Authentication in Registry (Mixed Mode)
$regPath = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL*SQLEXPRESS\MSSQLServer"
$key = Get-Item -Path "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server" -ErrorAction SilentlyContinue
if ($key) {
    # It's usually easier to just use the exact path if we can find it
    $instances = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL" -ErrorAction SilentlyContinue
    if ($instances) {
        $instName = $instances.GetValue("SQLEXPRESS")
        $fullPath = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instName\MSSQLServer"
        Set-ItemProperty -Path $fullPath -Name "LoginMode" -Value 2
        Write-Host "Set LoginMode to Mixed Authentication."
        Restart-Service -Name "MSSQL`$SQLEXPRESS" -Force
    }
}

# Allow Firewall
Write-Host "Configuring Firewall..."
New-NetFirewallRule -DisplayName "SQL Server 1433" -Direction Inbound -LocalPort 1433 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue

Stop-Transcript
