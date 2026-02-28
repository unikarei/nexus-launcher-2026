# WSL環境での起動問題の修正

## 問題の概要

YouTube Transcripterなど、WSL環境で開発したアプリケーションをランチャーから起動できない問題がありました。

### 根本原因

1. **パス形式の不一致**: `apps.yaml`のワークスペースパスが`\\wsl.localhost\Ubuntu\home\...`形式
2. **WSLコマンドでの実行**: WindowsからWSLコマンド（`wsl bash -lc`）を実行する際、このパス形式はWSL内部で認識されない
3. **作業ディレクトリの問題**: `subprocess.Popen`の`cwd`パラメータにWindowsパスを渡していたため、WSL内で正しいディレクトリに移動できなかった

## 実施した修正

### 1. パス変換関数の追加（utils.py）

新しい関数`convert_wsl_network_path_to_linux()`を追加し、WindowsのWSLネットワークパスをLinuxパスに変換：

```python
# 変換例
Input:  \\wsl.localhost\Ubuntu\home\ohide\usr8_work\...
Output: /home/ohide/usr8_work\...
```

### 2. bashコマンド実行時のcd処理（utils.py）

`get_shell_command()`関数を修正し、WSL bash実行時に作業ディレクトリへのcdコマンドを自動追加：

**変更前:**
```python
# WSL bash実行時
executable = 'wsl'
args = ['bash', '-lc', command]
# → cdが含まれていないため、作業ディレクトリが正しく設定されない
```

**変更後:**
```python
# WSL bash実行時、cwdが指定されている場合
executable = 'wsl'
if cwd:
    command = f"cd '{cwd}' && {command}"
args = ['bash', '-lc', command]
# → cd '/home/user/path' && ./start_app.sh のようにcdが自動挿入される
```

### 3. app_manager.pyでのパス変換処理

アプリ起動時にパスを変換：

```python
# 変換前のワークスペースパス（Windows形式）を保持
cwd = resolve_workspace_path(workspace_path)

# bash shell使用時、WSLネットワークパスをLinuxパスに変換
cwd_for_command = cwd
if cmd.shell == 'bash' and detect_os() == 'windows':
    cwd_for_command = convert_wsl_network_path_to_linux(cwd)

# 変換後のパスをコマンドに渡す
executable, args = get_shell_command(cmd.shell, cmd.cmd, cwd_for_command)
```

### 4. subprocess実行時のcwd処理

WSL bash実行時は、cdコマンドで作業ディレクトリを変更するため、`subprocess.Popen`の`cwd`パラメータは`None`を渡す：

```python
# bash on Windowsの場合、cwdはコマンド内のcdで処理されるため、Noneを渡す
process_cwd = None if (cmd.shell == 'bash' and detect_os() == 'windows') else cwd
process = subprocess.Popen(
    full_cmd,
    cwd=process_cwd,  # bash on Windowsの場合はNone
    ...
)
```

## 動作確認方法

### 1. パス変換関数のテスト

```powershell
cd d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher\launcher
python -c "from utils import convert_wsl_network_path_to_linux; test_path = r'\\wsl.localhost\Ubuntu\home\ohide\usr8_work\work_23_chatgpt\16_PoCs\0106_cc-sdd'; print(f'Input: {test_path}'); result = convert_wsl_network_path_to_linux(test_path); print(f'Output: {result}')"
```

**期待される出力:**
```
Input: \\wsl.localhost\Ubuntu\home\ohide\usr8_work\work_23_chatgpt\16_PoCs\0106_cc-sdd
Output: /home/ohide/usr8_work/work_23_chatgpt/16_PoCs/0106_cc-sdd
```

### 2. WSLコマンドの実行テスト

```powershell
wsl bash -lc "cd '/home/ohide/usr8_work/work_23_chatgpt/16_PoCs/0106_cc-sdd' && pwd && ls -la start_app.sh"
```

**期待される動作:**
- 正しいディレクトリに移動
- `start_app.sh`ファイルが表示される

### 3. ランチャーからの起動テスト

1. ランチャーを起動:
   ```powershell
   cd d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher\launcher
   python main.py
   ```

2. ブラウザで http://127.0.0.1:8080 にアクセス

3. YouTube Transcripterの「🚀 Launch」ボタンをクリック

4. ログを確認:
   ```
   [2026-01-12 xx:xx:xx] === Starting YouTube Transcripter ===
   [2026-01-12 xx:xx:xx] Executing: wsl bash -lc cd '/home/ohide/...' && ./start_app.sh --with-frontend
   [2026-01-12 xx:xx:xx] Working directory: \\wsl.localhost\... (command uses: /home/ohide/...)
   ```

   ログに「command uses: /home/ohide/...」と表示されていれば、パス変換が正しく動作しています。

## トラブルシューティング

### Q: まだ起動しない

**確認事項:**

1. **ワークスペースパスが正しいか確認:**
   ```powershell
   # Windows Explorerから確認
   explorer.exe \\wsl.localhost\Ubuntu\home\ohide\usr8_work\work_23_chatgpt\16_PoCs\0106_cc-sdd
   ```

2. **WSL内でstart_app.shが実行可能か確認:**
   ```powershell
   wsl bash -c "cd '/home/ohide/usr8_work/work_23_chatgpt/16_PoCs/0106_cc-sdd' && ls -la start_app.sh"
   ```
   
   実行権限がない場合:
   ```powershell
   wsl bash -c "cd '/home/ohide/usr8_work/work_23_chatgpt/16_PoCs/0106_cc-sdd' && chmod +x start_app.sh"
   ```

3. **ログファイルを確認:**
   ```powershell
   Get-Content d:\usr8_work\work_23_chatgpt\16_PoCs\0000_Launcher\launcher\logs\youtube-transcripter.log -Tail 50
   ```

### Q: Docker関連のエラーが出る

**原因:**
- Docker Desktopが起動していない
- WSL内でDockerが使用できない

**対策:**
1. Docker Desktopを起動
2. Docker DesktopでWSL統合を有効化:
   - Settings → Resources → WSL Integration
   - 使用しているディストリビューション（Ubuntu等）を有効化

3. WSLからDockerが使えるか確認:
   ```powershell
   wsl bash -c "docker --version"
   wsl bash -c "docker ps"
   ```

### Q: ポートが既に使用されている

**対策:**
1. 既存のプロセスを確認して終了:
   ```powershell
   # Windows側
   Get-NetTCPConnection -LocalPort 8000, 3000
   
   # WSL側
   wsl bash -c "lsof -ti:8000,3000 | xargs kill -9"
   ```

2. または、apps.yamlで別のポートを使用するよう変更

## まとめ

この修正により、以下が可能になりました：

✅ Windows環境からWSL内のアプリケーションを起動可能  
✅ `\\wsl.localhost\...`形式のパスを自動的にLinuxパス形式に変換  
✅ WSL bashコマンド実行時の作業ディレクトリの正しい処理  
✅ ログに変換前後のパスを表示してデバッグが容易に  

他のWSL環境で開発したアプリケーションも、同様の方法でランチャーに追加できます。
