param(
  [string]$Text = "I have tomatoes, garlic, olive oil, and pasta. Make dinner for 2 in 20 minutes.",
  [string]$SafetyIdentifier = "demo_user_123"
)

$ErrorActionPreference = 'Stop'

$body = @{ user_text = $Text; safety_identifier = $SafetyIdentifier } | ConvertTo-Json

try {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/analyze -ContentType 'application/json' -Body $body |
    ConvertTo-Json -Depth 10
} catch {
  "Status: {0}" -f $_.Exception.Response.StatusCode
  $_.ErrorDetails.Message
  exit 1
}
