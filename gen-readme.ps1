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

    $PageNum = 1
    do {
        $PageNum
        $Page = Invoke-RestMethod -Headers $Headers -Uri "https://api.github.com/users/$User/starred?per_page=100&page=$PageNum"
        $Starred.Add($Page)
        $PageNum++
    } while ($Page.count -gt 0)

    $ParamsRaw = @{
        StrokeWidth      = 1
        Path             = "wordcloud.svg"
        FocusWord        = 'Security'
        FocusWordAngle   = 0
        ImageSize        = 2048
        InputObject      = $Starred.Topics
        MaxRenderedWords = 254
        ExcludeWord      = 'hacktoberfest'
    }

    New-WordCloud @ParamsRaw

    $YAML = Get-Content content.yml | ConvertFrom-Yaml
    $YAML.Content | Out-File -FilePath README.md -Force -Verbose

    Get-ChildItem $Home -Force

} Catch {
    Write-Output "Ran into an issue: $($PSItem.ToString())"
}
