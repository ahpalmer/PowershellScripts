# Script to search for .nuget files/folders in Windows
# This searches your entire user profile by default

# Set the starting directory (change this if you want to search elsewhere)
$searchPath = $env:USERPROFILE  # This searches your user folder (C:\Users\YourName)
# To search entire C: drive, use: $searchPath = "C:\"

Write-Host "Searching for .nuget files and folders..." -ForegroundColor Cyan
Write-Host "Starting from: $searchPath" -ForegroundColor Yellow
Write-Host ""

# Search for .nuget folders
Write-Host "=== .nuget Folders ===" -ForegroundColor Green
try {
    $folders = Get-ChildItem -Path $searchPath -Filter ".nuget" -Directory -Recurse -ErrorAction SilentlyContinue
    
    if ($folders) {
        foreach ($folder in $folders) {
            Write-Host "Found: $($folder.FullName)" -ForegroundColor White
        }
        Write-Host "`nTotal folders found: $($folders.Count)" -ForegroundColor Cyan
    } else {
        Write-Host "No .nuget folders found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error searching for folders: $_" -ForegroundColor Red
}

Write-Host ""

# Search for nuget.config files
Write-Host "=== nuget.config Files ===" -ForegroundColor Green
try {
    $configFiles = Get-ChildItem -Path $searchPath -Filter "nuget.config" -File -Recurse -ErrorAction SilentlyContinue
    
    if ($configFiles) {
        foreach ($file in $configFiles) {
            Write-Host "Found: $($file.FullName)" -ForegroundColor White
        }
        Write-Host "`nTotal config files found: $($configFiles.Count)" -ForegroundColor Cyan
    } else {
        Write-Host "No nuget.config files found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error searching for config files: $_" -ForegroundColor Red
}

Write-Host "`nSearch complete!" -ForegroundColor Green

# Also check the common NuGet package cache locations
Write-Host "`n=== Common NuGet Locations ===" -ForegroundColor Magenta
$commonPaths = @(
    "$env:USERPROFILE\.nuget\packages",
    "$env:LOCALAPPDATA\NuGet",
    "$env:APPDATA\NuGet"
)

foreach ($path in $commonPaths) {
    if (Test-Path $path) {
        Write-Host "EXISTS: $path" -ForegroundColor Green
    } else {
        Write-Host "NOT FOUND: $path" -ForegroundColor Gray
    }
}