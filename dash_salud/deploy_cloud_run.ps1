param(
    [string]$ProjectId = "eda-salud-atlantico-2018",
    [string]$Region = "us-east1",
    [string]$ServiceName = "dataviz-salud-atlantico"
)

$ErrorActionPreference = "Stop"
$sourceDir = $PSScriptRoot
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Falta Google Cloud CLI (gcloud) o no está en PATH."
}
foreach ($relativePath in @("data/eda.json", "data/modelo.json", "informe/index.html")) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceDir $relativePath))) {
        throw "Falta $relativePath. Genere los agregados y copie el Bookdown renderizado antes de publicar."
    }
}
$activeAccount = & gcloud auth list --filter="status:ACTIVE" --format="value(account)"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($activeAccount)) {
    throw "Inicie sesión en Google Cloud CLI con gcloud auth login."
}
Write-Host "Publicando $ServiceName en $ProjectId ($Region) con la cuenta $activeAccount"
Push-Location -LiteralPath $sourceDir
try {
    & gcloud run deploy $ServiceName `
        --project $ProjectId `
        --region $Region `
        --source . `
        --platform managed `
        --allow-unauthenticated `
        --port 8080 `
        --cpu 1 `
        --memory 512Mi `
        --min-instances 0 `
        --max-instances 3 `
        --concurrency 40 `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Falló el despliegue en Cloud Run." }
} finally {
    Pop-Location
}
