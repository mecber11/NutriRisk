param([string]$InputDocx,[string]$OutputPdf)
$ErrorActionPreference='Stop'
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
$word.AutomationSecurity=3
try {
  $document=$word.Documents.Open($InputDocx,$false,$true)
  $document.Repaginate()
  $document.ExportAsFixedFormat($OutputPdf,17)
  $document.Close(0)
} finally { $word.Quit() }
