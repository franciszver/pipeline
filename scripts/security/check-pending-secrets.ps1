# Check pending git changes for sensitive information
param(
    [switch]$Verbose
)

Write-Host "Checking Pending Files for Sensitive Information" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Get all pending files (modified, staged, untracked)
$pendingFiles = @()

# Modified files
$modified = git diff --name-only 2>$null
if ($modified) {
    $pendingFiles += $modified
}

# Staged files
$staged = git diff --cached --name-only 2>$null
if ($staged) {
    $pendingFiles += $staged
}

# Untracked files (excluding .env and other ignored files)
$untracked = git ls-files --others --exclude-standard 2>$null
if ($untracked) {
    $pendingFiles += $untracked
}

$pendingFiles = $pendingFiles | Sort-Object -Unique

if ($pendingFiles.Count -eq 0) {
    Write-Host "No pending files to check." -ForegroundColor Green
    exit 0
}

Write-Host "Found $($pendingFiles.Count) pending file(s) to check" -ForegroundColor Yellow
Write-Host ""

# Patterns to check for
$patterns = @{
    'AWS_ACCESS_KEY' = 'AKIA[0-9A-Z]{16}'
    'AWS_SECRET_KEY' = '[A-Za-z0-9/+=]{40,}'
    'REPLICATE_KEY' = 'r8_[A-Za-z0-9]{32,}'
    'OPENAI_KEY' = 'sk-[a-zA-Z0-9]{32,}'
    'OPENROUTER_KEY' = 'sk-or-v1-[a-zA-Z0-9]{40,}'
    'DATABASE_URL' = 'postgresql[+:]?://[^:]+:[^@\s]+@[^localhost]'
    'PRIVATE_KEY' = '-----BEGIN.*PRIVATE KEY-----'
    'JWT_SECRET' = '(?i)(jwt[_-]?secret|auth[_-]?secret).*[=:]\s*["'']?[A-Za-z0-9]{32,}'
    'BEARER_TOKEN' = 'Bearer\s+[A-Za-z0-9]{32,}'
}

# Exclude patterns (placeholders)
$excludePatterns = @(
    'AKIA_REDACTED',
    'AKIAxxxxxxxx',
    'AKIAIOSFODNN7EXAMPLE',
    'REDACTED.*',
    'your-.*-key',
    'sk-your-',
    'sk-xxxxxxxx',
    'sk-abc123',  # Test example
    'r8_your-',
    'r8_xxxxxxxx',
    'r8_EXAMPLE',
    'r8_YOUR',
    'YOURSECRETKEYGOESHERE',
    'dev-secret-key-change-in-production',
    'postgresql://postgres@localhost',
    'postgresql://user:pass@',
    'postgresql://user:password@localhost',
    'postgresql://.*@localhost',
    'postgresql\+psycopg://postgres@',
    'CHANGE_PASSWORD',
    'YOUR.*KEY',
    'EXAMPLE.*KEY',
    'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',  # AWS example key
    '-----BEGIN.*PRIVATE KEY-----',  # Regex pattern, not actual key
    '=================================================',  # Separator line
    'BEGIN.*PRIVATE KEY',  # Pattern definition
    'postgresql://.*@localhost'  # Pattern definition
)

function Test-IsPlaceholder {
    param([string]$value)
    
    foreach ($pattern in $excludePatterns) {
        if ($value -match $pattern) {
            return $true
        }
    }
    return $false
}

$findings = @()
$checkedCount = 0

foreach ($file in $pendingFiles) {
    if (-not (Test-Path $file)) {
        continue
    }
    
    # Skip binary files and large files
    $ext = [System.IO.Path]::GetExtension($file)
    $binaryExts = @('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.exe', '.dll', '.so', '.dylib')
    if ($binaryExts -contains $ext.ToLower()) {
        continue
    }
    
    try {
        $content = Get-Content -Path $file -Raw -ErrorAction Stop
        $checkedCount++
        
        if ($Verbose) {
            Write-Host "Checking: $file" -ForegroundColor Gray
        }
        
        foreach ($patternName in $patterns.Keys) {
            $pattern = $patterns[$patternName]
            $matches = [regex]::Matches($content, $pattern)
            
            foreach ($match in $matches) {
                $value = $match.Value
                
                # Skip placeholders
                if (Test-IsPlaceholder $value) {
                    continue
                }
                
                # Get line number
                $lineNum = ($content.Substring(0, $match.Index) -split "`r?`n").Count
                
                # Get context (surrounding lines)
                $lines = $content -split "`r?`n"
                $contextStart = [Math]::Max(0, $lineNum - 2)
                $contextEnd = [Math]::Min($lines.Count - 1, $lineNum + 2)
                $context = ($lines[$contextStart..$contextEnd] | ForEach-Object { "  $_" }) -join "`n"
                
                $findings += @{
                    File = $file
                    Type = $patternName
                    Value = $value.Substring(0, [Math]::Min(50, $value.Length))
                    Line = $lineNum
                    Context = $context
                }
            }
        }
    } catch {
        if ($Verbose) {
            Write-Host "  Warning: Could not read $file" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Checked $checkedCount file(s)" -ForegroundColor Gray
Write-Host ""

if ($findings.Count -eq 0) {
    Write-Host "✅ CLEAN - No sensitive information found in pending files!" -ForegroundColor Green
    Write-Host ""
    exit 0
}

Write-Host "⚠️  WARNING: Found $($findings.Count) potential sensitive information item(s)" -ForegroundColor Red
Write-Host ""

# Group by file
$byFile = $findings | Group-Object File

foreach ($group in $byFile) {
    Write-Host "File: $($group.Name)" -ForegroundColor Yellow
    Write-Host "  Findings: $($group.Count)" -ForegroundColor White
    Write-Host ""
    
    foreach ($finding in $group.Group) {
        Write-Host "  Type: $($finding.Type)" -ForegroundColor Cyan
        Write-Host "  Line: $($finding.Line)" -ForegroundColor Gray
        Write-Host "  Value: $($finding.Value)..." -ForegroundColor Red
        Write-Host "  Context:" -ForegroundColor Gray
        Write-Host $finding.Context -ForegroundColor DarkGray
        Write-Host ""
    }
}

Write-Host "⚠️  Review these findings before committing!" -ForegroundColor Red
Write-Host ""
exit 1

