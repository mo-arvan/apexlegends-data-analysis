---
title: "Apex Legends\u2122: July 2023 Ranked Dev Blog"
date: 2023-08-04
slug: july-2023-ranked-dev-blog
type: Game Updates
tags: []
source: https://www.ea.com/en/games/apex-legends/apex-legends/news/july-2023-ranked-dev-blog
---

# Apex Legends™: July 2023 Ranked Dev Blog


In the [Arsenal Ranked update](https://www.ea.com/games/apex-legends/apex-legends/news/arsenal-ranked-update), the team rolled out a series of changes that were intended to create consistently competitive matches by adjusting the scoring system to focus on playing the Battle Royale and as a team. Now that players have had a solid amount of time playing the Arsenal update, we’ve been able to analyze the data behind-the-scenes. Today, we’re able to share our thoughts around the state—and immediate future of—Ranked Play.

In an effort to address as many questions as possible, we’re hosting a live **Ranked AMA** on **July 21, 2023** from **9:30-11:30 am Pacific Time.** Join us on the [r/ApexLegends subreddit](https://www.reddit.com/r/apexlegends/comments/153zd5h/ama_lets_talk_about_ranked_and_our_latest_dev_blog/)!

The art of game development is rarely a straight line, it often involves building upon and refining ideas—Ranked is no exception. We hit some aspects of our goals, and also missed the mark with some of our tuning and bugs, which caused the inflated number of players in Masters and occasional unfairness in matchmaking. Let&#39;s take a deeper look at these issues and discuss some upcoming changes that will help us move towards a more stable and competitive Ranked for future seasons. 

For those who just want the gist, here’s the TLDR:

- **Overly Generous Ladder Points (LP):** Arsenal’s LP tuning was intended to be generous, but not *this* generous. Its current tuning is causing a series of cascading issues with the rest of the Ranked system. We are tightening the amount of LP awarded and bonuses included for Season 18.
- **Bugs:** We love to hate them. They are contributing to the tuning problem and we’re feeling confident about our upcoming fixes. 
- **Future Changes:** Season 18 will focus on refining Ranked tuning and stability. We’re going to take a deep breath and take the time needed to prepare for an even tighter and more competitive Ranked system.


Thank you for your passion, your feedback, and for taking this journey with us.
## <u>WHAT’S HAPPENED IN ARSENAL</u>
### LADDER POINTS: PLACEMENT AND BONUS TUNING

We intended Arsenal to be a learning experience for players adapting to the new ruleset and matchmaking. Unfortunately, the combo of this and some bugs in the Ranked system caused Ladder Point gains to be extremely generous, resulting in an excess of Masters players.

**Season 18 focus:** lowering the amount of LP distributed in a match to even out the distribution of players per rank.
### BONUSES

When a player’s ranking vastly exceeds their [Matchmaking Rating (MMR)](https://www.ea.com/games/apex-legends/news/arsenal-ranked-2023-update) equivalent, the bonus system withholds the bonus. This limit is intended and used to dial in the correct rank over time.

Thanks to the aforementioned generous LP, some players’ rankings were inflated compared to their MMR causing them to hit this “no bonus” state *much* sooner. In extreme cases, the rank was ~1-2 tiers higher than the MMR which caused the bonus withholding system to completely overshadow all bonuses. With future adjustments, this state will return to being hard to reach.

For the average player not seeing bonuses, they’d need to raise their MMR by actively defeating multiple squads per match while placing high in order to start getting bonuses again.

But we know that it feels bad to perform well and not see any bonuses.

**Season 18 focus:** adding a minimum elimination bonus increase based on the player&#39;s MMR that will be exempt from bonus withholding and bumping up the elim bonus slightly.
### RANK DISTRIBUTION

Let’s get right to it: you may have even seen a graph like the one below. This inflation of Masters players is caused by a mix of bugs and the overly generous LP tuning.

LP distribution skewed further to the right than we would like, resulting in too many Masters players. The distribution is indicated in the below graph with the dotted line for players from Rookie 4 through to 36000 LP.

![Apex Legends infographic showcasing the ranked player spread in 2017.](https://drop-assets.ea.com/images/4NRplPUf4wAniMpJk0o2pA/2eafe1fd6258d75e86d77cdcfd38fdf4/2023-07-13-ranked-dev-blog-percent-player-per-lp.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

**Our next steps:**

- LP gains per match will be decreased to address the shift in the ranking distribution.
- Adding a ruleset that only applies to Diamond + to address the large concentration of players creeping above. Players in these ranked tiers will have increased stakes and LP losses, and decreased rating bonuses and loss mitigations.


These solutions together will slow the pace to Masters for the average player, and allow for more accurate matchmaking and higher quality matches—especially at Diamond+ ranks.
## <u>PLAYING THE BATTLE ROYALE</u>
### END GAME

With the Arsenal updates, we’re seeing more climactic end games with multiple squads, players valuing their lives, and wanting to win the game instead of deathmatch simulators. 

An intense firefight for the top placement in an exciting, hectic endgame is the most memorable way to close a game of Apex Legends™, and we’re happy this is happening more frequently.

The chart below is just one of the metrics that we use to detect potential intensity of play at various points during a match. Even 2 additional players alive at the 15-minute mark is impactful for the average match!

![Apex Legends infographic for s17 showing how many players survived at the 15 minute mark.](https://drop-assets.ea.com/images/5ZjOQt05RhKfmjVNo9r7lW/dd18a066bc07f7f9bb891d42c418212b/2023-07-13-ranked-dev-blog-surviving-player-count-at-15-minutes.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.45416666666666666,yPosition=0.2526785714285714)
### PERCEPTIVE PLAY

Perceptive Play is more macro focused, where play is centered around ring positioning rather than all out aggression—an extreme variant of this is often referred to as &quot;ratting&quot;. While exciting endgames are happening, there is room for improvement with the recent increase of ratting.

A portion of this is due to an increased number of players waiting for ring closures, but we can safely say that it is mostly due to players hiding and avoiding others (while crouching or standing).

![Apex Legends infographic showing how long players are idling during a match.](https://drop-assets.ea.com/images/19XeoErb42xWGDNVp70ZTH/14b7ea84c35b422c13e07c6510c6d176/2023-07-13-ranked-dev-blog-time-spent-idle-during-match.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.4973958333333333,yPosition=0.2895467160037003)

Pretty sure you’re not all doing squat reps between rings…

We’ve noticed a particular pattern in both Ranked and ALGS levels: teams stay outside of the ring and delay interacting with other teams to gain points. 

Hiding and avoiding firefights isn’t a rewarding way to play Apex Legends™. Season 18 has some updates to target this, and more are coming in future seasons to address the core gameplay issues around inactivity and avoidant playstyles.

**Season 18 focuses:**

- Adjusting ring timings to increase mid-game encounters
- Ring damage tuning to enforce playing inside the ring
- Fixed a number of &quot;ratting&quot; spots with more fixes to come

## <u>MATCHMAKING</u>
### GENEROUS LP’S EFFECT ON MATCHMAKING

We need to talk about a specific detail with the Arsenal matchmaker that wasn’t in [our previous ranked blog](https://www.ea.com/games/apex-legends/news/arsenal-ranked-2023-update).

While we generally matchmake based on MMR, we start using Ranking (LP) in place of a player’s MMR when their ranking exceeds their MMR equivalent. In an extreme example, if a Gold MMR player has a LP ranking of Diamond, this player will be matched into a Diamond lobby.

This is to ensure MMR and LP ranking are connected and can both help guide players to their accurate Rank. If players succeed in these more difficult matchmaking situations, we allow them to continue climbing. Unfortunately, too many players in a game have inflated LP because of the generous tuning. This effectively creates a game full of players with lower MMR than their current Rank, nullifying the effect of this mechanic.

In Arsenal, you’ve been matching with a wider range of skill of players, even at the highest Ranks. This wasn’t intended and meant that your match-over-match experience varied much more than desired. We believe this will be less of an issue with reduced LP distribution in Season 18.

**Season 18 focus:** updating matchmaking to better handle players that are actively challenging their MMR to ensure a competitively challenging match that mirrors their current ranking.
### MATCH QUALITY

The new matchmaking algorithm is producing more competitive matches overall and matchmaking gameplay metrics are up across the board.

As an example, let’s look at one gameplay metric: Total Damage per Match. 

We use this to have an understanding of match intensity. When a match is unfair, many squads are decimated by an outlier squad, thus denying many players opportunities to deal damage. In contrast, a more fair match will have squads fighting, taking cover, and recovering, resulting in more overall damage dealt in a game.

![Apex Legends infographic highlighting the amounts of damage players do overall in ranked matches. ](https://drop-assets.ea.com/images/HFdw0yeCcNS4XeMI7Z8Qr/2b706d95ac3a4d5430ab2c5d26010b8a/2023-07-13-ranked-dev-blog-total-damage-per-match.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.4916294642857143,yPosition=0.2235294117647059)

This gameplay metric shot up at the launch of Arsenal, then started to degrade around May 18 as players climbed to inflated LP values and were served less fair matchups.
### QUEUE TIME

We believe queue times are too short, contributing to a higher chance you’re matched outside of your MMR. The graph below shows average wait time by player skill (lower skill on the left of the x-axis, higher on the right).

![Apex Legends infographic displaying ranked time by skill bracket.](https://drop-assets.ea.com/images/8HyLCtgKFPR1Kq0rLHNKF/0bb2007581859e6ac882d0b219c07a68/2023-07-13-ranked-dev-blog-queue-time-by-skill-bracket.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.53125,yPosition=0.3042671614100185)

During matchmaking, the system is trying to find players of a similar MMR—the longer it searches, the closer the match. The intent is to find similarly skilled players for maximum excitement and challenge, but it’s a race against the clock. Waiting forever isn’t fun either. When there aren’t enough exact matches to your MMR, the matchmaking system will continue to search for a limited time before starting the match with the closest MMR players it can find.

Matchmaking is failing at the extreme end of very high skill. These players are getting into matches too quickly, creating unfair matches with a too wide MMR range—mercilessly eliminating the lobby. We’re working on improving matchmaking for that end of the ladder to combat this.

**Season 18 focus:** the elusive root cause of this bug has been identified and we’re actively working on a fix for more consistent, high-end match experiences. 

The rest of the population is very stable and are more consistently matching with close MMR values. 

The graph below shows the adjusted MMR width of a game, highlighting how close MMR is in matches based on your current MMR + LP. Overall, the value is consistent across all but the highest tier of play. This is great because it means the matchmaker is working consistently and delivering consistently competitive matches for most players.

![Apex Legends infographic highlighting match width against skill ratings.](https://drop-assets.ea.com/images/3Mlh9CIRcW7PR4KhmJRMD6/a1cc5ac155a147c76a63f0823c52f3b3/2023-07-13-ranked-dev-blog-match-width-by-skill.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.43125,yPosition=0.23423423423423423)

Even though it’s consistent, the width above (~1.5 tiers) is still bigger than we’d like and we are confident we can tighten matches to divisions (instead of tiers) within a reasonable queue time. 

**Season 18 focus:** continued improvements and updates to matchmaking as a whole. These will ship as they are ready and are not locked to patch cycles.
## <u>SEASON 18 AND BEYOND</u>

The team has been hard at work digging into Arsenal’s data, working to address known bugs, and refining the Ranked system further. If you’ve made it this far, thanks for your time. Here’s a quick recap:

- Decreasing overall LP gains per match to combat the overall shift in the rank distribution.
- Adding a ruleset that only applies to Diamond+ to properly dial in the top of the ladder.

    - Players in these ranked tiers will have increased stakes and losses, and decreased rating bonuses and loss mitigations. Be ready to put it all on the line.

- Adding a minimum elimination bonus increase based on the player&#39;s MMR and buffing elimination bonus in general. Eliminations should always be a contributor to your rank.
- Increasing action in the ring by adjusting ring damage.
- Adjusting ring timings to create more mid-game encounters and less pre-finale lulls.
- Updating matchmaking to better handle players that are actively challenging their MMR, for more competitively challenging matches that mirror their ranking.


Waiting until Season 18 for these updates gives us more data to further inform these changes and strengthen our tuning, but it also gives players who made it to their first Masters time to relish the moment. If you earned Masters in Arsenal, you’ll keep it. You played by the game rules we implemented, and hopefully Season 18 will challenge you to earn it again.

We want to deliver the best Ranked BR experience in the world, with the tightest matchmaking and the sweatiest competition at every rank tier. Splits will not be returning for now as we’re focusing on monitoring and further finetuning. We look forward to sharing more updates on Ranked and how we plan to achieve our goals, especially as we approach Season 19—which is already in motion!

You play the most important role in the success of Apex Legends™, so please keep sharing your thoughts, feelings, and battle stories. And don’t forget to join us on r/ApexLegends subreddit for a live **Ranked AMA** on **July 21, 2023** from **9:30AM - 11:30AM Pacific Time**.

---

[Play Apex Legends™ for free](/games/apex-legends/apex-legends/buy)* now on PlayStation®  4, PlayStation®  5, Xbox One, Xbox Series X|S, Nintendo Switch™ , and PC via the EA app and Steam.

Follow Apex Legends on [Twitter](https://twitter.com/PlayApex) and [Instagram](https://www.instagram.com/playapex/), subscribe to our [YouTube channel](https://www.youtube.com/playapex%20), and check out our [forums](https://answers.ea.com/t5/Apex-Legends/ct-p/apex-legends-en).

Sign up for our [newsletter](https://www.ea.com/games/apex-legends/newsletter) today to receive the latest Apex Legends news, updates, behind-the-scenes content, exclusive offers, and more (including other EA news, products, events, and promotions) by email.

This announcement may change as we listen to community feedback and continue developing and evolving our Live Service &amp; Content. We will always strive to keep our community as informed as possible. For more information, please refer to EA’s Online Service Updates at [https://www.ea.com/service-updates](https://www.ea.com/service-updates).

*Applicable platform account and platform subscription (sold separately) may be required. A persistent internet connection and EA account required. Age restrictions apply. Includes in-game purchases.
