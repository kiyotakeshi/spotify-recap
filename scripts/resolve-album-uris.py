#!/usr/bin/env python3
"""Fill album_uri from Spotify Get Track (GET /v1/tracks/{id}).

Reads year-tops JSON on stdin, writes the same JSON with album_uri on stdout.
Lookups are cached in .spotify-album-cache.json next to the history files.

Auth: Client Credentials.
  SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
  or a .env file in the project root.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / ".spotify-album-cache.json"
ENV_PATH = ROOT / ".env"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TRACK_URL = "https://api.spotify.com/v1/tracks/{id}"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def track_id(uri: str) -> str | None:
    parts = uri.split(":")
    if len(parts) == 3 and parts[0] == "spotify" and parts[1] == "track" and parts[2]:
        return parts[2]
    return None


def load_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def save_cache(path: Path, cache: dict[str, str]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    retries: int = 6,
) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                wait = exc.headers.get("Retry-After", "1")
                try:
                    delay = max(1, int(float(wait)))
                except ValueError:
                    delay = 2 ** attempt
                print(f"429; sleep {delay}s", file=sys.stderr)
                time.sleep(delay)
                continue
            if exc.code in {500, 502, 503, 504}:
                time.sleep(min(30, 2 ** attempt))
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"request failed: {url}") from last_error


def access_token(client_id: str, client_secret: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    data = request_json(
        TOKEN_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError("token response had no access_token")
    return str(token)


def album_uri_for_track(token: str, spotify_track_id: str, market: str) -> str | None:
    query = urllib.parse.urlencode({"market": market})
    url = f"{TRACK_URL.format(id=urllib.parse.quote(spotify_track_id))}?{query}"
    try:
        data = request_json(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 400}:
            return None
        raise
    album = data.get("album") or {}
    album_id = album.get("id")
    if not album_id:
        uri = album.get("uri")
        return str(uri) if uri else None
    return f"spotify:album:{album_id}"


def collect_track_uris(payload: dict) -> list[str]:
    uris: list[str] = []
    seen: set[str] = set()
    for block in payload.get("years") or []:
        for item in block.get("albums") or []:
            uri = item.get("uri")
            if uri and uri not in seen:
                seen.add(uri)
                uris.append(uri)
    return uris


def apply_album_uris(payload: dict, mapping: dict[str, str]) -> None:
    for block in payload.get("years") or []:
        for item in block.get("albums") or []:
            album_uri = mapping.get(item.get("uri") or "")
            if album_uri:
                item["album_uri"] = album_uri


def credentials() -> tuple[str, str]:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "Spotify API の資格情報がありません。\n"
            "https://developer.spotify.com/dashboard でアプリを作り、\n"
            "SPOTIFY_CLIENT_ID と SPOTIFY_CLIENT_SECRET を環境変数か "
            f"{ENV_PATH.name} に置いてください。"
        )
    return client_id, client_secret


def main() -> None:
    load_dotenv(ENV_PATH)
    payload = json.load(sys.stdin)
    needed = collect_track_uris(payload)
    cache = load_cache(CACHE_PATH)
    missing = [uri for uri in needed if uri not in cache]
    if missing:
        client_id, client_secret = credentials()
        token = access_token(client_id, client_secret)
        market = os.environ.get("SPOTIFY_MARKET", "JP").strip() or "JP"
        print(f"Get Track: {len(missing)} 件（cache {len(needed) - len(missing)}）", file=sys.stderr)
        for i, uri in enumerate(missing, start=1):
            tid = track_id(uri)
            album_uri = album_uri_for_track(token, tid, market) if tid else None
            if album_uri:
                cache[uri] = album_uri
            if i == 1 or i % 25 == 0 or i == len(missing):
                print(f"  {i}/{len(missing)}", file=sys.stderr)
                save_cache(CACHE_PATH, cache)
            time.sleep(0.05)
        save_cache(CACHE_PATH, cache)
        found = sum(1 for uri in needed if uri in cache)
        print(f"album.id 解決: {found}/{len(needed)}", file=sys.stderr)
    else:
        print(f"album.id cache hit: {len(needed)}", file=sys.stderr)

    apply_album_uris(payload, cache)
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
