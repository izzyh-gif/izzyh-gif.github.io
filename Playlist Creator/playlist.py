"""Interactive playlist creator: add your own songs, then search them by vibe.

Run from anywhere:  python "Playlist Creator/playlist.py"
"""
import csv
import re
from pathlib import Path

import chromadb

HERE = Path(__file__).parent
client = chromadb.PersistentClient(path=str(HERE / "chroma_store"))
collection = client.get_or_create_collection(name="songs")

# CSV column -> metadata key for numeric audio features (only present for CSV imports).
FLOAT_FIELDS = {
    "Danceability": "danceability",
    "Energy": "energy",
    "Valence": "valence",
    "Tempo": "tempo",
    "Acousticness": "acousticness",
    "Speechiness": "speechiness",
    "Instrumentalness": "instrumentalness",
    "Loudness": "loudness",
}


# ---------- core logic (no input()/print here, so it can be reused by a web app) ----------

def make_song_id(title, artist):
    """Stable id for manually added songs, so re-adding the same song updates it."""
    slug = re.sub(r"[^\w]+", "-", f"{artist}-{title}".lower()).strip("-")
    return f"manual:{slug}"


def build_document(vibe, genres="", tags=""):
    """The text that gets embedded. Queries are matched against this.

    Title and artist are deliberately left out (they're stored as metadata
    instead): otherwise a query like "songs to sing in the car" matches a song
    called "Car's Outside" on the word alone. The CSV's "Suggested Playlist
    Prompts" column is also left out because it pre-answers queries word for word.
    """
    parts = []
    if genres:
        parts.append(f"Genres: {genres}.")
    parts.append(vibe.strip())
    if tags:
        parts.append(f"Vibe: {tags}.")
    return " ".join(parts)


def add_song(title, artist, vibe, genres=""):
    """Add or update one song entered by the user. Returns the song id."""
    title, artist, vibe = title.strip(), artist.strip(), vibe.strip()
    if not (title and artist and vibe):
        raise ValueError("Title, artist, and vibe description are all required.")
    song_id = make_song_id(title, artist)
    collection.upsert(
        ids=[song_id],
        documents=[build_document(vibe, genres.strip())],
        # Chroma metadata values must be str/int/float/bool, never None.
        metadatas=[{
            "track_name": title,
            "artist": artist,
            "genres": genres.strip(),
            "vibe": vibe,
            "source": "manual",
        }],
    )
    return song_id


def _merge_list_field(a, b, sep):
    """Union two separator-delimited strings, keeping order and dropping repeats."""
    seen = []
    for item in f"{a}{sep}{b}".split(sep):
        item = item.strip()
        if item and item.lower() not in (s.lower() for s in seen):
            seen.append(item)
    return sep.join(seen)


def _parse_float(value):
    """Float, or None if blank or malformed (e.g. 'n/a')."""
    try:
        return float(value) if value and value.strip() else None
    except ValueError:
        return None


def import_csv(path, batch_size=1000):
    """Bulk import a CSV in the same format as data/sample_songs.csv.

    Returns a report dict:
      imported     - number of unique songs written
      merged       - names of songs that appeared more than once (combined into one)
      skipped      - (name, reason) for rows that couldn't be imported
      bad_numbers  - (name, column) for audio features that weren't valid numbers
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    songs = {}  # id -> {"title", "artist", "vibe", "genres", "tags", "features"}
    merged, skipped, bad_numbers = [], [], []

    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        title = (row.get("Track Name") or "").strip()
        artist = (row.get("Artist Name(s)") or "").strip()
        vibe = (row.get("Vibe Description") or "").strip()
        uri = (row.get("Track URI") or "").strip()
        name = f"{title or '(no title)'} - {artist or '(no artist)'}"

        missing = [label for label, value in
                   (("title", title), ("artist", artist), ("vibe description", vibe)) if not value]
        if missing:
            skipped.append((f"line {line_no}: {name}", "missing " + ", ".join(missing)))
            continue

        # Spotify rows use the track id; rows without a URI fall back to title+artist.
        song_id = uri.split(":")[-1] if uri else make_song_id(title, artist)

        features = {}
        for csv_col, key in FLOAT_FIELDS.items():
            raw = row.get(csv_col, "")
            value = _parse_float(raw)
            if value is not None:
                features[key] = value
            elif raw and raw.strip():
                bad_numbers.append((name, csv_col))

        genres = (row.get("Genres") or "").strip()
        tags = (row.get("Vibe Tags") or "").strip()

        if song_id in songs:
            # Duplicate: keep the first vibe, combine genres/tags, fill in missing numbers.
            existing = songs[song_id]
            existing["genres"] = _merge_list_field(existing["genres"], genres, ",")
            existing["tags"] = _merge_list_field(existing["tags"], tags, ";")
            for key, value in features.items():
                existing["features"].setdefault(key, value)
            if name not in merged:
                merged.append(name)
            continue

        songs[song_id] = {"title": title, "artist": artist, "vibe": vibe,
                          "genres": genres, "tags": tags, "features": features}

    ids, documents, metadatas = [], [], []
    for song_id, s in songs.items():
        ids.append(song_id)
        documents.append(build_document(s["vibe"], s["genres"], s["tags"]))
        metadatas.append({
            "track_name": s["title"],
            "artist": s["artist"],
            "genres": s["genres"],
            "vibe": s["vibe"],
            "source": "csv",
            **s["features"],
        })

    # Chroma caps how many items one call can take, so write in batches.
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.upsert(ids=ids[start:end], documents=documents[start:end],
                          metadatas=metadatas[start:end])

    return {"imported": len(ids), "merged": merged,
            "skipped": skipped, "bad_numbers": bad_numbers}


# Audio-feature filters. Each level is a (min, max) range on Spotify's 0-1 scale.
# Cutoffs were picked from the spread of the liked-songs library (roughly its
# quartiles), so each level covers a meaningful share of songs.
FILTER_LEVELS = {
    "energy": {"low": (0.0, 0.4), "medium": (0.4, 0.7), "high": (0.7, 1.0)},
    "valence": {"sad": (0.0, 0.3), "neutral": (0.3, 0.55), "happy": (0.55, 1.0)},
    "danceability": {"low": (0.0, 0.45), "medium": (0.45, 0.65), "high": (0.65, 1.0)},
}


def build_where(filters):
    """Turn {"energy": "high", "valence": "happy"} into a Chroma `where` clause.

    Returns None when no filters are set. Unknown features or levels raise ValueError.
    """
    conditions = []
    for feature, level in (filters or {}).items():
        if not level:
            continue
        try:
            lo, hi = FILTER_LEVELS[feature][level]
        except KeyError:
            raise ValueError(f"Unknown filter {feature}={level}") from None
        conditions.append({feature: {"$gte": lo}})
        conditions.append({feature: {"$lte": hi}})
    if not conditions:
        return None
    return {"$and": conditions}  # always >= 2 conditions, which $and requires


def search(query, n=10, filters=None):
    """Return up to n songs closest to the query as a list of (metadata, distance).

    filters: optional {"energy"|"valence"|"danceability": level} from FILTER_LEVELS.
    Songs with no audio features (e.g. added by hand) can't match a filter.
    """
    if collection.count() == 0 or not query.strip():
        return []
    where = build_where(filters)
    # How many songs pass the filter, so n_results never asks for more than exist.
    available = len(collection.get(where=where, include=[])["ids"]) if where else collection.count()
    if available == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n, available), where=where)
    return list(zip(results["metadatas"][0], results["distances"][0]))


def list_songs():
    """All songs as (id, metadata) pairs, sorted by artist then title."""
    data = collection.get()
    songs = list(zip(data["ids"], data["metadatas"]))
    return sorted(songs, key=lambda s: (s[1]["artist"].lower(), s[1]["track_name"].lower()))


def find_songs(text):
    """Songs whose title or artist contains text (case-insensitive)."""
    text = text.lower()
    return [
        (song_id, meta) for song_id, meta in list_songs()
        if text in meta["track_name"].lower() or text in meta["artist"].lower()
    ]


def remove_songs(song_ids):
    if song_ids:
        collection.delete(ids=list(song_ids))


# ---------- command-line interface ----------

def ask(prompt, required=False):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This one is required.")


def cli_add():
    print("\nAdd a song. Describe how it feels and when you'd play it;")
    print("that description is what searches match against.")
    title = ask("  Title: ", required=True)
    artist = ask("  Artist: ", required=True)
    vibe = ask("  Vibe (e.g. 'slow tempos, ambient dream-pop textures, moody guitars, and an intimate, late-night, melancholic atmosphere'): ", required=True)
    genres = ask("  Genres (optional, comma-separated): ")
    add_song(title, artist, vibe, genres)
    print(f"  Added '{title}' by {artist}.")


def cli_import():
    # The full library is git-ignored, so a fresh clone only has the sample file.
    full = HERE / "data" / "liked_songs_all.csv"
    default = full if full.exists() else HERE / "data" / "sample_songs.csv"
    path = ask(f"  CSV path [{default}]: ") or str(default)
    try:
        report = import_csv(path)
    except FileNotFoundError:
        print(f"  File not found: {path}")
        return

    print(f"  Imported {report['imported']} songs.")
    if report["merged"]:
        print(f"  Merged {len(report['merged'])} duplicate song(s):")
        for name in report["merged"]:
            print(f"    - {name}")
    if report["skipped"]:
        print(f"  Skipped {len(report['skipped'])} row(s):")
        for name, reason in report["skipped"]:
            print(f"    - {name} ({reason})")
    if report["bad_numbers"]:
        print(f"  Treated {len(report['bad_numbers'])} invalid number(s) as missing:")
        for name, column in report["bad_numbers"]:
            print(f"    - {name}: {column}")


def cli_search():
    query = ask("\nWhat's the playlist for? ", required=True)
    n_raw = ask("  How many songs? [10]: ")
    n = int(n_raw) if n_raw.isdigit() and int(n_raw) > 0 else 10

    print("  Optional filters (press Enter to skip any):")
    filters = {}
    for feature, label in (("energy", "Energy"), ("valence", "Mood"),
                           ("danceability", "Danceability")):
        options = list(FILTER_LEVELS[feature])
        while True:
            choice = ask(f"    {label} ({'/'.join(options)}): ").lower()
            if not choice or choice in options:
                break
            print(f"    Pick one of: {', '.join(options)}, or leave blank.")
        if choice:
            filters[feature] = choice

    if collection.count() == 0:
        print("  No songs yet. Add or import some first.")
        return
    matches = search(query, n, filters)
    if not matches:
        print("  No songs match those filters. Try loosening them.")
        return

    active = ", ".join(f"{k}={v}" for k, v in filters.items())
    print(f'\nPlaylist for "{query}"' + (f" [{active}]" if active else "")
          + " (lower score = closer match):")
    if filters:
        print("  (Songs added by hand have no audio features, so filters leave them out.)")
    for i, (meta, dist) in enumerate(matches, start=1):
        extras = ""
        if "energy" in meta and "valence" in meta:
            extras = f"  [energy {meta['energy']:.2f}, mood {meta['valence']:.2f}]"
        print(f"  {i:>2}. {meta['track_name']} - {meta['artist']}  ({dist:.3f}){extras}")


def cli_list():
    songs = list_songs()
    print(f"\n{len(songs)} songs:")
    for _, meta in songs:
        print(f"  - {meta['track_name']} - {meta['artist']}")


def parse_selection(raw, count):
    """Turn '1, 3-5' into {0, 2, 3, 4}. Returns None if anything is invalid."""
    picked = set()
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        start, _, end = part.partition("-")
        if not start.isdigit() or (end and not end.isdigit()):
            return None
        lo, hi = int(start), int(end or start)
        if lo < 1 or hi > count or lo > hi:
            return None
        picked.update(range(lo - 1, hi))
    return picked or None


def cli_remove():
    text = ask("\nSearch by title or artist (leave blank to show all): ")
    matches = find_songs(text) if text else list_songs()
    if not matches:
        print("  No matching songs.")
        return

    for i, (_, meta) in enumerate(matches, start=1):
        print(f"  {i:>3}. {meta['track_name']} - {meta['artist']}")

    raw = ask("  Numbers to remove (e.g. 2 or 1,3-5; blank to cancel): ")
    if not raw:
        print("  Cancelled.")
        return
    picked = parse_selection(raw, len(matches))
    if picked is None:
        print(f"  Invalid selection. Use numbers from 1 to {len(matches)}.")
        return

    chosen = [matches[i] for i in sorted(picked)]
    print("  About to remove:")
    for _, meta in chosen:
        print(f"    - {meta['track_name']} - {meta['artist']}")
    # Removal is permanent and the collection is shared, so always confirm.
    if ask("  Remove these songs for everyone? (y/n): ").lower() != "y":
        print("  Cancelled.")
        return
    remove_songs([song_id for song_id, _ in chosen])
    print(f"  Removed {len(chosen)} song(s).")


MENU = {
    "1": ("Add a song", cli_add),
    "2": ("Import songs from CSV", cli_import),
    "3": ("Make a playlist", cli_search),
    "4": ("List songs", cli_list),
    "5": ("Remove songs", cli_remove),
}


def main():
    print(f"Playlist Creator ({collection.count()} songs loaded)")
    while True:
        print()
        for key, (label, _) in MENU.items():
            print(f"  {key}) {label}")
        print("  q) Quit")
        choice = input("> ").strip().lower()
        if choice == "q":
            break
        if choice in MENU:
            MENU[choice][1]()
        else:
            print(f"  Pick 1-{len(MENU)} or q.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print()
