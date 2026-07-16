$secpasswd = ConvertTo-SecureString "Qu1m1c4B055" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrador", $secpasswd)

# Check if we can run a command on the remote machine
Invoke-Command -ComputerName 192.168.2.187 -Credential $cred -ScriptBlock {
    Write-Host "Connected to remote machine."
    # Check if we can connect to SQL locally on that machine
    $serverName = "localhost\SQLEXPRESS"
    $connectionString = "Server=$serverName;Database=master;Integrated Security=True;"
    
    try {
        $connection = New-Object System.Data.SqlClient.SqlConnection
        $connection.ConnectionString = $connectionString
        $connection.Open()
        
        $command = $connection.CreateCommand()
        $command.CommandText = "SELECT @@VERSION"
        $version = $command.ExecuteScalar()
        Write-Host "SQL Server Version: $version"
        
        $connection.Close()
    } catch {
        Write-Host "SQL Connection failed: $($_.Exception.Message)"
    }
}
