param(
  [string]$Ticker = "",
  [string]$StartDate = "2019-01-01",
  [string]$EndDate = (Get-Date -Format "yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"
Write-Host "Market Research Terminal - Personal Stock Fetcher" -ForegroundColor Cyan
Write-Host "Token is used only in this PowerShell process and is not written to the JSON file." -ForegroundColor DarkGray

if ([string]::IsNullOrWhiteSpace($Ticker)) {
  $Ticker = Read-Host "Stock ticker (e.g. NVDA)"
}
$Ticker = $Ticker.Trim().ToUpperInvariant()
if ($Ticker -notmatch '^[A-Z0-9.\-]{1,12}$') { throw "Invalid ticker format." }

$secure = Read-Host "Tiingo API Token" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
if ([string]::IsNullOrWhiteSpace($token)) { throw "Token is empty." }

$headers = @{ Authorization = "Token $token"; Accept = "application/json" }
$escaped = [Uri]::EscapeDataString($Ticker)
$pricesUrl = "https://api.tiingo.com/tiingo/daily/$escaped/prices?startDate=$StartDate&endDate=$EndDate&format=json"
Write-Host "Fetching $Ticker EOD prices: $StartDate -> $EndDate ..."
$prices = Invoke-RestMethod -Uri $pricesUrl -Headers $headers -Method Get
if (-not $prices -or @($prices).Count -lt 1) { throw "Tiingo returned no EOD prices for $Ticker." }

# Standardized price basis: use provider-adjusted OHLCV when available.
$adjusted = @($prices | ForEach-Object {
  $hasAdj = ($null -ne $_.adjOpen -and $null -ne $_.adjHigh -and $null -ne $_.adjLow -and $null -ne $_.adjClose)
  [ordered]@{
    date = $_.date
    open = if ($hasAdj) { $_.adjOpen } else { $_.open }
    high = if ($hasAdj) { $_.adjHigh } else { $_.high }
    low = if ($hasAdj) { $_.adjLow } else { $_.low }
    close = if ($hasAdj) { $_.adjClose } else { $_.close }
    volume = if ($hasAdj -and $null -ne $_.adjVolume) { $_.adjVolume } else { $_.volume }
    priceBasis = if ($hasAdj) { "provider-adjusted" } else { "raw-fallback" }
  }
})

$fund = $null
$daily = $null
try { $fund = Invoke-RestMethod -Uri "https://api.tiingo.com/tiingo/fundamentals/$escaped/meta" -Headers $headers -Method Get } catch { Write-Host "Fundamentals metadata unavailable; continuing." -ForegroundColor Yellow }
try { $daily = Invoke-RestMethod -Uri "https://api.tiingo.com/tiingo/daily/$escaped" -Headers $headers -Method Get } catch { Write-Host "Daily metadata unavailable; continuing." -ForegroundColor Yellow }
$fundMeta = $fund
if ($fund -is [System.Array] -and $fund.Count -gt 0) { $fundMeta = $fund[0] }

$meta = [ordered]@{
  ticker = $Ticker
  name = if ($daily -and $daily.name) { $daily.name } elseif ($fundMeta -and $fundMeta.name) { $fundMeta.name } else { $Ticker }
  sector = if ($fundMeta -and $fundMeta.sector) { $fundMeta.sector } else { $null }
  industry = if ($fundMeta -and $fundMeta.industry) { $fundMeta.industry } else { $null }
  description = if ($daily -and $daily.description) { $daily.description } else { $null }
  exchangeCode = if ($daily -and $daily.exchangeCode) { $daily.exchangeCode } else { $null }
}

$data = @{}
$data[$Ticker] = $adjusted
$bundle = [ordered]@{
  schema = "MRT-TIINGO-STOCK-BUNDLE-V2"
  provider = "Tiingo EOD"
  price_basis = "provider-adjusted-first"
  symbol = $Ticker
  start = $StartDate
  end = $EndDate
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  meta = $meta
  data = $data
}

$downloads = Join-Path $env:USERPROFILE "Downloads"
if (-not (Test-Path $downloads)) { $downloads = $PSScriptRoot }
$out = Join-Path $downloads ("tiingo_stock_{0}.json" -f $Ticker)
$json = $bundle | ConvertTo-Json -Depth 20
[IO.File]::WriteAllText($out, $json, (New-Object Text.UTF8Encoding($false)))
$token = $null
Write-Host "Done: $out" -ForegroundColor Green
Write-Host "Import this JSON into the Stock Structure Terminal."
