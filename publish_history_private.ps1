param(
    [string]$RepositoryName = "real-estate-image-processor-history",
    [ValidateSet("local", "private")]
    [string]$Mode = "private",
    [string]$CommitMessage = "Update development history"
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name が見つかりません。$InstallHint"
    }
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Require-Command "git" "Git for Windows をインストールしてください。"

# 履歴として管理するファイルだけを明示的に指定します。
$TrackedFiles = @(
    "app.py",
    "processor.py",
    "watcher.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
    ".gitignore",
    "install_requirements.bat",
    "start.bat",
    "docs"
)

# 公開・履歴管理したくないものを強制除外します。
$GitIgnoreContent = @"
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/

# Local settings and secrets
.env
.env.*
*.local
config.local.*
secrets.*

# Images, logos and generated files
logo*.png
logo*.jpg
logo*.jpeg
*.psd
*.ai
*.zip
output/
outputs/
HP/
SUUMO/
logs/
*.log

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
"@

Set-Content -Path ".gitignore" -Value $GitIgnoreContent -Encoding UTF8

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

# すでに追跡されている除外対象があれば、一度インデックスから外します。
git rm -r --cached . 2>$null | Out-Null

$ExistingTrackedFiles = @()
foreach ($Item in $TrackedFiles) {
    if (Test-Path $Item) {
        $ExistingTrackedFiles += $Item
    }
}

if ($ExistingTrackedFiles.Count -eq 0) {
    throw "履歴管理対象のファイルが見つかりません。スクリプトをプロジェクト直下に置いてください。"
}

git add -- $ExistingTrackedFiles

$HasChanges = -not [string]::IsNullOrWhiteSpace((git status --porcelain))
if ($HasChanges) {
    git commit -m $CommitMessage
} else {
    Write-Host "コミット対象の変更はありません。" -ForegroundColor Yellow
}

if ($Mode -eq "local") {
    Write-Host "ローカルGit履歴への保存が完了しました。GitHubには送信していません。" -ForegroundColor Green
    exit 0
}

Require-Command "gh" "GitHub CLI をインストールしてください。"

try {
    gh auth status | Out-Null
} catch {
    gh auth login --web
}

$RemoteExists = -not [string]::IsNullOrWhiteSpace((git remote get-url origin 2>$null))

if (-not $RemoteExists) {
    # 作成履歴用なので、必ず非公開リポジトリとして作成します。
    gh repo create $RepositoryName --private --source . --remote origin --push
} else {
    git push -u origin main
}

Write-Host "非公開GitHubリポジトリへ履歴を保存しました。" -ForegroundColor Green
Write-Host "管理対象: ソースコード、README、仕様書、起動・依存関係ファイルのみ" -ForegroundColor Cyan
Write-Host "除外対象: ロゴ、画像、生成物、ZIP、ログ、秘密情報" -ForegroundColor Cyan
