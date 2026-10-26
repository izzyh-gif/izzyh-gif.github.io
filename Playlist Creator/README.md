## Use of AI
I used Claude in browser to hash out my idea, used Codex to populate my exported liked songs with vibe tags and descriptions based off web searches, and used Claude Opus 5.5 in my Kiro IDE to edit code and implement new features.

## Overview 
My app (currently CLI version) allows the user to update a list of songs, adding new songs or removing current songs, and the user can also type in a query like "music for dinner and chilling" to get a playlist of songs, with their chosen length, to match their query.

## Vector Database
Songs are stored in the database, one item counts as the song's title, artist, and vibe description. The sample data and the personal data I used but did not commit came from my liked songs, where I exported it from Spotify and then asked Codex to generate vibe descriptions for each song for me. Metadata for title, artist, genre, vibes, and source were attached. I loaded roughly 500+ items/liked songs for my own use, but left 20 songs for the sample data if other users wanted to upload their own too.

## Adding and Searching
The user adds songs by selecting the CLI option to do so, inputting information about title, artist, and a brief vibe description. They use the search function in two different areas. 1) If they want to remove a song, they can search by titles or artist. 2) If they want to generate a playlist, their query for what this playlist is for searches the vector database.

## Test Queries 
1) Dinner and chilling 
   Items retrieved - Playlist for "dinner and chilling" (lower score = closer match):
   1. Chemtrails Over The Country Club - Lana Del Rey  (1.337)  [energy 0.28, mood 0.43]
   2. That’s So True - Gracie Abrams  (1.401)  [energy 0.81, mood 0.37]
   3. Daylight - Taylor Swift  (1.428)  [energy 0.50, mood 0.27]
   4. Stop The Wedding! - Ashe  (1.431)  [energy 0.69, mood 0.41]
   5. About You - The 1975  (1.442)  [energy 0.76, mood 0.46]
2) Intense 2am lock-in session
   Items retrieved - Playlist for "intense 2am lock-in session" (lower score = closer match):
   1. CHIHIRO - Billie Eilish  (1.557)  [energy 0.42, mood 0.52]
   2. Chemtrails Over The Country Club - Lana Del Rey  (1.639)  [energy 0.28, mood 0.43]
   3. Wait a Minute! - WILLOW  (1.642)  [energy 0.70, mood 0.67]
   4. You Are In Love (Taylor's Version) - Taylor Swift  (1.684)  [energy 0.51, mood 0.40]
   5. Blink Gone (VIVINOS - ALNST Original Soundtrack Part.8) - BL8M;AKUGETSU  (1.703)  [energy 0.75, mood 0.69]
A normal database wouldn't be able to retrieve these songs because it would be limited to title/artist or numeric scores like "danceability" to try to guess what the user wants, but even then would fail to capture the semantic meaning of the query which is what vector databases are needed for.

## Getting the data

The full dataset is my personal Spotify library, so it is **not committed** (see `.gitignore`). The repo only includes `data/sample_songs.csv`, 20 songs in the expected format, so the app works right after cloning.

To use your own library:

1. **Export your songs from Spotify.** [Exportify](https://exportify.app) exports a playlist (including Liked Songs) as a CSV with track info and audio features: `Track URI`, `Track Name`, `Artist Name(s)`, `Genres`, `Energy`, `Valence`, `Danceability`, `Tempo`, and so on.
2. **Add vibe columns.** Spotify doesn't describe how a song *feels*, which is what the search matches on, so add two columns:
   - `Vibe Description`: a sentence or two about the song's mood and sound (required; rows without it are skipped).
   - `Vibe Tags`: a few semicolon-separated words, e.g. `melancholy; intimate; electronic` (optional).

   I wrote mine with help from web research on each song (reviews, interviews) combined with its audio features. Writing your own short descriptions works too. Look at `data/sample_songs.csv` for examples.
3. **Save the file** as `Playlist Creator/data/liked_songs_all.csv`. That path is git-ignored, and the app uses it as the default import file when it exists. Any other CSV in `data/` is ignored too.

### Required and optional columns

| Column | Required? | Used for |
|---|---|---|
| `Track Name`, `Artist Name(s)` | Yes | Display and removing songs (not searched) |
| `Vibe Description` | Yes | Searched text |
| `Track URI` | Recommended | Song id (duplicates with the same URI are merged) |
| `Genres`, `Vibe Tags` | Optional | Searched text |
| `Energy`, `Valence`, `Danceability`, `Tempo`, `Acousticness`, `Speechiness`, `Instrumentalness`, `Loudness` | Optional | Filters and display |

Other columns (ISRC, album, label, etc.) are ignored. When importing, the app merges duplicate songs, lists skipped rows by name with the reason, and treats invalid numbers (like `n/a`) as missing instead of stopping the import.

## Vector database and embedding model (AI generated documentation)

- **Vector database:** [Chroma](https://www.trychroma.com/) (`chromadb` 1.5.9), using a `PersistentClient`. Data is saved to `Playlist Creator/chroma_store/`, which is created on first run and git-ignored because it contains the full dataset.
- **Embedding model:** Chroma's default, [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (a sentence-transformers model run through ONNX Runtime on the CPU). No API key or paid service is needed.
- **First-run download:** yes. The first time songs are added or searched, Chroma downloads the model (about 80 MB) to `~/.cache/chroma/onnx_models/`, which takes about 170 MB on disk once extracted. This needs an internet connection and takes a minute or so. After that it runs offline from the cache.
- **What gets embedded:** each song's genres, vibe description and vibe tags. Title and artist are stored as metadata only, so a query like "songs to sing in the car" doesn't just match a song titled "Car's Outside."

## Running the app (AI generated documentation)

Requires Python 3.9 or newer (tested on Python 3.14).

```bash
# 1. From the repo root, create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r "Playlist Creator/requirements.txt"

# 3. Start the app (works from any folder)
python "Playlist Creator/playlist.py"
```

The menu:

```
  1) Add a song              title, artist, vibe description, optional genres
  2) Import songs from CSV   defaults to data/liked_songs_all.csv, else data/sample_songs.csv
  3) Make a playlist         type a request, choose how many songs, optional filters
  4) List songs
  5) Remove songs            search by title/artist, pick numbers (e.g. 1,3-5), confirm
  q) Quit
```

On a fresh clone the database is empty, so start with **2** and press Enter to import the default file. Imports and additions are saved to `chroma_store/`, so you only import once.

### Filters (AI generated documentation)

After entering a request, you can narrow the results by audio features (press Enter to skip any):

| Filter | Levels |
|---|---|
| Energy | low (< 0.4), medium (0.4–0.7), high (≥ 0.7) |
| Mood (valence) | sad (< 0.3), neutral (0.3–0.55), happy (≥ 0.55) |
| Danceability | low (< 0.45), medium (0.45–0.65), high (≥ 0.65) |

Songs added by hand through option 1 have no audio features, so filters leave them out.

### Quick check (AI generated documentation)

`test.py` imports `data/sample_songs.csv` and runs one sample query, which is a fast way to confirm Chroma and the model are working:

```bash
python "Playlist Creator/test.py"
```

### Resetting (AI generated documentation)

To start over, delete `Playlist Creator/chroma_store/` and import again. The downloaded model in `~/.cache/chroma/` doesn't need to be deleted.
