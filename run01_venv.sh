#!/usr/bin/env bash
#!/usr/bin/env bash
# 仮想環境を有効化するスクリプト（source して使う）
#  source ./run01_venv.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"

if [ ! -f "$ACTIVATE" ]; then
  echo "エラー: 仮想環境の activate スクリプトが見つかりません: $ACTIVATE" >&2
  return 2 2>/dev/null || exit 2
fi

# 実行（サブシェル）ではなく source されていることを確認
if [ "$0" = "$BASH_SOURCE" ]; then
  echo "注意: このスクリプトはシェルを現在のセッションで有効化するために 'source' してください:"
  echo "  source $SCRIPT_DIR/$(basename "$0")"
  exit 3
fi

# shellcheck disable=SC1090
. "$ACTIVATE"
echo ".venv を有効化しました: $ACTIVATE"
