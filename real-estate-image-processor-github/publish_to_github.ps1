[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$RepositoryName = "real-estate-image-processor",

    [Parameter(Mandatory = $false)]
    [string]$Description = "Windows desktop app that automatically processes real-estate images locally.",

    [Parameter(Mandatory = $false)]
    [ValidateSet("public", "private")]
    [string]$Visibility = "public",

    [Parameter(Mandatory = $false)]
    [string]$Branch = "main",

    [Parameter(Mandatory = $false)]
    [string]$CommitMessage = "Initial public release"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Require-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "'$Name' が見つかりません。$InstallHint"
    }
}

try {
    $ProjectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $ProjectDirectory

    Write-Host "GitHub publish target: $ProjectDirectory" -ForegroundColor Green
    Write-Host "Repository: $RepositoryName ($Visibility)" -ForegroundColor Green

    Require-Command -Name "git" -InstallHint "Git for Windowsをインストールしてください。"
    Require-Command -Name "gh" -InstallHint "GitHub CLIをインストールしてください: winget install --id GitHub.cli"

    Write-Step "GitHub CLIのログイン状態を確認"
    & gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GitHubへのログインが必要です。ブラウザ認証を開始します。" -ForegroundColor Yellow
        & gh auth login --web --git-protocol https
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub CLIの認証に失敗しました。"
        }
    }

    Write-Step "Gitリポジトリを準備"
    if (-not (Test-Path ".git")) {
        & git init
        if ($LASTEXITCODE -ne 0) {
            throw "git init に失敗しました。"
        }
    }

    $UserName = (& git config user.name).Trim()
    $UserEmail = (& git config user.email).Trim()

    if ([string]::IsNullOrWhiteSpace($UserName)) {
        $UserName = Read-Host "Gitの表示名を入力してください"
        & git config user.name $UserName
    }

    if ([string]::IsNullOrWhiteSpace($UserEmail)) {
        $UserEmail = Read-Host "Gitのメールアドレスを入力してください"
        & git config user.email $UserEmail
    }

    Write-Step "公開対象をステージング"
    & git add --all
    if ($LASTEXITCODE -ne 0) {
        throw "git add に失敗しました。"
    }

    & git diff --cached --quiet
    $HasStagedChanges = ($LASTEXITCODE -ne 0)

    if ($HasStagedChanges) {
        Write-Step "コミットを作成"
        & git commit -m $CommitMessage
        if ($LASTEXITCODE -ne 0) {
            throw "git commit に失敗しました。"
        }
    }
    else {
        Write-Host "新しいコミット対象はありません。" -ForegroundColor DarkYellow
    }

    & git branch -M $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "ブランチ名の設定に失敗しました。"
    }

    $OriginUrl = (& git remote get-url origin 2>$null)

    if ([string]::IsNullOrWhiteSpace($OriginUrl)) {
        Write-Step "GitHubリポジトリを作成して初回プッシュ"

        $VisibilityOption = "--$Visibility"
        & gh repo create $RepositoryName `
            $VisibilityOption `
            --description $Description `
            --source . `
            --remote origin `
            --push

        if ($LASTEXITCODE -ne 0) {
            throw "GitHubリポジトリの作成またはプッシュに失敗しました。既に同名のリポジトリがある場合は、RepositoryNameを変更してください。"
        }
    }
    else {
        Write-Step "既存のoriginへプッシュ"
        Write-Host "origin: $OriginUrl"
        & git push -u origin $Branch
        if ($LASTEXITCODE -ne 0) {
            throw "git push に失敗しました。"
        }
    }

    $PublishedUrl = (& gh repo view --json url --jq .url 2>$null).Trim()

    Write-Host "`n公開が完了しました。" -ForegroundColor Green
    if (-not [string]::IsNullOrWhiteSpace($PublishedUrl)) {
        Write-Host $PublishedUrl -ForegroundColor Green
    }
}
catch {
    Write-Host "`n公開処理に失敗しました。" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
