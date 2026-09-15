#!/usr/bin/env bash
# Audio 全ファイルを西暦で分け、再生回数ランキングを HTML にする。
# 集計ルールは top-listens.sh / year-tops.jq と同じ。
# 2023 年だけ Relax α Wave と α Healing を順位から除外する。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TRACK_LIMIT=50
ARTIST_LIMIT=50
ALBUM_LIMIT=30
OUT="$ROOT/listening-report.html"

usage() {
  cat <<'EOF'
Usage: make-year-report.sh [options]

Options:
  --tracks N    曲の top N（デフォルト: 50）
  --artists N   アーティストの top N（デフォルト: 50）
  --albums N    アルバムの top N（デフォルト: 30）
  --out path    出力 HTML

アルバムページは Get Track で album.id を解決する。
SPOTIFY_CLIENT_ID と SPOTIFY_CLIENT_SECRET を環境変数か .env に置く。
結果は .spotify-album-cache.json に保存する。
EOF
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tracks)
      TRACK_LIMIT="${2:?}"
      shift 2
      ;;
    --artists)
      ARTIST_LIMIT="${2:?}"
      shift 2
      ;;
    --albums)
      ALBUM_LIMIT="${2:?}"
      shift 2
      ;;
    --out)
      OUT="${2:?}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for label in tracks:"$TRACK_LIMIT" artists:"$ARTIST_LIMIT" albums:"$ALBUM_LIMIT"; do
  name="${label%%:*}"
  value="${label#*:}"
  if ! is_positive_int "$value"; then
    echo "--$name は正の整数にしてください: $value" >&2
    exit 2
  fi
done

shopt -s nullglob
FILES=("$ROOT"/Streaming_History_Audio_*.json)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "Streaming_History_Audio_*.json が見つかりません。" >&2
  exit 1
fi

jq -s \
  --argjson track_limit "$TRACK_LIMIT" \
  --argjson artist_limit "$ARTIST_LIMIT" \
  --argjson album_limit "$ALBUM_LIMIT" \
  -f "$ROOT/scripts/year-tops.jq" \
  "${FILES[@]}" \
  | python3 "$ROOT/scripts/resolve-album-uris.py" \
  | python3 "$ROOT/scripts/render-year-report.py" > "$OUT"

echo "wrote $OUT"
