# ============================================================================
# Windows PowerShell - Set Environment Variables
# ============================================================================
# 
# HOW TO USE:
# 1. Open PowerShell in your project directory
# 2. Replace the placeholder values below with your actual values
# 3. Run this script: .\set-env.ps1
# 4. Then run: python run.py
#
# ============================================================================

# Set Flask environment
$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "development"
$env:SECRET_KEY = "dev-secret-key-for-local-testing-only"

# Set Turso database credentials
# ⚠️ IMPORTANT: Replace these with your actual Turso credentials!
$env:TURSO_DATABASE_URL = "https://edushare-attastudy7-sudo.aws-us-west-2.turso.io"
$env:TURSO_AUTH_TOKEN = "YOUR_NEW_TOKEN_HERE"

# Confirm variables are set
Write-Host "✅ Environment variables set!" -ForegroundColor Green
Write-Host ""
Write-Host "FLASK_APP = $env:FLASK_APP"
Write-Host "FLASK_ENV = $env:FLASK_ENV"
Write-Host "TURSO_DATABASE_URL = $env:TURSO_DATABASE_URL"
Write-Host "TURSO_AUTH_TOKEN = [HIDDEN]"
Write-Host ""
Write-Host "You can now run: python run.py" -ForegroundColor Cyan