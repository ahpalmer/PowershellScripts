# This is a website with free IP addresses that you can test with
# https://www.quora.com/What-is-the-best-IP-address-to-ping-to-test-my-internet-connection
#'8.8.8.8': Google, '1.1.1.1': CloudFlare, '208.67.222.222': Cisco, '4.2.2.1': CenturyLink
#127.0.0.2: Loopback, designed to fail
# 192.0.2.0 This address is reserved for documentation and should not be assigned to any device, so pinging it should result in a failure.

Describe "Get-MultipleConections.ps1 Tests" {
    It "Should return Success" {
        $ipAddress = "8.8.8.8"
        $TimeoutMilliseconds = 500
        $answer = Test-Ping -ipAddress $ipAddress -TimeoutMilliseconds $TimeoutMilliseconds
        $answer | Should -Be 'Success'
    }
    It "Should return TimedOut" {
        $ipAddress = "192.0.2.0"
        $TimeoutMilliseconds = 500
        $answer = Test-Ping -ipAddress $ipAddress -TimeoutMilliseconds $TimeoutMilliseconds
        $answer | Should -Be 'TimedOut'
    }
    It "Should return succeeded" {
        $ipAddressList = @("8.8.8.8", '1.1.1.1', '208.67.222.222', '4.2.2.1')
        $answer = Test-MultipleConnections -ipAddressList $ipAddressList
        $expectedAnswer = @('8.8.8.8 connection succeeded', '1.1.1.1 connection succeeded', '208.67.222.222 connection succeeded', '4.2.2.1 connection succeeded')
        $answer | Should -Be $expectedAnswer
    }
    It "Should return TimedOut" {
        $ipAddressList = @("8.8.8.8", '192.0.2.0')
        $answer = Test-MultipleConnections -ipAddressList $ipAddressList
        $expectedAnswer = @('8.8.8.8 connection succeeded', '192.0.2.0 connection failed, Status: TimedOut')
        $answer | Should -Be $expectedAnswer
    }
}