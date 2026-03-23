"""FastAPI main application for Local Web Launcher."""  # このファイル全体の役割を示すモジュールドキュメント
import asyncio                                           # 非同期処理関連（現状は将来拡張用）
import os                                                # 環境変数取得などOS依存機能を使用
import socket                                            # ポート利用可否チェックに使用
import sys                                               # 異常終了時の終了コード返却に使用
from contextlib import closing                           # ソケットを安全に閉じるために使用
from fastapi import FastAPI, HTTPException, Request      # FastAPI本体とHTTP例外、リクエスト型
from fastapi.responses import HTMLResponse, JSONResponse # HTML/JSONレスポンス型
from fastapi.staticfiles import StaticFiles              # 静的ファイル配信
from fastapi.templating import Jinja2Templates           # Jinja2テンプレート描画
from pydantic import BaseModel                           # APIリクエストのバリデーションモデル
from typing import List, Optional                        # 型ヒント（リスト/オプショナル）
import uvicorn                                           # ASGIサーバー
from pathlib import Path                                 # パス操作

from models import AppDefinition, AppState, StartCommand, HealthCheck, OpenUrl  # 独自データモデル
from config import ConfigManager                         # apps.yaml読み書き管理
from app_manager import AppManager                       # アプリ起動/停止/状態管理


# ============================== FastAPIアプリ本体の初期化 ==============================
# Initialize FastAPI app
app = FastAPI(                                            # FastAPIアプリケーションインスタンスを生成
    title="Nexus Web Launcher",                           # OpenAPIタイトル
    description="Launch and manage local web applications", # OpenAPI説明
    version="1.0.0"                                       # APIバージョン
)

# Setup paths
BASE_DIR = Path(__file__).parent                         # このmain_annotated.pyのあるディレクトリ
TEMPLATE_DIR = BASE_DIR / "templates"                    # テンプレートディレクトリ
STATIC_DIR = BASE_DIR / "static"                         # 静的ファイルディレクトリ

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")  # /staticを配信

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR)) # Jinja2テンプレートローダー作成

# Initialize managers
config_manager = ConfigManager()                         # 設定ファイル管理オブジェクト
app_manager = AppManager()                               # アプリ実行管理オブジェクト


# ============================== フロントエンド配信モード設定 ==============================
# Frontend mode settings
LAUNCHER_ENV = os.environ.get("LAUNCHER_ENV", "development").strip().lower() or "development"  # 開発/本番モード
VITE_HOST = os.environ.get("VITE_HOST", "127.0.0.1").strip() or "127.0.0.1"                     # Viteホスト
try:                                                                                            # VITE_PORTを安全に整数化
    VITE_PORT = int((os.environ.get("VITE_PORT", "5173").strip() or "5173"))                   # Viteポート番号
except ValueError:                                                                               # 数値でないとき
    VITE_PORT = 5173                                                                             # 既定値へフォールバック


# ============================== ユーティリティ関数群 ==============================
# Vite開発サーバー到達性チェック関数

def _is_vite_reachable(host: str = VITE_HOST, port: int = VITE_PORT, timeout_sec: float = 0.15) -> bool:
    """Return True when the Vite dev server is reachable."""      # 関数の説明（英語原文）
    try:                                                             # 接続できるかを試す
        with closing(socket.create_connection((host, int(port)), timeout=timeout_sec)):  # TCP接続を試行
            return True                                              # 成功したら到達可能
    except Exception:                                                # 接続失敗等の例外
        return False                                                 # 到達不可


# テンプレートに渡すフロントエンド文脈情報を作る関数

def _frontend_context() -> dict:
    """Build template context for frontend asset loading.

    Default behavior is development mode. In development mode, Vite is used
    when available; otherwise, static assets are served as a safe fallback.
    """
    env_mode = "development" if LAUNCHER_ENV not in {"production", "prod"} else "production"  # 実行モード正規化
    use_vite = env_mode == "development" and _is_vite_reachable()                               # 開発かつVite到達可なら使用
    vite_origin = f"http://{VITE_HOST}:{VITE_PORT}"                                             # ViteのオリジンURL
    return {                                                                                      # テンプレートへ返す辞書
        "launcher_env": env_mode,                                                                # 正規化済みモード
        "use_vite": use_vite,                                                                    # Vite使用フラグ
        "vite_origin": vite_origin,                                                              # Vite起点URL
    }


# ============================== APIリクエストモデル定義 ==============================
# API Models
class LaunchRequest(BaseModel):                             # 起動/停止などで使う最小リクエスト
    app_id: str                                             # 対象アプリID


class AddAppRequest(BaseModel):                             # アプリ追加用リクエスト
    id: str                                                 # 新規アプリID
    name: str                                               # 表示名
    workspace: str                                          # ワークスペースパス
    start_commands: List[dict]                              # 起動コマンド配列
    health_checks: List[dict]                               # ヘルスチェック配列
    open_urls: List[str]                                    # 起動後に開くURL配列
    ports: List[int]                                        # 利用ポート配列


class UpdateWorkspaceRequest(BaseModel):                    # ワークスペース更新リクエスト
    app_id: str                                             # 対象アプリID
    workspace: str                                          # 更新後ワークスペース


# ============================== ルーティング（APIエンドポイント） ==============================
# Routes
@app.get("/", response_class=HTMLResponse)                 # ルートURLのGET
async def index(request: Request):                          # メイン画面描画
    """Render main launcher page."""                        # 関数説明
    context = {"request": request, **_frontend_context()}   # テンプレート用コンテキスト生成
    return templates.TemplateResponse("index.html", context) # index.htmlを返却


@app.get("/api/apps")                                      # アプリ一覧取得API
async def get_apps():                                       # 全アプリと状態を返す
    """Get all applications and their states."""            # 関数説明
    apps = config_manager.load_apps()                       # 設定ファイルから定義を読み込み

    # Refresh states
    await app_manager.refresh_states(apps)                  # 各アプリ状態を最新化

    # Build response
    result = []                                             # レスポンス配列初期化
    for app in apps:                                        # 各アプリ定義を順に処理
        state = app_manager.get_state(app.id)               # 既存状態を取得
        if not state:                                       # 状態が未初期化なら
            state = app_manager.init_state(app)             # 状態を初期化

        result.append({                                     # API返却形式に整形
            "id": app.id,                                  # ID
            "name": app.name,                              # 名称
            "workspace": app.workspace,                    # ワークスペース
            "status": state.status.value,                  # 状態文字列
            "message": state.message,                      # 補足メッセージ
            "last_check": state.last_check,                # 最終確認時刻
            "ports": app.ports,                            # 利用ポート
            "open_urls": app_manager.resolve_open_urls(app) # 実際に開くURL
        })

    return {"apps": result}                                # JSONで返却


@app.post("/api/apps/launch")                              # アプリ起動API
async def launch_app(request: LaunchRequest):               # 起動処理の入口
    """Launch an application."""                           # 関数説明
    print(f"[DEBUG] Launch request received: app_id={request.app_id}")  # デバッグログ
    apps = config_manager.load_apps()                       # 定義一覧を読み込み
    app = next((a for a in apps if a.id == request.app_id), None)  # app_id一致を検索

    if not app:                                             # 見つからない場合
        raise HTTPException(status_code=404, detail="Application not found")  # 404返却

    result = await app_manager.launch_app(app)              # 実起動処理を委譲

    return result                                           # 実行結果を返却


@app.post("/api/apps/stop")                                # アプリ停止API
async def stop_app(request: LaunchRequest):                 # 停止処理
    """Stop an application."""                             # 関数説明
    success = await app_manager.stop_app(request.app_id)    # 停止を実行

    if success:                                             # 停止成功時
        return {"status": "success", "message": "Application stopped"}  # 成功レスポンス
    else:                                                   # 停止失敗時
        return {"status": "error", "message": "Failed to stop application"}  # 失敗レスポンス


@app.get("/api/apps/{app_id}/logs")                        # ログ取得API
async def get_logs(app_id: str, lines: int = 2000):        # 指定行数のログを返す
    """Get application logs."""                            # 関数説明
    log_content = app_manager.read_log(app_id, lines)       # ログを読み込み

    return {"app_id": app_id, "logs": log_content}       # JSON返却


@app.post("/api/apps/add")                                 # アプリ追加API
async def add_app(request: AddAppRequest):                  # 追加処理
    """Add a new application."""                            # 関数説明
    try:                                                    # バリデーション/保存失敗に備えて例外捕捉
        # Convert request to AppDefinition
        start_commands = [                                 # start_commandsをStartCommand型へ変換
            StartCommand(                                  # 1コマンド分のモデル
                cmd=cmd.get('cmd'),                        # 実行コマンド文字列
                shell=cmd.get('shell', 'bash'),            # シェル種別（既定bash）
                cwd=cmd.get('cwd')                         # 作業ディレクトリ
            )
            for cmd in request.start_commands              # 受信配列を走査
        ]

        health_checks = [                                  # health_checksをHealthCheck型へ変換
            HealthCheck(                                   # 1ヘルスチェック分のモデル
                url=health.get('url'),                     # チェックURL
                timeout_sec=health.get('timeout_sec', 120) # タイムアウト秒（既定120）
            )
            for health in request.health_checks            # 受信配列を走査
        ]

        open_urls = [OpenUrl(url=url) for url in request.open_urls]  # open_urlsをOpenUrl型へ変換

        app = AppDefinition(                               # AppDefinitionを構築
            id=request.id,                                 # ID
            name=request.name,                             # 名称
            workspace=request.workspace,                   # ワークスペース
            start=start_commands,                          # 起動コマンド群
            health=health_checks,                          # ヘルスチェック群
            open=open_urls,                                # 起動後オープンURL群
            ports=request.ports                            # ポート群
        )

        success = config_manager.add_app(app)             # 設定へ追加

        if success:                                        # 追加成功時
            app_manager.init_state(app)                    # メモリ上の状態も初期化
            return {"status": "success", "message": "Application added"}  # 成功レスポンス
        else:                                              # 追加失敗（ID重複等）
            raise HTTPException(status_code=400, detail="Application ID already exists")  # 400返却

    except Exception as e:                                 # 予期した/しないエラー
        raise HTTPException(status_code=400, detail=str(e)) # 400でメッセージ返却


@app.post("/api/apps/update-workspace")                   # ワークスペース更新API
async def update_workspace(request: UpdateWorkspaceRequest): # 更新処理
    """Update application workspace."""                    # 関数説明
    apps = config_manager.load_apps()                      # 現在定義を読み込み
    app = next((a for a in apps if a.id == request.app_id), None)  # 対象アプリ検索

    if not app:                                            # 対象がなければ
        raise HTTPException(status_code=404, detail="Application not found")  # 404返却

    # Update workspace
    app.workspace = request.workspace                      # 定義オブジェクトのworkspaceを更新

    success = config_manager.update_app(app)              # 設定ファイルへ反映

    if success:                                            # 保存成功時
        # Update state
        state = app_manager.get_state(app.id)              # 既存状態取得
        if state:                                          # 状態があれば
            state.workspace = request.workspace            # 状態側のworkspaceも同期

        return {"status": "success", "message": "Workspace updated"}  # 成功レスポンス
    else:                                                  # 保存失敗時
        raise HTTPException(status_code=400, detail="Failed to update workspace")  # 400返却


@app.delete("/api/apps/{app_id}")                         # アプリ削除API
async def delete_app(app_id: str):                        # 削除処理
    """Delete an application."""                          # 関数説明
    # Stop app first if running
    await app_manager.stop_app(app_id)                    # まず停止を試行（起動中対策）

    # Delete from config
    success = config_manager.delete_app(app_id)           # 設定から削除

    if success:                                            # 削除成功時
        # Remove state
        if app_id in app_manager.app_states:              # メモリ状態が残っていれば
            del app_manager.app_states[app_id]            # 状態辞書から削除

        return {"status": "success", "message": "Application deleted"}  # 成功レスポンス
    else:                                                  # 削除対象がない等
        raise HTTPException(status_code=404, detail="Application not found")  # 404返却


@app.get("/api/health")                                  # ランチャー自身のヘルスチェック
async def health_check():                                 # ヘルスチェック処理
    """Health check endpoint for launcher itself."""      # 関数説明
    return {"status": "ok", "message": "Launcher is running"}  # 常時OKを返す


# ============================== アプリ起動エントリポイント ==============================
# 本番実行時のメイン関数

def main():                                                # プログラム起動の主処理
    """Run the launcher."""                               # 関数説明
    host = "127.0.0.1"                                    # バインド先ホスト

    env_port = os.environ.get("LAUNCHER_PORT", "").strip() # 環境変数からポートを取得
    port_was_explicit = bool(env_port)                    # 明示指定の有無を記録
    if env_port:                                           # 文字列がある場合
        try:                                               # 数値変換を試みる
            preferred_port = int(env_port)                # 優先ポート
        except ValueError:                                 # 数値でなければ
            print(f"[ERROR] Invalid LAUNCHER_PORT: {env_port!r}. Must be an integer.")  # エラーメッセージ
            sys.exit(2)                                    # 異常終了
    else:                                                  # 指定がなければ
        preferred_port = 8080                             # 既定ポート

    # ポートが利用可能かを確認する内部関数
    def is_port_available(check_host: str, check_port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # TCPソケット生成
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    # 再利用設定
            try:                                                           # bindで使用可否を確認
                sock.bind((check_host, check_port))                       # バインド試行
            except OSError:                                                # 失敗=使用中
                return False                                               # 利用不可
            return True                                                    # 利用可能

    # 利用可能ポートを選定する内部関数
    def pick_port(check_host: str, start_port: int, max_tries: int = 20) -> int:
        if is_port_available(check_host, start_port):                      # 優先ポートが空いていれば
            return start_port                                              # そのまま採用
        if port_was_explicit:                                              # 明示指定ポートが埋まっていたら
            print(                                                         # ユーザー向けに対処方法を表示
                f"[ERROR] Port {start_port} is already in use. "
                f"Either stop the process using it or choose another port with LAUNCHER_PORT.\n"
                f"        Example (PowerShell):  $env:LAUNCHER_PORT=8081; .\\01_start_launcher.bat\n"
                f"        Example (cmd):        set LAUNCHER_PORT=8081 & 01_start_launcher.bat\n"
                f"        Find PID:             netstat -ano | findstr :{start_port}\n"
                f"        Kill PID:             taskkill /PID <pid> /F"
            )
            sys.exit(1)                                                     # 明示指定時は自動変更せず終了
        for p in range(start_port + 1, start_port + 1 + max_tries):        # 連続探索範囲を走査
            if is_port_available(check_host, p):                            # 空きポート発見時
                print(f"[WARN] Port {start_port} is in use. Using {p} instead.")  # 警告表示
                return p                                                    # 代替ポート採用
        print(f"[ERROR] No free port found in range {start_port}-{start_port + max_tries}.")  # 見つからない場合
        sys.exit(1)                                                         # 異常終了

    port = pick_port(host, preferred_port)             # 実際に使うポートを決定

    print("=" * 60)                                   # 区切り線
    print("  Nexus Web Launcher")                     # タイトル表示
    print("=" * 60)                                   # 区切り線
    print()                                            # 空行
    print(f"  Starting launcher at http://{host}:{port}")  # 起動URL表示
    print("  Press Ctrl+C to stop")                   # 終了方法表示
    print()                                            # 空行
    print("=" * 60)                                   # 区切り線

    uvicorn.run(                                       # Uvicornサーバーを起動
        app,                                           # FastAPIアプリ本体
        host=host,                                     # ホスト
        port=port,                                     # ポート
        log_level="info"                              # ログレベル
    )


# ============================== スクリプト実行判定 ==============================
if __name__ == "__main__":                             # 直接実行時のみ
    main()                                              # メイン関数を呼び出す
