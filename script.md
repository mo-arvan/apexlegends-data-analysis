
Hi Competitive Apex, I'm a data scientist and I was bored during the holidays, so I decided to do some data analysis on Apex Legends.
With latest SMG nerfs, I thought this would be a great time to share my findings with you.

Here I present two visualizations that I think are interesting that are based on two close range scenarios:
 - 1v1 fight: there is no cover, the first player to deal 225 damage wins. If the weapon runs out of ammo, the player will switch to the secondary weapon. For the sake of simplicity, the secondary weapon is the same as the primary weapon. Swapping weapons adds 550ms.
 - Jiggle Peak: one player has cover and can peak, shoot, and get back into the cover, the longer the peak, the more damage the player can deal.

Just crunching numbers on time-to-kill (TTK) or raw damage lacks practicality without considering accuracy, as hitting every shot is improbable. Hence, I introduced the concept of "effective TTK" (eTTK) to factor in accuracy when determining the time needed to eliminate an opponent.

Accuracy varies among players and scenarios. You can gauge your accuracy using firing range dummies, shooting them from various distances and angles for at least 30 minutes to better reflect your in-game performance.

Once you understand your accuracy level, you can determine the ideal weapon.

## Take Aways:

- Overall SMG meta is in a good state, I don't believe R99 is the best weapon for everyone, this was not the case prior to the nerf.
- R99 now requires a minimum of 81 accuracy to one clip a red shield, which is quite high. If you are forced to swap to your secondary weapon, other guns will outperform R99. To give you a point a reference, Dezignful had a ~55% accuracy using R99 in R5 Reloaded according to this [post](https://www.reddit.com/r/CompetitiveApex/comments/18w1upq/r5reloaded_mnk_vs_controller_stats/).
- R99 is still very competitive for a 500ms jiggle peak.
- Alternator with Disruptor Rounds has the best Jiggle Peak damage, but its eTTK is still not the best. Note that slower firing weapons are more punishing for missing shots. I would rework Alternator to have smaller magazine size and higher damage per bullet.
- Car, Volt are in the middle of the pack.
- If you hear a Prowler Auto, run for your life.


If you spot a mistake in the calculations, please let me know. Also, I'm open to suggestions on how to improve the analysis. Depending on the reception and feedback, I might expand the analysis to other weapons and more scenarios.


Ultimately in a fight, a player who deals the most damage wins. 
Time-to-kill (TTK) is the amount of time it takes to kill an enemy, is a common term in FPS games and is used to describe the amount of time it takes to kill an enemy.
The problem is in reality, the actual TTK differs from the theoretical TTK, since no one can hit all their shots.
This leaves players to decide which weapon is the best based on "the feel" of the weapon.
This works fine for the most part, except it is not based on concrete data.
My current findings match the Pro Players' opinions, R99 is the best weapon in the game.
But, let's try to figure out why.

    # st.write(
    #     'This analysis aims to provide a deeper understanding of the SMGs in Apex Legends. By the end of this analysis, we will have a better understanding of the SMGs in Apex Legends.')
    # st.latex(r''' e^{i\pi} + 1 = 0 ''')
    # tab1, tab2 = st.tabs(["Tab 1", "Tab2"])
    # intro = """
    # Ultimately in a fight, a player who deals the most damage wins.
    #
    # Time-to-kill (TTK) is the amount of time it takes to kill an enemy, is a common term in FPS games and is used to describe the amount of time it takes to kill an enemy.
    # The problem is in reality, the actual TTK differs from the theoretical TTK, since no one can hit all their shots.
    #
    # This leaves players to decide which weapon is the best based on "the feel" of the weapon.
    # This works fine for the most part, except it is not based on concrete data.
    # My current findings match the Pro Players' opinions, R99 is the best weapon in the game.
    #
    # But, let's try to figure out why.
    # """
    # # tab1.write(intro)
    # tab1.markdown(intro)  # see #*
    # tab2.write("this is tab 2")