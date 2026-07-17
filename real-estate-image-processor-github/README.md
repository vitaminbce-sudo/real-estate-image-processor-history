# Real Estate Image Processor

Windows上で指定フォルダを監視し、不動産写真をローカル処理して `HP` 用と `SUUMO` 用のJPEGを自動生成するデスクトップアプリです。外部APIは使用しません。

## 主な機能

- 監視フォルダ配下の物件フォルダを自動監視
- JPEG / PNG / WebP / BMP / TIFFに対応
- EXIF回転、ホワイトバランス、トーンカーブ、彩度・コントラスト・シャープネス補正
- 1920×1440へ高品質リサイズ＋中央クロップ
- `HP` と `SUUMO` フォルダを自動作成
- `SUUMO` 側だけ任意の `logo.png` を右下へ合成
- 出力フォルダの再処理を防止
- コピー途中のファイルを待ってから処理
- 元画像が更新された場合だけ再生成

## 必要環境

- Windows 10 / 11
- Python 3.12 または 3.13 推奨
- Tkinter（通常はWindows版Pythonに同梱）

## セットアップ

1. リポジトリをZIPで取得、またはクローンします。
2. `install_requirements.bat` を実行します。
3. `start.bat` を実行します。
4. 画面から監視フォルダを選択し、「監視開始」を押します。

初期値は次のフォルダです。

```text
%USERPROFILE%\Downloads\ImageInbox
```

存在しない場合は先に作成するか、画面から別のフォルダを選択してください。

## フォルダ構成例

```text
ImageInbox/
└─ Property-A/
   ├─ exterior.jpg
   ├─ living.jpg
   ├─ HP/
   │  ├─ exterior.jpg
   │  └─ living.jpg
   └─ SUUMO/
      ├─ exterior.jpg
      └─ living.jpg
```

監視フォルダ直下の画像は処理されません。必ず物件フォルダを1階層作成してください。

## 任意ロゴ

公開リポジトリには固有ブランドのロゴを含めていません。`SUUMO` 出力にロゴを付ける場合は、プロジェクト直下へ透過PNGの `logo.png` を置いてください。ファイルがない場合、ロゴ合成はスキップされます。

## 重要な制限

このアプリはOpenCVとPillowによる画素処理です。生成AIのような意味理解は行わないため、青空化、電線除去、人物削除、家具配置、建物形状の修復などはできません。

また、水平補正機能はコード上に実装されていますが、誤補正を避けるため初期設定では無効です。詳細は [仕様書](docs/SPECIFICATION.md) を参照してください。

## 実行ファイル

- `app.py`: Tkinter GUI
- `watcher.py`: フォルダ監視・重複防止
- `processor.py`: 画像補正・保存・ロゴ合成
- `requirements.txt`: Python依存パッケージ
- `install_requirements.bat`: 依存パッケージ導入
- `start.bat`: アプリ起動

## ライセンス

MIT License。詳細は `LICENSE` を参照してください。

## PowerShellからGitHubへ公開

Git for WindowsとGitHub CLIをインストール後、プロジェクトフォルダ内で次を実行します。

```powershell
PowerShell -ExecutionPolicy Bypass -File .\publish_to_github.ps1
```

既定では、`real-estate-image-processor` という名前の公開リポジトリを作成します。名前や公開範囲を変える場合は引数を指定します。

```powershell
PowerShell -ExecutionPolicy Bypass -File .\publish_to_github.ps1 `
  -RepositoryName "my-image-processor" `
  -Visibility private `
  -Description "Local real-estate image processor"
```

スクリプトは、Git初期化、コミット、GitHub認証、リポジトリ作成、`main` ブランチへのプッシュまで行います。既に `origin` が設定されている場合は、新規リポジトリを作らず既存の接続先へプッシュします。
