In class prompt- completely discarded (Claude Sonnet 4.5):
Build the game Crossy Road. Feel free to ask clarifying questions as needed and iterate to complete the feature requirements and debug.
Now code it based on the documents you created

Outside of class prompts (Claude Sonnet 4.6):
Build me the game crossy road. Base it off of the original crossy road game and the graphics should be 3D. Use javascript to write the program and I want to be able to host the game on github portfolio. Feel free to ask clarifying questions before starting and iterate to complete tasks as needed.

1. I want the controls to use the arrow keys.
2. For now, keep the character the classic chicken.
3. Put all game files in the existing Crossy Road folder.
4. I want it to be a standalone page from my index.html

The player should be able to pause the game by pressing 'p'. The orientation of the chicken should face the direction it is moving in. Also, the wheels of the car currently do not touch the ground. Re-render the cars and use the original crossy road game for reference.

Change the colors and shapes of objects like logs, trees, and trucks to be like the reference image. I want the world to extend through the full screen so that it looks like the vehicles and logs are still on the river or roads, not coming out of a blank blue screen.

The brightness of the game is too high, lower it. The controls are bugged, the chicken can't move left or right currently. The perspective or view should remain fixed, it should not change based on where the chicken is facing. Also, slow down the speed of all objects for easier gameplay.

Currently the chicken snaps to a fixed position on the log. I want it to be able to move around on the log. Also the chicken is still not facing the direction it's traveling in.

When the chicken moves off the screen, it should be game over. Also the vehicles wheels are not visible. I also want to add a "wasted" screen when the player dies.

Add a jetpack powerup that randomly spawns every few lanes which players can collect that allows the chicken to directly fly over 5-7 lanes.

Add a jetpack within the first 3 lanes of the game to introduce it's functionality to the player.

The direction of the lines on the roads are incorrect, they should be parallel to the edges of the road (horizontal on the screen)

When the jetpack is behind a tree, the power-up doesn't work even when the chicken touches it. Iterate to fix any bigs with the jetpack feature.
also, change the chicken to a cow

Add a function where the player can drop onto a lane while using the jetpack by pressing the down arrow

Can you double check and make sure the jetpack functionality is working correctly? Sometime when the cow moves onto the jetpack, it doesn't launch the cow

Rather than having the player use the down arrow to land, can you change the jetpack to always land on a grass lane so the player never dies from using the jetpack?

Make sure the jetpack always appears within 2 blocks of the edge of the screen to avoid accidentally killing a player for grabbing it.

Also add this sound effect everytime the wasted screen plays: https://www.myinstants.com/en/instant/gta-v-wasted/?utm_source=copy&utm_medium=share

stop the audio task and just work on making the jetpack never appear further than 2 blocks from the edge of the screen

I want the jetpack to AVOID spawning in any of the furthest 2 columns

The tutorial jetpack at the beginning doesn't work when I die and press play again. Make sure it's always functioning

