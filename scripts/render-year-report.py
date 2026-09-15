#!/usr/bin/env python3
"""Render year-tops JSON (stdin) to a self-contained HTML report (stdout)."""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def spotify_open_url(uri: str | None) -> str | None:
    if not uri:
        return None
    parts = uri.split(":")
    if len(parts) != 3 or parts[0] != "spotify" or not parts[2]:
        return None
    return f"https://open.spotify.com/{parts[1]}/{parts[2]}"


def album_open_url(item: dict) -> str | None:
    return spotify_open_url(item.get("album_uri") or item.get("uri"))


def linked(text: str, url: str | None) -> str:
    escaped = e(text)
    if not url:
        return escaped
    return (
        f"<a href='{e(url)}' target='_blank' rel='noopener noreferrer' "
        f"title='Spotify で開く'>{escaped}</a>"
    )


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_range(start: str, end: str) -> str:
    return f"{start[:10]} — {end[:10]}"


def track_rows(tracks: list[dict], album_urls: dict[tuple[str, str], str]) -> str:
    rows = []
    for item in tracks:
        album_url = album_urls.get((item["artist"], item["album"]))
        rows.append(
            "<tr>"
            f"<td class='rank'>{e(item['rank'])}</td>"
            f"<td class='num'>{e(fmt_int(item['plays']))}</td>"
            f"<td class='time'>{e(item['listen_time'])}</td>"
            f"<td>{e(item['artist'])}</td>"
            f"<td class='title'>{linked(item['track'], spotify_open_url(item.get('uri')))}</td>"
            f"<td class='muted'>{linked(item['album'], album_url)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def artist_rows(artists: list[dict]) -> str:
    rows = []
    for item in artists:
        rows.append(
            "<tr>"
            f"<td class='rank'>{e(item['rank'])}</td>"
            f"<td class='num'>{e(fmt_int(item['plays']))}</td>"
            f"<td class='time'>{e(item['listen_time'])}</td>"
            f"<td class='num'>{e(fmt_int(item['unique_tracks']))}</td>"
            f"<td class='title'>{e(item['artist'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def album_rows(albums: list[dict]) -> str:
    rows = []
    for item in albums:
        rows.append(
            "<tr>"
            f"<td class='rank'>{e(item['rank'])}</td>"
            f"<td class='num'>{e(fmt_int(item['plays']))}</td>"
            f"<td class='time'>{e(item['listen_time'])}</td>"
            f"<td class='num'>{e(fmt_int(item['unique_tracks']))}</td>"
            f"<td>{e(item['artist'])}</td>"
            f"<td class='title'>{linked(item['album'], album_open_url(item))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def main() -> None:
    data = json.load(sys.stdin)
    years = data["years"]
    track_limit = data.get("track_limit", data.get("limit", 50))
    artist_limit = data.get("artist_limit", 50)
    album_limit = data.get("album_limit", 30)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    album_urls_by_key: dict[tuple[str, str], str] = {}
    for block in years:
        for item in block.get("albums") or []:
            url = album_open_url(item)
            if url:
                album_urls_by_key[(item["artist"], item["album"])] = url

    nav = []
    for block in years:
        top = block["artists"][0]["artist"] if block["artists"] else "—"
        nav.append(
            f"<a href='#y{e(block['year'])}'>"
            f"<span class='nav-year'>{e(block['year'])}</span>"
            f"<span class='nav-artist'>{e(top)}</span>"
            "</a>"
        )

    sections = []
    for block in years:
        year = block["year"]
        meta = block["meta"]
        note = ""
        excluded = meta.get("excluded_artists") or []
        if excluded:
            names = "、".join(excluded)
            dropped = fmt_int(meta.get("excluded_plays") or 0)
            note = (
                f"<p class='note'>順位から除外: {e(names)}"
                f"（{e(dropped)} 回）</p>"
            )
        sections.append(
            f"""
<section class="year" id="y{e(year)}">
  <header class="year-head">
    <h2>{e(year)}</h2>
    <p>{e(fmt_int(meta['track_records']))} 曲再生
      <span class="dot">·</span> {e(fmt_int(meta['records']))} 件
      <span class="dot">·</span> {e(fmt_range(meta['from'], meta['to']))}</p>
    {note}
    <p class="jumps">
      <a href="#y{e(year)}-albums">アルバム</a>
      <a href="#y{e(year)}-tracks">曲</a>
      <a href="#y{e(year)}-artists">アーティスト</a>
    </p>
  </header>
  <article class="albums" id="y{e(year)}-albums">
    <h3>アルバム Top {e(album_limit)}</h3>
    <table>
      <thead>
        <tr>
          <th>#</th><th>回</th><th>時間</th><th>曲数</th><th>アーティスト</th><th>アルバム</th>
        </tr>
      </thead>
      <tbody>
        {album_rows(block.get('albums') or [])}
      </tbody>
    </table>
  </article>
  <div class="grid">
    <article id="y{e(year)}-tracks">
      <h3>曲 Top {e(track_limit)}</h3>
      <table>
        <thead>
          <tr>
            <th>#</th><th>回</th><th>時間</th><th>アーティスト</th><th>曲</th><th>アルバム</th>
          </tr>
        </thead>
        <tbody>
          {track_rows(block['tracks'], album_urls_by_key)}
        </tbody>
      </table>
    </article>
    <article id="y{e(year)}-artists">
      <h3>アーティスト Top {e(artist_limit)}</h3>
      <table>
        <thead>
          <tr>
            <th>#</th><th>回</th><th>時間</th><th>曲数</th><th>アーティスト</th>
          </tr>
        </thead>
        <tbody>
          {artist_rows(block['artists'])}
        </tbody>
      </table>
    </article>
  </div>
</section>
"""
        )

    print(
        f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spotify 年度別 Top {e(track_limit)}</title>
  <style>
    :root {{
      --bg: #10110f;
      --panel: #181a16;
      --line: #2a2d26;
      --text: #efe8d8;
      --muted: #9a937f;
      --accent: #c8f25a;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(1200px 500px at 10% -10%, #243018 0%, transparent 55%),
        var(--bg);
      font-family: "Hiragino Sans", "Yu Gothic UI", "Helvetica Neue", sans-serif;
      line-height: 1.45;
    }}
    a {{ color: inherit; }}
    code {{
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 0.92em;
      color: var(--text);
    }}
    .wrap {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; }}
    .hero {{
      padding: 48px 0 28px;
      border-bottom: 1px solid var(--line);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: clamp(32px, 6vw, 64px);
      letter-spacing: -0.04em;
      line-height: 1;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      max-width: 46em;
    }}
    nav {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: color-mix(in srgb, var(--bg) 88%, transparent);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
    }}
    nav .wrap {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 12px 0;
    }}
    nav a {{
      flex: 0 0 auto;
      display: grid;
      gap: 2px;
      min-width: 116px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      text-decoration: none;
    }}
    nav a:hover, nav a:focus-visible {{
      border-color: var(--accent);
    }}
    .nav-year {{ font-variant-numeric: tabular-nums; font-weight: 700; }}
    .nav-artist {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .year {{ padding: 36px 0 12px; }}
    .year-head h2 {{
      margin: 0;
      font-size: clamp(40px, 8vw, 80px);
      letter-spacing: -0.06em;
      line-height: 0.9;
    }}
    .year-head p {{
      margin: 10px 0 0;
      color: var(--muted);
    }}
    .year-head .note {{
      color: var(--text);
    }}
    .jumps {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .jumps a {{
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      text-decoration: none;
      font-size: 12px;
    }}
    .dot {{ margin: 0 6px; }}
    .albums {{ margin-top: 22px; }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      margin-top: 18px;
    }}
    article {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
    }}
    article h3 {{
      margin: 0;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 7px 10px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .rank, .num, .time {{
      font-variant-numeric: tabular-nums;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      white-space: nowrap;
    }}
    .rank {{ color: var(--accent); width: 2.2em; }}
    .title {{ font-weight: 650; }}
    .muted {{ color: var(--muted); }}
    td a {{
      color: inherit;
      text-decoration: none;
      border-bottom: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
    }}
    td a:hover, td a:focus-visible {{
      color: var(--accent);
      border-bottom-color: var(--accent);
    }}
    footer {{
      padding: 28px 0 48px;
      color: var(--muted);
      font-size: 13px;
      border-top: 1px solid var(--line);
    }}
    footer code {{
      color: var(--text);
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
    }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <h1>年度別 Top {e(track_limit)}</h1>
      <p>
        Extended Streaming History の Audio 全件を、再生時刻の西暦で集計。
        指標は再生回数。曲 Top {e(track_limit)}、アーティスト Top {e(artist_limit)}、
        アルバム Top {e(album_limit)}。
        曲は <code>spotify_track_uri</code>、
        アーティストは <code>master_metadata_album_artist_name</code>、
        アルバムはアーティスト名とアルバム名の組。
        曲名は URI から Spotify を開き、アルバム名は Get Track で得た <code>album.id</code> から開く。
      </p>
    </div>
  </header>
  <nav>
    <div class="wrap">
      {''.join(nav)}
    </div>
  </nav>
  <main class="wrap">
    {''.join(sections)}
  </main>
  <footer>
    <div class="wrap">
      <p>
        対象は <code>spotify_track_uri</code> がある再生のみ。
        同点は再生時間合計、その後 URI / 名前で安定ソート。
        アルバムは同名異アーティストを分けて数える。
        曲のリンクは <code>https://open.spotify.com/track/…</code>。
        アルバムのリンクは Get Track（<code>GET /v1/tracks/{{id}}</code>）の
        <code>album.id</code> から <code>https://open.spotify.com/album/…</code>。
        取れないときはそのアルバムの最多再生曲を開く。
        2023 年だけ <code>Relax α Wave</code> と <code>α Healing</code> を順位から除外。
        ナビの下段は、その年の最多再生アーティスト。
      </p>
      <p>生成: {e(generated)} / <code>scripts/make-year-report.sh</code></p>
    </div>
  </footer>
</body>
</html>
"""
    )


if __name__ == "__main__":
    main()
