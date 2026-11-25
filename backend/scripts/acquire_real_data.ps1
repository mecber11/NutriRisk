param([switch]$Refresh)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'data/real'
$raw = Join-Path $out 'raw'
New-Item -ItemType Directory -Force -Path $raw | Out-Null
$sources = [Collections.Generic.List[object]]::new()
function Fetch([string]$Name, [string]$Url) {
    $path = Join-Path $raw ($Name + '.json')
    if ($Refresh -or !(Test-Path -LiteralPath $path)) {
        $ok = $false
        for ($attempt=1; $attempt -le 3; $attempt++) {
            try { Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $path -TimeoutSec 90; $ok=$true; break }
            catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 2 }
        }
    }
    $payload = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($payload.Count -ne 2 -or !$payload[1]) { throw "Invalid API response: $Name" }
    if ($payload[0].pages -gt 1) { throw "Pagination required for $Name; increase per_page" }
    $sources.Add([ordered]@{file=('raw/'+$Name+'.json'); url=$Url; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower(); bytes=(Get-Item -LiteralPath $path).Length; retrieved_utc=(Get-Item -LiteralPath $path).LastWriteTimeUtc.ToString('o'); api_metadata=$payload[0]})
    return $payload[1]
}
$countries = Fetch 'countries' 'https://api.worldbank.org/v2/country?format=json&per_page=400'
$countryMap = @{}
foreach ($country in $countries) { if ($country.region.id -ne 'NA' -and $country.longitude -and $country.latitude) { $countryMap[$country.id] = $country } }
$variables = [ordered]@{
    stunting_prevalence_pct='SH.STA.STNT.ME.ZS'
    gdp_per_capita_constant_usd='NY.GDP.PCAP.KD'
    basic_drinking_water_pct='SH.H2O.BASW.ZS'
    basic_sanitation_pct='SH.STA.BASS.ZS'
    electricity_access_pct='EG.ELC.ACCS.ZS'
    urban_population_pct='SP.URB.TOTL.IN.ZS'
    population_density='EN.POP.DNST'
    fertility_births_per_woman='SP.DYN.TFRT.IN'
    female_secondary_enrollment_pct='SE.SEC.ENRR.FE'
    pm25_exposure='EN.ATM.PM25.MC.M3'
}
$rows = @{}
$indicatorMetadata = [ordered]@{}
foreach ($name in $variables.Keys) {
    $code = $variables[$name]
    Write-Output "Downloading $code ($name)"
    $values = Fetch $code "https://api.worldbank.org/v2/country/all/indicator/${code}?format=json&per_page=20000&date=2000:2024"
    $indicatorMetadata[$name] = @(Fetch ($code+'_metadata') "https://api.worldbank.org/v2/indicator/${code}?format=json&per_page=100")
    foreach ($item in $values) {
        $iso = $item.countryiso3code
        if (!$countryMap.ContainsKey($iso)) { continue }
        $key = "$iso-$($item.date)"
        if (!$rows.ContainsKey($key)) {
            $country=$countryMap[$iso]
            $row=[ordered]@{country_code=$iso; country_name=$country.name; region=$country.region.value; region_code=$country.region.id; period_year=[int]$item.date; latitude=[double]::Parse($country.latitude,[Globalization.CultureInfo]::InvariantCulture); longitude=[double]::Parse($country.longitude,[Globalization.CultureInfo]::InvariantCulture); is_synthetic=$false; source='WORLD_BANK_WDI_JME'}
            foreach ($column in $variables.Keys) { $row[$column]=$null }
            $rows[$key]=$row
        }
        $rows[$key][$name]=$item.value
    }
}
$panel = @($rows.Values | Where-Object {$null -ne $_.stunting_prevalence_pct} | ForEach-Object {[pscustomobject]$_} | Sort-Object country_code,period_year)
if ($panel.Count -lt 500) { throw 'Unexpectedly few observed national target estimates' }
$csv = Join-Path $out 'country_panel.csv'
$panel | Export-Csv -LiteralPath $csv -NoTypeInformation -Encoding UTF8
$missing = [ordered]@{}
foreach ($name in $variables.Keys) { $count=@($panel | Where-Object {$null -eq $_.$name}).Count; $missing[$name]=@{missing=$count; fraction=$count/$panel.Count} }
$years=@($panel.period_year | Sort-Object -Unique)
$coverage=@($panel | Group-Object period_year | ForEach-Object {@{year=[int]$_.Name; countries=$_.Count; complete_predictor_rows=@($_.Group | Where-Object {$r=$_; @($variables.Keys | Where-Object {$_ -ne 'stunting_prevalence_pct' -and $null -eq $r.$_}).Count -eq 0}).Count}})
$manifest=[ordered]@{
    dataset_id='worldbank-jme-country-panel'; created_utc=[DateTime]::UtcNow.ToString('o'); is_synthetic=$false
    unit='country-year'; outcome='JME modeled national prevalence of stunting, percentage children under 5; official estimates derived from surveys, not individual observations'
    countries=@($panel.country_code | Sort-Object -Unique).Count; rows=$panel.Count; years=$years
    target='stunting_prevalence_pct'; target_scale='percentage 0 to 100'; predictors=@($variables.Keys | Where-Object {$_ -ne 'stunting_prevalence_pct'})
    indicators=$variables; indicator_metadata=$indicatorMetadata; missingness=$missing; yearly_coverage=$coverage; sources=$sources
    output=@{file='country_panel.csv'; sha256=(Get-FileHash -LiteralPath $csv -Algorithm SHA256).Hash.ToLower()}
    license='World Bank datasets generally CC BY 4.0 unless indicator-specific terms apply; retain source attribution and check indicator metadata'
    license_url='https://datacatalog.worldbank.org/public-licenses#cc-by'
    methodology_url='https://data.unicef.org/resources/jme/'
    limitations=@('Ecological national analysis; no individual clinical prediction or child-level fairness estimates','JME outcomes are modeled and revised retrospectively; temporal evaluation is retrospective, not a real-time forecasting claim','Latitude/longitude are World Bank capital coordinates, not population centroids or survey clusters','No synthetic filling or interpolation; missing values retained for training-only imputation','No survey weights or microdata available in this panel; countries are equally weighted unless an explicit estimand says otherwise','Country/region identity, coordinates and year are metadata, not default determinants; no anthropometric predictors','Repeated country-years and source smoothing induce dependence; avoid row-wise random splits')
}
$manifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $out 'manifest.json') -Encoding UTF8
Write-Output "Prepared $($panel.Count) real country-year rows, $($manifest.countries) countries, $($years[0])-$($years[-1])."
