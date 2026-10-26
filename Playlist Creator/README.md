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
    
