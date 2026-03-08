# Test POST /v1/analyze. Run backend first: uvicorn snapdish.main:app --port 8000
# Usage: .\test_analyze.ps1
#        .\test_analyze.ps1 -Text "How do I make carbonara?"
#        .\test_analyze.ps1 -Uri "https://api.example.com"
param(
  [string]$Text = "I have tomatoes, garlic, olive oil, and pasta. Make dinner for 2 in 20 minutes.",
  [string]$SafetyIdentifier = "demo_user_123",
  [string]$Uri = ($env:SNAPDISH_API_URL ?? "http://127.0.0.1:8000")
)

$ErrorActionPreference = 'Stop'
$base = $Uri.TrimEnd('/')
$url = "$base/v1/analyze"
$body = @{ user_text = $Text; safety_identifier = $SafetyIdentifier } | ConvertTo-Json

try {
  $response = Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json' -Body $body
  $response | ConvertTo-Json -Depth 10
} catch {
  $statusCode = $null
  if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
  Write-Host "HTTP status: $statusCode" -ForegroundColor Red
  if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message -ForegroundColor Red }
  exit 1
}
