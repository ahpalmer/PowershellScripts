param (
    [string[]]$ipAddressList,
    [int]$TimeoutMilliseconds = 500,
    [string]$path
)

<#
.SYNOPSIS
Pings multiple IP addresses and returns the status of each.

.DESCRIPTION
This function pings mutiple IP address and returns status of each.  Test-NetConnection takes a very long time to connect to each address.  This is a very lightweight function that does not attempt a TCP connection and only pings the addresses.

.EXAMPLE
$ipAddressList = @("8.8.8.8", "0.0.0.0", "1.1.1.1")
IN PS TERMINAL: & .\Test-MultipleConnections.ps1 -ipAddressList $ipAddressList
IN VSCODE:      .\Test-MultipleConnections.ps1 -ipAddressList $ipAddressList
or
.\Test-MultipleConnections.ps1 -ipAddressList "8.8.8.8", "0.0.0.0", "1.1.1.1"
or
.\Test-MultipleConnections.ps1 -ipAddressList $ipAddressList -TimeoutMilliseconds $miliSeconds
or
.\Test-MultipleConnections.ps1 -path "C:\path\to\ipaddresses.txt"

.NOTES
I considered using Test-NetConnection multiple times but it was very slow.  In the future, if I see a need to test multiple connections using Test-NetConnection I'll change the function 'Test-MultipleConnections' to access that commandlet, and I'll change the current function to 'Test-MultiplePings'.
Example IP addresses: 
'8.8.8.8': Google
'1.1.1.1': CloudFlare
'208.67.222.222': Cisco 
'4.2.2.1': CenturyLink
127.0.0.2: Loopback, I thought it would fail but it actually succeeds
192.0.2.0 This address is reserved for documentation and should not be assigned to any device, so pinging it should result in a failure.
#>

function Test-MultipleConnections {
    # Define the Test-Ping script block for parallel execution
    $scriptBlock = {
        param($ipAddress, $TimeoutMilliseconds)
        
        $ping = New-Object System.Net.NetworkInformation.Ping
        $replyOne = $ping.Send($ipAddress, $TimeoutMilliseconds)
        $replyTwo = $ping.Send($ipAddress, $TimeoutMilliseconds)
        $replyThree = $ping.Send($ipAddress, $TimeoutMilliseconds)
        $replyFour = $ping.Send($ipAddress, $TimeoutMilliseconds)
        $replyList = @($replyOne, $replyTwo, $replyThree, $replyFour)

        $successfulReplies = $replyList | Where-Object { $_.Status -eq [System.Net.NetworkInformation.IPStatus]::Success }

        [PSCustomObject]@{
            IpAddress = $ipAddress
            SuccessCount = $successfulReplies.Count
            FailedStatus = if ($successfulReplies.Count -eq 0) { ($replyList | Where-Object { $_.Status -ne [System.Net.NetworkInformation.IPStatus]::Success } | Select-Object -First 1).Status } else { $null }
        }
    }

    # Create runspace pool for parallel execution
    $runspacePool = [RunspaceFactory]::CreateRunspacePool(1, [Math]::Min($ipAddressList.Count, 50))
    $runspacePool.Open()

    # Start all runspaces in parallel
    $runspaces = foreach ($ipAddress in $ipAddressList) {
        $powershell = [PowerShell]::Create()
        $powershell.RunspacePool = $runspacePool
        [void]$powershell.AddScript($scriptBlock).AddArgument($ipAddress).AddArgument($TimeoutMilliseconds)
        
        [PSCustomObject]@{
            PowerShell = $powershell
            Handle = $powershell.BeginInvoke()
        }
    }

    # Wait for all runspaces and collect results
    $results = foreach ($runspace in $runspaces) {
        $runspace.PowerShell.EndInvoke($runspace.Handle)
        $runspace.PowerShell.Dispose()
    }

    $runspacePool.Close()
    $runspacePool.Dispose()

    # Output results
    foreach ($result in $results) {
        if ($result.SuccessCount -eq 4) {
            Write-Output "$($result.IpAddress) connection succeeded"
        } elseif ($result.SuccessCount -gt 0) {
            Write-Output "$($result.IpAddress) connection succeeded with $($result.SuccessCount) successful connects" 
        } else {
            Write-Output "$($result.IpAddress) connection failed, Status: $($result.FailedStatus)"
        }
    }
}

function Test-Ping {
    param (
        [string]$ipAddress
    )

    $ping = New-Object System.Net.NetworkInformation.Ping
    $replyOne = $ping.Send($ipAddress, $TimeoutMilliseconds)
    $replyTwo = $ping.Send($ipAddress, $TimeoutMilliseconds)
    $replyThree = $ping.Send($ipAddress, $TimeoutMilliseconds)
    $replyFour = $ping.Send($ipAddress, $TimeoutMilliseconds)
    $replyList = @($replyOne, $replyTwo, $replyThree, $replyFour)

    $result = $replyList | Where-Object { $_.Status -eq 'Success' }

    if ($result.Count -eq 4) {
        return $result
    } elseif ($result.Count -gt 0) {
        return $result
    } else {
        $failedReplies = $replyList | Where-Object { $_.Status -ne 'Success' }
        return $failedReplies
    }
}

# If a file path is provided, read IP addresses from the file
if ($path) {
    if (Test-Path $path) {
        $ipAddressList = Get-Content $path | Where-Object { $_.Trim() -ne "" }
    } else {
        Write-Error "File not found: $path"
        exit 1
    }
}

if (($null -eq $ipAddressList) -or ($ipAddressList.Count -eq 0)) {
    Write-Output "No IP address provided, using defaults, '8.8.8.8', '1.1.1.1', '208.67.222.222', '4.2.2.1'"
    $ipAddressList = @('8.8.8.8', '1.1.1.1', '208.67.222.222', '4.2.2.1')
    Test-MultipleConnections -ipAddressList $ipAddressList
}

Test-MultipleConnections -ipAddressList $ipAddressList -TimeoutMilliseconds $TimeoutMilliseconds