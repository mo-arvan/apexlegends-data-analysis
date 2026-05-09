---
title: "Apex Legends\u2122: Matchmaking Test Update"
date: 2025-11-26
slug: amped-matchmaking-update
type: News Article
tags: []
source: https://www.ea.com/en/games/apex-legends/apex-legends/news/amped-matchmaking-update
---

# Apex Legends™: Matchmaking Test Update


Welcome back to the latest Apex Legends Matchmaking dev update! Grab a comfy chair, your favourite warm beverage, and settle in for our latest update. 

In this blog, we’re going to cover:

- A refresher of key matchmaking concepts
- Test Results: 26.1 Ranked matchmaking test
- Matchmaking health motivated Duos changes
- Things you can do to (possibly) improve your matchmaking experience
- What is next for matchmaking

## Matchmaking Key Concepts Refresher

If you have been keeping up on our Matchmaking Blogs (links here), then you can probably skip this section, or use it as a refresher and read on.

Apex Legends’ matchmaking systems try to balance two main criteria for an optimal player experience: filling a lobby with similarly skilled players and doing so within a certain amount of time. It can only fill a lobby from the pool of available players currently online, who are actively seeking a match, on a specific platform (unless you have crossplay enabled), in a specific region. 

The system has parameters for each mode that control the acceptable skill disparity between “similarly skilled players” thus allowing them into the same lobby. However, this also needs to be balanced with ensuring players aren’t waiting in queue for too long as a result of the available player population at that moment.

Platforms and regions with higher overall active populations at key times will result in smaller skill variance in matches. Active player counts (depending on platform and region) have a “peak” and “valley” each 24 hour period, when they are at their highest and lowest counts, respectively.

![Line graph showing matches per hour in Apex Legends from just before Nov. 12th, to Nov. 18th.](https://drop-assets.ea.com/images/2h51wssHpn5NBK6T3zYVGM/90928f5ba48c418c1af5a2fe496b9d56/Matches_per_Hour_16x9_v3.jpg?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

***The above graph illustrates the peaks (typically between 7pm and 10pm, local time) and valleys (in the middle of the night) of the number of matches being made across different hours of the day for a single region and players can expect similar trends throughout each season.***

Population is the key to establishing matchmaking that is both fast and “tight.” In theory, the fastest and tightest skill lobby would result from there being 60 players all matchmaking for the same game mode, at the same time, on the same region server, playing on the same platform, AND having the same skill value.

As that is simply not the norm, we attempt to find the best matches for you for when you’re playing, and that sometimes results in longer queue times.

We&#39;re always looking to improve the overall quality of your experience, share what we&#39;re working on and give context based on your feedback.
## Test Results: 26.1 Ranked Matchmaking Test

Now that we’re all caught up, let&#39;s review the matchmaking test and the result from 26.1. 

This was our second test attempting to remove Masters tier (which includes Apex Predators, as they are the top 750 Masters tier players, per platform) from matchmaking with Platinum players and below. 

In this test, which ran for just under two weeks at the end of Split 2, Masters players were only able to match with other Masters and any division of Diamond (I through IV).

The goals of this test (and this blog) were to:

- Determine if we can safely restrict Masters to play against only other Masters players and Diamond tier 
- Ensuring every player that searches for a match is able to find one eventually, even if the wait is much longer than it is without the restriction
- Improve our matchmaking parameters to adapt to tier populations shift over the course of a season
- Communicate transparently with the community to set expectations for the future of Ranked matchmaking


**TLDR**: This test successfully limited Masters matchmaking as intended and did not negatively impact queue times or skill width. When the test was run, our queue times and skill width were already near our targets, so they did not move much as a result. We are optimistic about what we learned and are eager to make improvements that can impact the overall seasonal matchmaking experience, not just at the end.

The Ranked tuning changes in Season 26 increased the effort required to achieve higher tiers, resulting in lower-than-previous populations in Diamond and Masters. These lower populations pushed matchmaking at these tiers to the upper limits of what we consider acceptable queue waits and match skill-width for an ideal player experience. As a result, players outside of Masters experienced similar matchmaking before and during the test.

One big takeaway for us from the last two matchmaking tests is that our ability to more aggressively adapt matchmaking to shifting populations could create more consistent experiences over the course of a season. We’ll dive more deeply into this challenge and resulting opportunity below.

![Bar graph showing the distribution of player competitive tiers from season 25. The bar starts on the left from before May 19th, and goes till a bit after July 28th.](https://drop-assets.ea.com/images/58L6OezsgPqJkdFrCy0ZR8/531715e1bfe7e31f1473f81baeb4a6f8/s25_Tier_Distribution_16x9_v1.jpg?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

The above graph shows the percentage of players in each Rank Tier, per day, over the course of Season 25. Diamond was hitting about 20% of total players near the end of Split 2; this population is what allowed us to more easily restrict Masters to play against only Diamond I players.

When we compare this to the distribution across Season 26 below, there is a dramatic difference in populations in the higher Tiers.

![Bar graph showing the distribution of player competitive tiers from season 26. The bar starts on the left from before Aug 18th, and goes till a bit after Oct 27th.](https://drop-assets.ea.com/images/53bb5tczhikCvdx5plGPbQ/62f1106df9b97af248e02ab022ae79e9/s26_Tier_Distribution_16x9_v1.jpg?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

In Season 26, the population that achieved Masters was ⅓ the total seen in Season 25 due to RP tuning, as well as the introduction of Drop Zones. With fewer overall players achieving the higher ranks relative to the larger Apex playerbase, players experience longer wait times when matchmaking is restricted to only Masters and Diamond. Considering these populations start low, they must be mixed with lower-tiered players to be able to play at all.

As a result of these learnings, we will be looking at how to better adapt matchmaking to maintain match consistency based on shifting populations and will keep you updated as we move forward with next steps.
## A Note About Solo Queueing

A consistent request we hear from our community is the ask to address solo queue. There are two distinct flavors of the underlying frustrations that lead to this request, which are:

1. “It feels unfair to be matched against a premade squad”
2. “As a solo player, I don’t like the squadmates I get assigned” 


The typical solution proposed as part of these conversations is to have solo queue squads only be in matches with other solo queue squads, and premade squads to only be in matches with other premade squads. 

The suggestion is a good one, in a world where there are enough solo queue players and premade squad players to keep the matchmaking close to where it is now. 

The very rough, back-of-the-napkin math shows reducing a population by 50% by splitting solo and premade players (assuming 50/50 balance between the two) would double the queue wait times and skill width of matches for each population. Duos is living proof of this occurring, which we speak to next. 

So, in short, we are currently choosing to not split out premades and solo queuers into their own matching and matches, as we feel it would too dramatically increase queue waits and match skill-width. 

When looking at concerns surrounding squadmate quality, the matchmaking systems work to partner you with players of similar skill levels. What we’re seeing is that not everyone at a certain skill level plays the exact same way, or is even playing each match with the same goals in mind. As a simple example, some players of similar skill may be more aggressive while others may have a tendency to hang back.

As these are all subjective qualities and personal playstyle preferences, any objective definition we attempt to create to leverage in matchmaking would be OURS, and therefore might be out of alignment with many players. 

It’s not an easy problem to solve, but we’ve got some folks working to crack it. We encourage you to think about what makes an ideal teammate. We’re always monitoring player feedback and look forward to seeing what the community has to say on the matter.

In the meantime, we encourage solo queuers to take advantage of the Requeue with Squad feature and keep that great squad together for as long as you can.
## Duos BR &amp; Matchmaking

More context on the recent Duos changes has been highly requested, and we thought it would be most beneficial to explain the changes in the context of matchmaking and player populations. 

As a quick recap, the lobby size of Duos was reduced to 30 players and the rings on maps were adjusted to keep match pacing aligned with the 60 player experience. 

So, why was it done?

Well, it comes down to population. When Wildcard launched, many players migrated to that mode and made it their new regular stomping ground. 

As a result, over half of the previously active Duos players stopped playing the mode and never came back. We have seen some theories that the drop is a result of UI changes, but we can confidently point to Wildcard’s introduction. This had a significant negative impact on the quality of matchmaking for the remaining Duos mains. In some cases it roughly doubled queue wait times, depending on region and time of day. 

After evaluating the data, the difficult decision was made to modify the mode’s maximum lobby size (and maps). This was the solution that provided the most confidence in how to rapidly and, with one focused change, restore the previous matchmaking quality in Duos. 

Duos population is now stable, as is the matchmaking width and queue wait times. Given the current stability, there are no current plans to revert Duos to a 60 player lobby. 

We have been gathering and sorting specific feedback around the current Duos experience, and will be evaluating it as part of our future plans for any opportunities to address concerns inside the 30-player experience. 
## Can I Do Anything To Help My Matchmaking?

While we continue to evolve solutions on our side, there are a few optional actions you can take to attempt to improve your matchmaking experience. Some of these we already see players doing, and they are worth sharing wider in case they align with how you play Apex. 

1. Play during peak hours for your chosen server. Each server region has peak hours, typically between 7pm and 11pm, and the highest quality matchmaking is most likely to occur during the peak. The opposite also applies — if you are playing during the valley, when population is lowest, the matchmaking will take longer and result in higher skill-width. 
2. Choose a different server to play on. You have the option to select a different region and server to play on. This can be done at the splash screen, before launching full into Apex. Changing servers may increase your latency beyond your acceptable level, so pay attention to the Ping value of your chosen region. 
3. Ensure Crossplay is enabled (if available on your platform) [<u>[https://help.ea.com/en/articles/apex-legends/add-friends-cross-play/](https://help.ea.com/en/articles/apex-legends/add-friends-cross-play/)</u>]
4. To find squadmates with similar skill level and play style, consider joining external Apex-focused social hubs where LFG threads are common. Also, leverage Requeue with Squad after the match if you want to keep a good time rolling!


While these actions will not guarantee a better matchmaking experience, we hope these are things you can take advantage of and test your own success. 
## Wrap Up &amp; Next Up

As we move forward into future seasons of Apex, we will continue our commitment to listen, evaluate and take action to address concerns from player feedback and from our data analysis. 

We always appreciate feedback and sharing of experiences, so please continue to engage with us on socials. 

For what is up next for matchmaking, we are looking to:

- Create more consistent matchmaking experiences in Ranked across the entire season, for all Rank Tiers
- Activate hard limits to prevent Masters from playing Platinum when Masters and Diamond reach the required population
- Increase maximum queue wait times for higher Rank Tiers, to increase the opportunity for them to match within their own Tier
- Faster and narrower matchmaking by testing merging of select populations, while minimizing performance impacts (latency)


As we take these actions, expect more updates across our official channels.

We hope you enjoy the current season and we’ll see you in the arena!

*This announcement may change as we listen to community feedback and continue developing and evolving our Live Service &amp; Content. We will always strive to keep our community as informed as possible. For more information, please refer to EA’s Online Service Updates at* <u>[*https://www.ea.com/service-updates*](https://www.ea.com/service-updates)</u>*.* 

---

[Play Apex Legends for free](https://www.ea.com/games/apex-legends/apex-legends/buy)* now on PlayStation 4, PlayStation 5, Xbox One, Xbox Series X|S, Nintendo Switch, Nintendo Switch 2, and PC via the EA app, Epic, and Steam.

Follow Apex Legends™ on [Twitter](https://twitter.com/PlayApex), [Instagram](https://www.instagram.com/playapex/), and [TikTok](https://www.tiktok.com/@PlayApex), subscribe to our [YouTube channel](https://www.youtube.com/playapex%20), and check out our [forums](https://answers.ea.com/t5/Apex-Legends/ct-p/apex-legends-en).

Sign up for our [newsletter](https://www.ea.com/games/apex-legends/newsletter) today to receive the latest Apex Legends news, updates, behind-the-scenes content, exclusive offers, and more (including other EA news, products, events, and promotions) by email.

This announcement may change as we listen to community feedback and continue developing and evolving our Live Service &amp; Content. We will always strive to keep our community as informed as possible. For more information, please refer to EA’s Online Service Updates at [https://www.ea.com/service-updates](https://www.ea.com/service-updates).

*Applicable platform account and platform subscription (sold separately) may be required. A persistent internet connection and EA account required. Age restrictions apply. Includes in-game purchases.
