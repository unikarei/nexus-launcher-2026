#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Program Overview
#   run04_tag.sh is the release-oriented Git operation script.
#   It supports two controlled paths:
#     A) changes exist: stage -> commit -> tag -> push branch -> push tag
#     B) no changes:    tag-only on current HEAD -> push branch -> push tag
#   Use this script when tagging/release traceability is required.
# =============================================================================

# このスクリプトは「直接実行」すること（source しない）
if [ "$0" != "${BASH_SOURCE[0]}" ]; then
    printf 'Error: このスクリプトは source ではなく直接実行してください:\n  ./run04_tag.sh\n' >&2
    return 1 2>/dev/null || exit 1
fi

cd "$(dirname "$0")" || exit 1

if ! command -v git >/dev/null 2>&1; then
    echo "[Error] git が見つかりません。" >&2
    exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[Error] このディレクトリは Git リポジトリではありません。" >&2
    exit 1
fi

CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
CUR_BRANCH="${CUR_BRANCH:-main}"
LATEST_TAG="$(git tag --sort=-version:refname 2>/dev/null | head -n1 || true)"
LATEST_TAG="${LATEST_TAG:-v0.0.0}"

cat <<EOF
========================================
           Git Tag Script
========================================
Current branch : $CUR_BRANCH
Latest tag     : $LATEST_TAG

EOF

echo "Staging changes..."
git add -A

if git diff --cached --quiet --exit-code; then
    echo "[Info] No changes to commit."
    read -r -p "Proceed with tag+push on current HEAD without commit? [y/N]: " TAG_ONLY
    case "${TAG_ONLY}" in
        y|Y|yes|YES)
            ;;
        *)
            echo "[Info] Cancelled."
            exit 1
            ;;
    esac
else
    read -r -p "Enter commit message: " COMMIT_MSG
    if [ -z "${COMMIT_MSG// /}" ]; then
        echo "[Error] Commit message cannot be empty." >&2
        exit 1
    fi
    COMMIT_MSG="${COMMIT_MSG//\"/\'}"

    echo "Creating commit..."
    if ! git commit -m "$COMMIT_MSG"; then
        echo "[Error] git commit failed." >&2
        exit 1
    fi
fi

read -r -p "Please enter NEW tag version (ex: v1.2.3): " VERSION
if [ -z "${VERSION// /}" ]; then
    echo "[Error] Version cannot be empty." >&2
    exit 1
fi

# Ensure tag doesn't already exist
if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null 2>&1; then
    echo "[Error] Tag $VERSION already exists." >&2
    exit 1
fi

read -r -p "Enter tag message (annotation): " TAG_MSG
if [ -z "${TAG_MSG// /}" ]; then
    echo "[Error] Tag message cannot be empty." >&2
    exit 1
fi
TAG_MSG="${TAG_MSG//\"/\'}"

echo "Creating annotated tag $VERSION ..."
if ! git tag -a "$VERSION" -m "$TAG_MSG"; then
    echo "[Error] Tag creation failed." >&2
    exit 1
fi

echo "Pushing to origin/$CUR_BRANCH ..."
if ! git push origin "$CUR_BRANCH"; then
    echo
    echo "[Error] git push failed." >&2
    echo "Hint: remote may have commits that are not present locally (non-fast-forward)." >&2
    read -r -p "Force push to overwrite remote history? [y/N]: " ANSWER
    case "${ANSWER}" in
        y|Y|yes|YES)
            echo "Force pushing to origin/$CUR_BRANCH ..."
            if ! git push -f origin "$CUR_BRANCH"; then
                echo "[Error] Force push failed." >&2
                echo "[Info] Try: git pull --rebase origin $CUR_BRANCH then push again." >&2
                exit 1
            fi
            ;;
        *)
            echo "[Info] Cancelled. Try: git pull --rebase origin $CUR_BRANCH then push again."
            exit 1
            ;;
    esac
fi

echo "Pushing tag $VERSION to origin ..."
if ! git push origin "$VERSION"; then
    echo "[Error] Tag push failed." >&2
    exit 1
fi

echo
echo "[Success] Commit/tag/push completed on branch $CUR_BRANCH with tag $VERSION."
exit 0