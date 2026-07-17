不動産画像処理
Windows 上で指定フォルダを監視し、不動産写真をローカル処理して使用するHPためSUUMOの JPEG を自動生成するデスクトップアプリです。外部 API は使用しません。

主な機能
監視フォルダ配下の物件フォルダを自動監視
JPEG / PNG / WebP / BMP / TIFFに対応
EXIF回転、ホワイトバランス、トーンカーブ、彩度・コントラスト・シャープネス補正
1920×1440へ高品質リサイズ＋中央クロップ
HPとSUUMOフォルダを自動作成
SUUMO側だけ任意のlogo.pngを右下へ合成
出力フォルダの再処理を防止
コピー途中のファイルを待ってから処理
元画像が更新された場合だけ再生成
必要な環境
Windows 10 / 11
Python 3.12 または 3.13 推奨
Tkinter（通常はWindows版Pythonに同梱）
セットアップ
リポジトリをZIPで取得、またはクローンします。
install_requirements.batを実行します。
start.batを実行します。
画面から監視フォルダを選択し、「監視開始」を押します。
初期値は次のフォルダです。

%USERPROFILE%\Downloads\ImageInbox
存在しない場合は先に作成しますか、画面から別のフォルダを選択してください。

フォルダ構成例
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
監視フォルダ直下の画像は処理されません。必ず物件フォルダを1件作成してください。

任意のロゴ
公開リポジトリには固有ブランドのロゴを含めません。SUUMO出力にロゴを付ける場合は、プロジェクト直下へ透過PNGをlogo.png置いてください。ファイルがない場合、ロゴ合成はスキップされます。

重要な制限
このアプリはOpenCVとPillowによる評価処理です。生成AIのような意味理解は行わないため、青空化、電線削除、人物削除、家具配置、建物形状の修復などはできません。

また、水平補正機能はコード上に実装されていますが、誤補正を気にするための初期設定では無効です。詳細は仕様書を参照してください。

実行ファイル
app.py: Tkinter GUI
watcher.py: フォルダ監視・重複防止
processor.py: 画像補正・保存・ロゴ合成
requirements.txt: Python依存パッケージ
install_requirements.bat:依存パッケージ導入
start.bat：アプリ起動
ライセンス
MIT License。詳細はLICENSEを参照してください。
