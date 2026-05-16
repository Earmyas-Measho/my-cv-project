# One-time setup
$jobDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $jobDir

if (-not (Test-Path "environment.env")) {
    if (Test-Path "environment.env.example") {
        Copy-Item "environment.env.example" "environment.env"
        Write-Host "Created environment.env — open it and paste your API keys."
    }
}

pip install -r requirements.txt

Write-Host ""
Write-Host "Env file:  environment.env  (must contain APIFY_TOKEN and MISTRAL_API_KEY)"
Write-Host ""
Write-Host "Test run:"
Write-Host "  python jobsearch.py --use-cache --max-jobs 5 --dry-run"
