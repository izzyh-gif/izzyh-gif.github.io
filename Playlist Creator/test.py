import csv
from pathlib import Path

import chromadb

HERE = Path(__file__).parent
CSV_PATH = HERE / "data" / "sample_songs.csv"

# PersistentClient writes to disk. The default in-memory client does NOT.
client = chromadb.PersistentClient(path=str(HERE / "chroma_store"))
collection = client.get_or_create_collection(name="songs")

# Numeric audio features kept as metadata so they can be used in `where` filters later.
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


def build_document(row):
    """The text that gets embedded. This is what queries are matched against."""
    # Title/artist live in metadata only, so queries match on vibe, not song names.
    genres = row["Genres"] or "unknown genre"
    return (
        f"Genres: {genres}. "
        f"{row['Vibe Description']} "
        f"Vibe: {row['Vibe Tags']}."
    )


def build_metadata(row):
    # Chroma metadata values must be str, int, float, or bool (no None).
    meta = {
        "track_name": row["Track Name"],
        "artist": row["Artist Name(s)"],
        "album": row["Album Name"],
        "genres": row["Genres"] or "",
        "track_uri": row["Track URI"],
        "popularity": int(row["Popularity"]),
        "explicit": row["Explicit"].strip().upper() == "TRUE",
        "duration_ms": int(row["Duration (ms)"]),
    }
    for csv_col, key in FLOAT_FIELDS.items():
        meta[key] = float(row[csv_col])
    return meta


# utf-8-sig strips the BOM that Spotify/Exportify CSVs often start with.
with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

ids, documents, metadatas = [], [], []
for row in rows:
    # "spotify:track:4gMPlHHAjOQnUrhsuqHivn" -> "4gMPlHHAjOQnUrhsuqHivn"
    ids.append(row["Track URI"].split(":")[-1])
    documents.append(build_document(row))
    metadatas.append(build_metadata(row))

# upsert lets the script be re-run without duplicate-id warnings.
collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
print("songs in collection:", collection.count())

query = "playlist for an intense 2am lock-in session"
results = collection.query(query_texts=[query], n_results=10)

print(f'\nTop matches for "{query}" (lower distance = closer match):')
for rank, (meta, dist) in enumerate(
    zip(results["metadatas"][0], results["distances"][0]), start=1
):
    print(
        f"{rank:>2}. {dist:.3f}  {meta['track_name']} - {meta['artist']}"
        f"  (energy {meta['energy']:.2f}, valence {meta['valence']:.2f})"
    )
