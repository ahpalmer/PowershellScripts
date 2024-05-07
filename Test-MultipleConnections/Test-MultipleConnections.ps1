param (
    [string[]]$ipAddressList,
    [int]$TimeoutMilliseconds = 500
)

<#
.SYNOPSIS
Pings multiple IP addresses and returns the status of each.

.DESCRIPTION
This function pings mutiple IP address and returns status of each.  Test-NetConnection takes a very long time to connect to each address.  This is a very lightweight function that does not attempt a TCP connection and only pings the addresses.

.EXAMPLE
$ipAddressList = @("8.8.8.8", 0.0.0.0, 1.1.1.1)
.\Test-MultipleConnections.ps1 -ipAddressList $ipAddressList
or
.\Test-MultipleConnections.ps1 -ipAddressList "8.8.8.8", "0.0.0.0", "1.1.1.1"
or
.\Test-MultipleConnections.ps1 -ipAddressList $ipAddressList -TimeoutMilliseconds $miliSeconds

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

# Todo: Figure out how to run this from a terminal instead of only running it in VSCode.  It's not working in the terminal and I've spent too long trying to figure it out.  Do it tomorrow.
function Test-MultipleConnections {
    foreach ($ipAddress in $ipAddressList) {
        $result = Test-Ping -ipAddress $ipAddress
        if ($result.Count -eq 4) {
            Write-Output "$ipAddress connection succeeded"
        } elseif ($result.Count -gt 0) {
            Write-Output "$ipAddress connection succeeded with $($result.Count) successful connects" 
        }
        else {
            Write-Output "$ipAddress connection failed, Status: $($result[0].Status)"
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

if (($null -eq $ipAddressList) -or ($ipAddressList -eq "")) {
    Write-Output "No IP address provided, using defaults, '8.8.8.8', '1.1.1.1', '208.67.222.222', '4.2.2.1'"
    $ipAddressList = @('8.8.8.8', '1.1.1.1', '208.67.222.222', '4.2.2.1')
}
