# Agents

Spotify Extended Streaming History の集計を触るときの手順。ランキング規則は推測で書き換えない。実装の正は `scripts/` と `README.md`。

## やること / やらないこと

- 集計してほしいと言われたら、まず `scripts/make-year-report.sh` を実行する。jq や Python で同等の順位を再実装しない
- 規則を変えるのはユーザーが明示したときだけ。変更したら `year-tops.jq` と `top-listens.sh` のコメント、README、このファイルを揃える
- `.env` と `.spotify-album-cache.json` はコミットしない。値をチャットに出さない
- 履歴 JSON の `ip_addr` など個人情報を README やコミットメッセージに書かない
- Spotify Soloist API Key は使わない。アルバム ID は Get Track + Client Credentials
- `open.spotify.com` をスクレイピングしない（429 になる）
- このリポジトリの `Streaming_History_Audio_*.json` は各 100 件サンプル。フル履歴は通常リポジトリ外（例: Downloads の export）にある

## フル履歴でレポートを出す流れ

1. 入力ファイルを確認する。使うのは `Streaming_History_Audio_*.json` だけ。Video JSON は入れない
2. フルデータを使うなら、そのディレクトリを作業ルートにするか、JSON をプロジェクト直下に置く。サンプルの 100 件で `listening-report.html` を上書きしない
3. `.env` があるか見る。無ければ `.env.sample` をコピーするようユーザーに案内する。キーを代わりに発行しない
4. 生成する

```bash
scripts/make-year-report.sh
```

5. stderr で `album.id 解決` または `album.id cache hit` を確認する。HTML のアルバムリンクが `open.spotify.com/album/` になっていることを確認する
6. コミットはユーザーが頼んだときだけ

キャッシュが揃っていれば API は呼ばない。未解決分だけ Get Track する。429 が出たら待つ。並列でトラックページを叩き直さない。

## パイプ（この順を崩さない）

```
jq -s -f scripts/year-tops.jq Streaming_History_Audio_*.json
  | python3 scripts/resolve-album-uris.py
  | python3 scripts/render-year-report.py
  > listening-report.html
```

| 段 | 役割 | ネットワーク |
|---|---|---|
| `year-tops.jq` | 年次 Top JSON。決定的 | なし |
| `resolve-album-uris.py` | 代表曲 URI → `album_uri` | キャッシュミス時のみ |
| `render-year-report.py` | HTML | なし |

単年の Quick 確認だけなら `scripts/top-listens.sh`。アルバムと HTML は出ない。

## 集計ルール（変更禁止の既定）

`top-listens.sh` 先頭コメントと `year-tops.jq` が正。

1. `spotify_track_uri != null` の再生だけ
2. 主指標は再生回数（レコード数）。聴いた時間はタイブレーク
3. 曲 = `spotify_track_uri`（曲名でまとめない）
4. アーティスト = `master_metadata_album_artist_name`
5. アルバム = アーティスト名 × アルバム名。同名異アーティストは別
6. `skipped` も 30 秒未満も除外しない
7. 年はファイル名ではなく `ts` の先頭 4 文字
8. 2023 年だけ順位から `Relax α Wave` と `α Healing` を外す。他年はそのまま。除外件数は `meta` に残す

新しい「一番聴いた」定義（時間合計、ユニーク日数など）を頼まれたら、既存パイプを壊さずオプションにするか、先に方針を確認する。

## リンク

- 曲: `spotify_track_uri` → `https://open.spotify.com/track/{id}`
- アルバム: Get Track の `album.id` → `https://open.spotify.com/album/{id}`
- アルバム URI が履歴に無いので、検索 URL（`/search/…/albums`）は使わない。アーティスト名とアルバム名を連結した検索はヒットしない

アルバム ID の一括取得 `GET /v1/tracks?ids=` は Development Mode では廃止。`GET /v1/tracks/{id}` を 1 曲ずつ。`market` は `.env` の `SPOTIFY_MARKET`（既定 `JP`）。

## よくある依頼

| 依頼 | やること |
|---|---|
| レポート再生成 | フル JSON の場所を確認して `make-year-report.sh` |
| Top N を変える | `--tracks` / `--artists` / `--albums` |
| 除外アーティストを増やす | `year-tops.jq` の `excluded_artists_for` だけ |
| サンプル JSON を小さくする | git 用。フル export は消さない |
| 曲やアルバムに Spotify リンク | 既存の URI / `album_uri` を使う。検索リンクを足さない |

## 触ってよいファイル / 注意

- 規則変更: `scripts/year-tops.jq`（必要なら `top-listens.sh` も）
- HTML 見た目: `scripts/render-year-report.py`
- アルバム解決: `scripts/resolve-album-uris.py`
- 生成物: `listening-report.html`（サンプル JSON から作り直すと中身が変わる）
- 秘密: `.env`（`.gitignore` 済み）
