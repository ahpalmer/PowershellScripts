# Set the path to search
$searchPath = "c:\Users\andrewpalmer\Documents\WorkRepos\ACES\src\ACES.AdminPortal\node_modules"

# Define the vulnerable versions to search for
$vulnerableVersions = @(
    "19.0.0-rc-6230622a1a-20240610",
    "19.2.0-canary-5252281c-20250408"
)

# Find all package.json files recursively
Write-Host "Searching for vulnerable packages in: $searchPath" -ForegroundColor Cyan
Write-Host "Looking for versions: $($vulnerableVersions -join ', ')" -ForegroundColor Cyan
Write-Host ""

$packageFiles = Get-ChildItem -Path $searchPath -Filter "package.json" -Recurse -ErrorAction SilentlyContinue

$foundVulnerabilities = @()

foreach ($file in $packageFiles) {
    try {
        $content = Get-Content -Path $file.FullName -Raw | ConvertFrom-Json
        $packageName = $content.name
        $packageVersion = $content.version
        
        foreach ($vulnVersion in $vulnerableVersions) {
            if ($packageVersion -eq $vulnVersion) {
                $foundVulnerabilities += [PSCustomObject]@{
                    Package = $packageName
                    Version = $packageVersion
                    Path    = $file.FullName
                }
                Write-Host "FOUND: $packageName@$packageVersion" -ForegroundColor Red
                Write-Host "  Path: $($file.FullName)" -ForegroundColor Yellow
                Write-Host ""
            }
        }
    }
    catch {
        # Skip files that can't be parsed
    }
}

# Also search for any React-related packages with RC or canary versions
Write-Host "-------------------------------------------" -ForegroundColor Cyan
Write-Host "Searching for ANY React packages with RC or canary versions..." -ForegroundColor Cyan
Write-Host ""

foreach ($file in $packageFiles) {
    try {
        $content = Get-Content -Path $file.FullName -Raw | ConvertFrom-Json
        $packageName = $content.name
        $packageVersion = $content.version
        
        # Check if it's a React-related package with rc or canary version
        if ($packageName -match "^react" -or $packageName -match "scheduler") {
            if ($packageVersion -match "(rc|canary)") {
                $alreadyFound = $foundVulnerabilities | Where-Object { $_.Path -eq $file.FullName }
                if (-not $alreadyFound) {
                    $foundVulnerabilities += [PSCustomObject]@{
                        Package = $packageName
                        Version = $packageVersion
                        Path    = $file.FullName
                    }
                    Write-Host "FOUND: $packageName@$packageVersion" -ForegroundColor Red
                    Write-Host "  Path: $($file.FullName)" -ForegroundColor Yellow
                    Write-Host ""
                }
            }
        }
    }
    catch {
        # Skip files that can't be parsed
    }
}

# Summary
Write-Host "-------------------------------------------" -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "-------------------------------------------" -ForegroundColor Cyan

if ($foundVulnerabilities.Count -eq 0) {
    Write-Host "No vulnerable packages found!" -ForegroundColor Green
} else {
    Write-Host "Found $($foundVulnerabilities.Count) vulnerable package(s):" -ForegroundColor Red
    $foundVulnerabilities | Format-Table -AutoSize
}