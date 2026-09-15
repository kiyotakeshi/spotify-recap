#!/usr/bin/env bash
# Spotify Extended Streaming History の決定的な top N 集計。
#
# ルール（探索結果を固定したもの）:
#   1. 曲は spotify_track_uri がある再生だけを対象（Podcast / オーディオブックを除外）
#   2. 「一番聴かれた」の主指標は再生回数（レコード件数）
#   3. 曲の識別子は曲名ではなく spotify_track_uri（同名異曲の衝突を避ける）
#   4. アーティストの識別子は master_metadata_album_artist_name
#   5. 同点は ms_played 合計の降順、その後 uri / artist 名の昇順で安定ソート
#   6. skipped や 30 秒未満は除外しない（1再生 = 1回として数える）
#
# 使い方:
#   scripts/top-listens.sh Streaming_History_Audio_2017.json
#   scripts/top-listens.sh Streaming_History_Audio_*.json
#   scripts/top-listens.sh --limit 20 --json Streaming_History_Audio_2017.json
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: top-listens.sh [options] <history.json> [history.json ...]

Options:
  -n, --limit N   top N（デフォルト: 10）
      --json      機械可読な JSON を出す
  -h, --help      このヘルプ
EOF
}

LIMIT=10
JSON_OUT=0
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--limit)
      LIMIT="${2:?--limit には数値が必要}"
      shift 2
      ;;
    --json)
      JSON_OUT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      FILES+=("$@")
      break
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      FILES+=("$1")
      shift
      ;;
  esac
done

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "JSON ファイルを指定してください。" >&2
  usage >&2
  exit 2
fi

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "file not found: $f" >&2
    exit 1
  fi
done

if ! [[ "$LIMIT" =~ ^[1-9][0-9]*$ ]]; then
  echo "--limit は正の整数にしてください: $LIMIT" >&2
  exit 2
fi

JQ_PROG='
def pad2:
  tostring | if length < 2 then "0" + . else . end;

def fmt_ms:
  (. / 1000 | floor) as $sec
  | ($sec / 3600 | floor) as $h
  | (($sec % 3600) / 60 | floor) as $m
  | ($sec % 60) as $s
  | "\($h):\($m | pad2):\($s | pad2)";

def tracks($n):
  map(select(.spotify_track_uri != null))
  | group_by(.spotify_track_uri)
  | map({
      uri: .[0].spotify_track_uri,
      track: .[0].master_metadata_track_name,
      artist: .[0].master_metadata_album_artist_name,
      album: .[0].master_metadata_album_album_name,
      plays: length,
      ms_played: (map(.ms_played) | add)
    })
  | sort_by([-.plays, -.ms_played, .uri])
  | .[0:$n]
  | to_entries
  | map(.value + {
      rank: (.key + 1),
      listen_time: (.value.ms_played | fmt_ms)
    });

def artists($n):
  map(select(.spotify_track_uri != null and .master_metadata_album_artist_name != null))
  | group_by(.master_metadata_album_artist_name)
  | map({
      artist: .[0].master_metadata_album_artist_name,
      plays: length,
      unique_tracks: ([.[].spotify_track_uri] | unique | length),
      ms_played: (map(.ms_played) | add)
    })
  | sort_by([-.plays, -.ms_played, .artist])
  | .[0:$n]
  | to_entries
  | map(.value + {
      rank: (.key + 1),
      listen_time: (.value.ms_played | fmt_ms)
    });

add
| {
    meta: {
      files: $files,
      records: length,
      track_records: ([.[] | select(.spotify_track_uri != null)] | length),
      from: ([.[].ts] | min),
      to: ([.[].ts] | max),
      metric: "plays",
      limit: $limit
    },
    tracks: tracks($limit),
    artists: artists($limit)
  }
'

RESULT="$(jq -s --argjson limit "$LIMIT" --argjson files "$(printf '%s\n' "${FILES[@]}" | jq -R . | jq -s .)" "$JQ_PROG" "${FILES[@]}")"

if [[ "$JSON_OUT" -eq 1 ]]; then
  printf '%s\n' "$RESULT"
  exit 0
fi

jq -r '
  .meta as $m
  | "files: \($m.files | join(" "))",
    "records: \($m.records)  tracks: \($m.track_records)",
    "range: \($m.from) .. \($m.to)",
    "metric: \($m.metric)  limit: \($m.limit)"
' <<<"$RESULT"

echo
echo "=== Top tracks ==="
jq -r '
  (["rank","plays","time","artist","track","album"] | @tsv),
  (.tracks[] | [.rank, .plays, .listen_time, .artist, .track, .album] | @tsv)
' <<<"$RESULT" | column -t -s $'\t'

echo
echo "=== Top artists ==="
jq -r '
  (["rank","plays","time","unique_tracks","artist"] | @tsv),
  (.artists[] | [.rank, .plays, .listen_time, .unique_tracks, .artist] | @tsv)
' <<<"$RESULT" | column -t -s $'\t'
