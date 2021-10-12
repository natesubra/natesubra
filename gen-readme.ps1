#Requires -Version 7
#Requires -Module PSWordCloud
#Requires -Module powershell-yaml

Try {

    $User = ($env:GITHUB_REPOSITORY -split '/')[0]
    $Pair = "$($User):$($Token)"
    $encodedCreds = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($Pair))
    $basicAuthValue = "Basic $encodedCreds"
    $Starred = [System.Collections.Generic.List[System.Object]]::new()
    $Headers = @{
        Accept        = "application/vnd.github.v3+json"
        Authorization = $basicAuthValue
    }

    $outputPath = "$HOME\output"

    $PageNum = 1
    do {
        $PageNum
        $Page = Invoke-RestMethod -Headers $Headers -Uri "https://api.github.com/users/$User/starred?per_page=100&page=$PageNum"
        $Starred.Add($Page)
        $PageNum++
    } while ($Page.count -gt 0)

    New-Item -ItemType Directory -Name $outputPath -Force -Verbose

    $ParamsRaw = @{
        StrokeWidth      = 1
        StrokeColor      = 'MidnightBlue'
        Path             = "${outputPath}\wordcloud.svg"
        FocusWord        = 'Security'
        FocusWordAngle   = 0
        ImageSize        = "480x800"
        InputObject      = $Starred.Topics
        MaxRenderedWords = 100
        ColorSet         = '*blue*', '*red*', '*purple*'
    }

    New-WordCloud @ParamsRaw

    $YAML = Get-Content content.yml | ConvertFrom-Yaml
    $YAML.Content | Out-File -FilePath "${outputPath}\README.md" -Force -Verbose

} Catch {
    Write-Output "Ran into an issue: $($PSItem.ToString())"
}
