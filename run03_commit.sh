#!/usr/bin/env bash
set -euo pipefail

# このスクリプトは「直接実行」すること（source しない）
if [ "$0" != "$BASH_SOURCE" ]; then
    echo "Error: このスクリプトは source ではなく直接実行してください:" >&2
    echo "  ./run03_commit.sh" >&2
    return 1 2>/dev/null || exit 1
fi

# プロジェクトルートへ移動
cd "$(dirname "$0")" || exit 1

# git が使えるか
if ! command -v git >/dev/null 2>&1; then
    echo "[Error] git が見つかりません。" >&2
    exit 1
fi

# Git リポジトリ内か確認
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[Error] このディレクトリは Git リポジトリではありません。" >&2
    exit 1
fi

# 現在のブランチ
CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
CUR_BRANCH="${CUR_BRANCH:-main}"

# 最新タグ（参考）
LATEST_TAG="$(git tag --sort=-version:refname 2>/dev/null | head -n1 || true)"
LATEST_TAG="${LATEST_TAG:-v0.0.0}"

cat <<EOF
========================================
           Git Commit Script
========================================
Current branch : $CUR_BRANCH
Latest tag     : $LATEST_TAG

EOF

# コミットメッセージを対話で取得
read -r -p "Enter commit message: " COMMIT_MSG
if [ -z "${COMMIT_MSG// /}" ]; then
    echo "[Error] Commit message を入力してください。" >&2
    exit 1
fi
# ダブルクォートをシングルに置換（安全対策）
COMMIT_MSG="${COMMIT_MSG//\"/\'}"

echo
echo "Staging changes..."
git add -A

# ステージされた差分が無ければ終了
if git diff --cached --quiet --exit-code; then
    echo "[Info] コミットする変更がありません。"
    exit 0
fi

echo "Creating commit..."
if ! git commit -m "$COMMIT_MSG"; then
    echo "[Error] git commit に失敗しました。" >&2
    exit 1
fi

echo "Pushing to origin/$CUR_BRANCH ..."
if ! git push origin "$CUR_BRANCH"; then
    echo
    echo "[Error] git push に失敗しました。" >&2
    echo "ヒント: リモートに先行コミットがあり、non-fast-forward 拒否の可能性があります。" >&2
    read -r -p "リモートの履歴を上書きして強制プッシュしますか？ [y/N]: " ANSWER
    case "${ANSWER}" in
        y|Y|yes|YES)
            echo "Force pushing to origin/$CUR_BRANCH ..."
            if git push -f origin "$CUR_BRANCH"; then
                echo
                echo "[Success] Force push completed on branch $CUR_BRANCH."
            else
                echo "[Error] Force push に失敗しました。" >&2
                echo "[Info] 代替案: git pull --rebase origin $CUR_BRANCH を実行してから再度 push してください。" >&2
                exit 1
            fi
            ;;
        *)
            echo "[Info] 中止しました。代替案: git pull --rebase origin $CUR_BRANCH を実行してから再度 push してください。"
            exit 1
            ;;
    esac
fi

echo
echo "[Success] Commit and push completed on branch $CUR_BRANCH."
echo "(タグ付けは別スクリプトで行ってください。)"
exit 0