def pad2:
  tostring | if length < 2 then "0" + . else . end;

def fmt_ms:
  (. / 1000 | floor) as $sec
  | ($sec / 3600 | floor) as $h
  | (($sec % 3600) / 60 | floor) as $m
  | ($sec % 60) as $s
  | "\($h):\($m | pad2):\($s | pad2)";

def rank_tracks($n):
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

def rank_artists($n):
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

def rank_albums($n):
  map(select(
      .spotify_track_uri != null
      and .master_metadata_album_album_name != null
      and .master_metadata_album_artist_name != null
    ))
  | group_by([.master_metadata_album_artist_name, .master_metadata_album_album_name])
  | map(
      . as $rows
      | {
          artist: $rows[0].master_metadata_album_artist_name,
          album: $rows[0].master_metadata_album_album_name,
          uri: (
            $rows
            | group_by(.spotify_track_uri)
            | map({
                uri: .[0].spotify_track_uri,
                plays: length,
                ms_played: (map(.ms_played) | add)
              })
            | sort_by([-.plays, -.ms_played, .uri])
            | .[0].uri
          ),
          plays: ($rows | length),
          unique_tracks: ([$rows[].spotify_track_uri] | unique | length),
          ms_played: ($rows | map(.ms_played) | add)
        }
    )
  | sort_by([-.plays, -.ms_played, .artist, .album])
  | .[0:$n]
  | to_entries
  | map(.value + {
      rank: (.key + 1),
      listen_time: (.value.ms_played | fmt_ms)
    });

# 2023 だけ環境音系を順位から外す。他年はそのまま残す。
def excluded_artists_for($year):
  if $year == "2023" then
    ["Relax α Wave", "α Healing"]
  else
    []
  end;

def drop_artists($names):
  if ($names | length) == 0 then
    .
  else
    map(select(.master_metadata_album_artist_name as $a | $names | index($a) | not))
  end;

def year_block($tn; $an; $aln):
  .[0].ts[0:4] as $year
  | excluded_artists_for($year) as $excl
  | . as $rows
  | ($rows | drop_artists($excl)) as $ranked
  | {
      year: $year,
      meta: {
        records: ($rows | length),
        track_records: ([$rows[] | select(.spotify_track_uri != null)] | length),
        from: ([$rows[].ts] | min),
        to: ([$rows[].ts] | max),
        excluded_artists: $excl,
        excluded_plays: ([$rows[] | select(.master_metadata_album_artist_name as $a | $excl | index($a) != null)] | length)
      },
      tracks: ($ranked | rank_tracks($tn)),
      artists: ($ranked | rank_artists($an)),
      albums: ($ranked | rank_albums($aln))
    };

add
| group_by(.ts[0:4])
| map(year_block($track_limit; $artist_limit; $album_limit))
| sort_by(.year)
| {
    metric: "plays",
    track_limit: $track_limit,
    artist_limit: $artist_limit,
    album_limit: $album_limit,
    years: .
  }
