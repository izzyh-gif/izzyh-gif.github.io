## Use of AI
I used Claude in browser to hash out my idea, used Codex to populate my exported liked songs with vibe tags and descriptions based off web searches, and used Claude Opus 5.5 in my Kiro IDE to edit code and implement new features.

## Prompts

I installed chromadb, can you double check if it's working properly using the test file in playlist creator and editing it to see if it works on more items

Don't code yet. I'm planning to build a playlist creator based on user input or queries such as "songs to sing in the car" or "a playlist for an intense 2am lock in session". I have a data source on kaggle for 30000 Spotify songs. 1) Is that too many songs to deal with? 2) How should i load in my data source?

Beginning with just these 20 songs adapt the code with the right documents, metadatas, and ids and then try to use the query I changed: songs to sing in the car

Now do this for the rest of the liked songs, ignore any duplicates

Now, I want the user to be able to input their own songs and input their own queries. Add that functionaility and ask clarifying questions as needed. Which is for feasibile, balancing user experience and program complexity: having the user input a vibe description or generating one for the song based off a web search?

This can stay a terminal tool for now.
Everyone can share a song collection.
Ignore the kaggle data set, I will upload my liked songs later to test a larger amount of songs.
Add an option to remove songs

Ignore the "good for" some situation column from liked songs csv I think that takes away from the need for vector databases

I have about 500 songs I'm going to add in a csv, is the current program equipped to handle that many?

merge duplicates, report skipped songs by name, and treat bad numbers as missing
Liked_Songs_All_Uni….csv

Implement both changes (taking title and artist out of the searched data and use the audio features as filters)

I'm not supposed to commit my raw dataset to my github repository. Can you rename the 20 songs I used originally to sample_songs.csv and ensure only that csv can be commited? My other dataset should use a .gitignore to avoid being committed

## Brainstorming prompts

https://www.cs.cmu.edu/~113/hw6.html
This is my assignment, what are some ideas to explore?

give me some creative ideas

could there be something about online games like nyt games, krillion, poople, globle, minecraftle, etc.?

is this not just the game contexto

would it be feasible and relevant to use census and healthcare data to identify peer communities or countries and find those with greatest divergence in healthcare quality using this assignment?

can you give me some ideas based on my interests? would it be possible to search for dances based on a description of style and vibes or is it too hard to get data for that?

could I make a playlist or song recommender based on vibes?

organizing music you already have (ex: liked songs)

https://www.kaggle.com/datasets/joebeachcapital/30000-spotify-songs
would this dataset work? and would I be able to add a feature where users can upload their own liked songs?

can I use my liked songs and then use codex to generate a description of vibes for each song based on a web search? I have 543 liked songs
