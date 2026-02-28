# Local Web Launcher

🚀 複数のローカルWebアプリケーションを管理・起動するためのランチャーツールです。

## 概要

Local Web Launcherは、複数のローカル開発環境（YouTube Transcripter等）を統一的に管理し、ボタンクリックで起動・再利用・表示を可能にします。

### 主な機能

- ✨ **ワンクリック起動**: ボタンを押すだけでアプリを起動
- 🔍 **自動ヘルスチェック**: アプリの起動状態を自動監視
- 📊 **状態管理**: Stopped/Starting/Running/Errorの状態表示
- 📝 **ログ表示**: 各アプリのログを直接確認
- ⚙️ **簡単設定**: YAMLファイルまたはUIから設定
- 🔄 **自動リフレッシュ**: 10秒ごとに状態を自動更新
- 🖥️ **Windows/WSL対応**: 両環境で動作

## セットアップ

### 1. 前提条件

- Python 3.8以上
- pip
- （オプション）WSL2（bash使用時）

### 2. インストール

```powershell
# ランチャーディレクトリに移動
cd d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher\launcher

# 依存パッケージをインストール
pip install -r requirements.txt
```

#### フロントエンド（Vite, 開発時HMR）

```powershell
cd d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher\launcher
npm install
```

- デフォルト動作は **開発モード**（`LAUNCHER_ENV=development`）です。
- 開発モードでは、Viteサーバー（`http://127.0.0.1:5173`）が起動していれば自動でViteアセットを使用します。
- Viteが未起動の場合は、自動で従来の`/static`配信にフォールバックします。

### 3. アプリケーション設定

`apps.yaml` を編集して、管理したいアプリケーションを定義します：

```yaml
- id: youtube-transcripter
  name: YouTube Transcripter
  workspace: "C:\\path\\to\\0106_cc-sdd"   # 実際のパスに変更
  start:
    - cmd: "./start_app.sh"
      shell: bash
      cwd: "{workspace}"
    - cmd: "docker compose up -d frontend"
      shell: bash
      cwd: "{workspace}"
  health:
    - url: "http://127.0.0.1:8000/health"
      timeout_sec: 120
  open:
    - url: "http://127.0.0.1:3000"
    - url: "http://127.0.0.1:8000/docs"
  ports:
    - 3000
    - 8000
```

#### 設定項目の説明

- **id**: アプリの一意な識別子（英数字、ハイフン可）
- **name**: 表示名
- **workspace**: アプリのルートディレクトリ（絶対パス）
- **start**: 起動コマンドのリスト
  - **cmd**: 実行コマンド
  - **shell**: シェルタイプ（bash/powershell/cmd）
  - **cwd**: 作業ディレクトリ（`{workspace}`で置換可能）
- **health**: ヘルスチェックURLのリスト
  - **url**: ヘルスチェックエンドポイント
  - **timeout_sec**: タイムアウト時間（秒）
- **open**: 起動後に開くURLのリスト
- **ports**: 使用するポート番号のリスト

## 起動方法

### まずはこれだけ（推奨 / 定型手順）

Windowsでは、Docker Desktop と WSL 統合の都合で「Dockerが起動していないとYouTube Transcripterが上がらない」ことがあります。

本リポジトリでは、以下のバッチを **1つ実行するだけ** で:

- 必要なら Docker Desktop を起動
- Docker Engine が応答するまで待機
- Launcher を起動

…まで行います。

```powershell
cd d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher
.\01_start_launcher.bat
```

起動後は、ブラウザで `http://127.0.0.1:8080` を開き、対象アプリの「Launch」を押すだけです。

#### ポート(8080)が使用中で起動できない場合

`[Errno 10048] ... bind on address ('127.0.0.1', 8080)` が出る場合、すでに別のプロセスが 8080 を使っています。

- 対処A: ランチャーのポートを変更して起動
  - PowerShell:

    ```powershell
    $env:LAUNCHER_PORT=8081
    .\01_start_launcher.bat
    ```

  - cmd:

    ```bat
    set LAUNCHER_PORT=8081
    01_start_launcher.bat
    ```

- 対処B: 8080 を使っているプロセスを終了

  ```bat
  netstat -ano | findstr :8080
  taskkill /PID <pid> /F
  ```

### ランチャーを起動

```powershell
cd launcher
python main.py
```

### Vite開発モードの起動（推奨）

ターミナル1（FastAPI）:

```powershell
cd launcher
set LAUNCHER_ENV=development
python main.py
```

ターミナル2（Vite）:

```powershell
cd launcher
npm run dev
```

### 本番モード（静的配信）

```powershell
cd launcher
set LAUNCHER_ENV=production
python main.py
```

起動すると、以下のように表示されます：

```
============================================================
  Local Web Launcher
============================================================

  Starting launcher at http://127.0.0.1:8080
  Press Ctrl+C to stop

============================================================
```

### ブラウザでアクセス

ブラウザで以下のURLを開きます：

```
http://127.0.0.1:8080
```

※ `LAUNCHER_PORT` を指定して起動した場合は、そのポート番号に読み替えてください。

## 使い方

### アプリの起動

1. ランチャー画面でアプリカードを探す
2. 「🚀 Launch」ボタンをクリック
3. 状態が「Starting」→「Running」に変わる
4. 自動的にブラウザで対象アプリが開く

### アプリの停止

1. 「⏹️ Stop」ボタンをクリック
2. プロセスが終了し、状態が「Stopped」になる

### ワークスペースの編集

1. 「✏️ Edit」ボタンをクリック
2. ワークスペースパスを変更
3. 「Save」をクリック

### ログの確認

1. 「📋 Logs」ボタンをクリック
2. モーダルでログ内容を確認
3. 最新2000行が表示される

### 新しいアプリの追加

#### 方法1: UIから追加

1. 右上の「➕ Add App」ボタンをクリック
2. フォームに必要情報を入力：
   - ID（例: my-app）
   - Name（例: My Application）
   - Workspace Path
   - Ports
   - Health Check URL
   - Open URLs（改行区切り）
   - Start Command
   - Shell Type
3. 「Add Application」をクリック

#### 方法2: apps.yamlを直接編集

1. `launcher/apps.yaml` をテキストエディタで開く
2. 新しいアプリ定義を追加
3. ランチャーを再起動、または「🔄 Refresh」をクリック

### アプリの削除

1. 「🗑️ Delete」ボタンをクリック
2. 確認ダイアログで「OK」をクリック
3. アプリが削除される（apps.yamlから削除）

## 起動の仕組み

### 1. ヘルスチェック

Launchボタンを押すと、まずヘルスチェックを実行：

```
GET http://localhost:8000/health
```

- **成功**: すでに起動中 → すぐにURLを開く
- **失敗**: 未起動 → 起動処理を開始

### 2. 起動処理

未起動の場合、以下の手順で起動：

1. ワークスペースの存在確認
2. `start.cmd` を実行（非同期）
3. ログファイルに出力を記録（`logs/{app_id}.log`）
4. 定期的にヘルスチェックをポーリング
5. 成功したら状態を「Running」にしてURLを開く
6. タイムアウトしたら状態を「Error」にする

### 3. プロセス管理

- 起動したプロセスは `AppManager` が追跡
- Stopボタンで親プロセスと子プロセスをすべて終了
- プロセスが残っている場合は強制終了（kill）

## ファイル構成

```
launcher/
├── main.py              # FastAPIアプリケーション本体
├── models.py            # データモデル（Pydantic）
├── app_manager.py       # アプリ起動/ヘルスチェック/状態管理
├── config.py            # apps.yaml読み書き
├── utils.py             # OS判定、パス処理
├── requirements.txt     # 依存パッケージ
├── apps.yaml            # アプリ定義（ユーザー編集）
├── logs/                # アプリごとのログ
│   ├── youtube-transcripter.log
│   └── ...
├── templates/
│   └── index.html       # メインUI
└── static/
    ├── style.css        # スタイルシート
    └── app.js           # フロントエンドロジック
```

## トラブルシュート

### Q: アプリが起動しない

**確認事項：**

1. **ワークスペースパスは正しいか？**
   - Editボタンで確認・修正
   - Windowsパス: `C:\\path\\to\\app`
   - WSLパス: `/home/user/app` または `/mnt/c/path/to/app`

2. **起動スクリプトは存在するか？**
   - `start_app.sh` 等のファイルがワークスペース内にあるか確認
   - 実行権限があるか確認（WSL: `chmod +x start_app.sh`）

3. **ポートは空いているか？**
   - 他のプロセスが同じポートを使用していないか確認
   - PowerShell: `netstat -ano | findstr :8000`
   - WSL: `netstat -tulpn | grep 8000`

4. **ログを確認**
   - Logsボタンでエラーメッセージを確認
   - `launcher/logs/{app_id}.log` を直接確認

### Q: ヘルスチェックがタイムアウトする

**原因：**

- アプリの起動に時間がかかる
- ヘルスチェックURLが間違っている
- ファイアウォールやネットワーク設定

**対策：**

1. `apps.yaml` の `timeout_sec` を増やす：

```yaml
health:
  - url: "http://localhost:8000/health"
    timeout_sec: 300  # 5分に延長
```

2. ヘルスチェックURLを確認：

```powershell
# 手動でアクセスしてみる
curl http://localhost:8000/health
```

3. アプリが正常に起動しているか確認：

```powershell
# プロセスを確認
Get-Process | Where-Object {$_.Path -like "*python*"}
```

### Q: WSLでbashコマンドが動かない

**確認事項：**

1. WSL2がインストールされているか：

```powershell
wsl --list --verbose
```

2. `shell: bash` の場合、ランチャーは `wsl bash -lc "command"` を実行
3. WSLの既定ディストリビューションを確認：

```powershell
wsl --set-default Ubuntu
```

### Q: Stopボタンが効かない

**原因：**

- プロセスが正しく追跡されていない
- 子プロセスが残っている

**対策：**

1. 手動でプロセスを終了：

```powershell
# PowerShell
Get-Process | Where-Object {$_.Path -like "*アプリ名*"} | Stop-Process -Force

# WSL
pkill -f "アプリ名"
```

2. ポートを使用しているプロセスを特定して終了：

```powershell
# PowerShell
$port = 8000
$processId = (Get-NetTCPConnection -LocalPort $port).OwningProcess
Stop-Process -Id $processId -Force

# WSL
lsof -ti:8000 | xargs kill -9
```

### Q: ログが文字化けする

**対策：**

- ログファイルは UTF-8 で保存されています
- テキストエディタで UTF-8 として開く
- `logs/{app_id}.log` を直接確認

### Q: ランチャー自体が起動しない

**確認事項：**

1. Python/pipが正しくインストールされているか：

```powershell
python --version
pip --version
```

2. 依存パッケージがインストールされているか：

```powershell
pip list | Select-String "fastapi|uvicorn|pydantic|pyyaml|aiohttp|psutil|jinja2"
```

3. ポート8080が空いているか：

```powershell
netstat -ano | findstr :8080
```

別のポートを使用する場合：

```python
# main.py の最後を編集
uvicorn.run(
    app,
    host="127.0.0.1",
    port=9090,  # ポート番号を変更
    log_level="info"
)
```

## 高度な設定

### 複数のstartコマンド

バックエンドとフロントエンドを別々に起動する場合：

```yaml
start:
  - cmd: "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
    shell: powershell
    cwd: "{workspace}/backend"
  - cmd: "npm run dev"
    shell: powershell
    cwd: "{workspace}/frontend"
```

### 複数のヘルスチェック

複数のエンドポイントをチェックする場合（最初に成功したらOK）：

```yaml
health:
  - url: "http://localhost:8000/health"
    timeout_sec: 60
  - url: "http://localhost:3000"
    timeout_sec: 60
```

### 環境変数の指定

コマンド内で環境変数を設定：

```yaml
start:
  - cmd: "export PORT=8000 && python run.py"
    shell: bash
    cwd: "{workspace}"
```

PowerShellの場合：

```yaml
start:
  - cmd: "$env:PORT=8000; python run.py"
    shell: powershell
    cwd: "{workspace}"
```

### WSLパスの自動変換

`utils.py` が自動的にパスを変換：

- Windowsパス `C:\path` → WSL `/mnt/c/path`
- WSLパス `/home/user` → Windows `\\wsl$\Ubuntu\home\user`

## セキュリティ

- ランチャーは `127.0.0.1` にバインド（外部公開されない）
- コマンドインジェクション対策済み
- 設定ファイルはローカルのみアクセス可能
- **注意**: ローカル環境専用のため、本番環境では使用しないこと

## ライセンス

MIT License

## サポート

問題が発生した場合：

1. Logsボタンでエラーを確認
2. `launcher/logs/` 内のログファイルを確認
3. ランチャーのコンソール出力を確認
4. GitHub Issuesで報告

## 開発

### テスト実行

```powershell
# 単体テスト（今後追加予定）
pytest tests/
```

### 開発モード

```powershell
# ホットリロード有効
uvicorn main:app --reload --host 127.0.0.1 --port 8080
```

---

**Happy Launching! 🚀**
