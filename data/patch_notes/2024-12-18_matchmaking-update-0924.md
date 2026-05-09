---
title: "Apex Legends\u2122: Matchmaking Update 2024"
date: 2024-12-18
slug: matchmaking-update-0924
type: News Article
tags: []
source: https://www.ea.com/en/games/apex-legends/apex-legends/news/matchmaking-update-0924
---

# Apex Legends™: Matchmaking Update 2024


Matchmaking is not only a core part of Apex Legends™, but it’s also an important topic for both our community and our development team. For us, good matchmaking means putting you in a squad with players of a similar skill, in a lobby with squads within your skill range, where everyone has a shot to come out on top. You may win some, you may lose some, but it is a system that should provide a variety of outcomes with each encounter.

Matchmaking is also complex and Apex has a lot of variables to account for that going into assessing a player’s skill; we don’t rely on KDR (Kill/Death Ratio) as it doesn’t fully reflect the complexity of what skilled play looks like in a Battle Royale. We know that there’s room to improve on our matchmaking and we’re going to.

A primary goal for us moving forward is to grow the conversation with our community on how our system works, why it works the way it does, and what we’re working on to better your experience. When we’re all on the same page about where we are now, we can then move the conversation forward quickly and towards the outcomes we all want—matches that consistently feel both fair and fun.

We are committed to focusing on matchmaking every season, continuing the conversation with you in the coming seasons, and promising that this is a priority for Apex. Here’s a TLDR of what we&#39;re covering today:

- Our current tech systems: the big changes since [our last update](/games/apex-legends/apex-legends/news/matchmaking-2023).

    - We’ve introduced Continuous Window Matchmaking: a dynamic system that’s capable of predicting and adapting to the current live population. This has increased our consistency during both natural periods of lower and higher server populations.
    - Bespoke changes to game modes: we made changes to how we approach measuring and using a value for a player’s skill, and each game mode is measured differently. We don’t rely on KDR as that’s not fully reflective of how we measure success and skill in a Battle Royale.

- Recent improvements: Ranked Pre-match Skill Display. This launched with From the Rift and has become a tangible means for players to understand the range of ranks they’re seeing in the lobby. Some of these are due to pre-made squads, but some screenshots have helped us with investigations and adjustments.
- Working with your feedback: we share answers to some of the most commented pieces of feedback.


The above sections have been tabbed below so that you can jump to what matters most to you and your Apex Legends experience.
## OUR CURRENT TECH SYSTEMS

There are 2 major changes since [our last matchmaking update](/games/apex-legends/apex-legends/news/matchmaking-2023) that we want to share:

- Introduction of Continuous Window Matchmaking (CWMM)
- Bespoke changes to game modes, including Ranked

### CONTINUOUS WINDOW MATCHMAKING

Live games need a lot of players at any time of the day in order to form balanced matches. Populations can shift based on time of day, region, and game mode, so we invested a lot in a dynamic system capable of predicting and adapting to the current live population. This has allowed us to create a dynamic balance between queue times and how wide the skill gap is for the lobby, which is then optimized against overall live population. Aka Continuous Window Matchmaking (CWMM).

Overall, CWMM provides an advantage in that our matchmaking is more consistent during both natural periods of lower server population and during periods of high server populations.

![A .gif graph showing how the Continuous Window Matchmaking or CWMM adapts and predicts queue times and skill gaps in a lobby at different times.](https://drop-assets.ea.com/images/3TlWtYFhc5oACRyUMsxvnM/2f952966283bcebf2b8eef04b8d0bf8c/cwmm.gif?im=AspectCrop=%2816,9%29,xPosition=0.5227777777777778,yPosition=0.4658333333333333)

(As population shrinks, CWMM widens the skill levels that are allowed into a match. It does this predictively based on live populations, striking a balance between queue wait times and lobby skill width.)

CWMM has limits in how far and quickly it’s allowed to adapt, which are set as a result of continued analysis and assessment. This means that we can effectively cap both the time a player will wait in queue and also how wide the skill can be in any given lobby; these are the ‘rails’ we establish for the system to work within. 

From metas to playstyles to growing skills, no two seasons are alike for each player. We’re constantly evaluating and adjusting those data ‘rails’ to keep the majority of matchmaking experiences within our desired design goals. All game modes make use of CWMM in order to match players with the closest skill values possible, though how we determine the skill value can be different depending on the mode.
### BESPOKE MATCHMAKING CHANGES TO GAME MODES

As CWMM came online, we also made changes to how we approach measuring and using a value for a player’s skill. This skill measurement is different between game modes, as is how we decide to update the skill value based on a player’s performance.
#### DAMAGE MODEL

Measuring damage output is a reliable way to determine skill when it’s done over a number of matches. It’s a very good system for game modes that have a smaller number of teams and players as damage output is more consistent. All players currently start with a matchmaking ‘skill’ value of 0 for their very first match of a mode that uses this model. Then the player plays the match, (hopefully) deals damage, and then their skill value updates once the match is completed.

The skill value consists of 2 parts:

- Average damage done by players historically, which makes up the majority of the overall value
- Damage from your last match, which makes up a small part of the value


With only a small part coming from your most recent match, the overall skill value becomes fairly stable over a number of matches. This allows exceptional matches to change the outcome more significantly, but not to the point of wild swings. The Damage Model skill value is used when matching in Mixtape (each Mixtape mode has an independent skill value) and certain non-BR LTMs.
#### MATCHMAKING RATING (MMR) MODEL

Over time, the team determined that the damage model could be improved upon as Battle Royales have more nuance to being ‘skilled’ than pure damage output. A new set of criteria were developed to establish skill values and when players would get updates to their overall skill value. 

For all BR modes, an update to your MMR is triggered when your squad knocks or kills a player in another squad. Both squads are then flagged for a skill update because the eliminated squad is likely to leave the in-progress match after elimination. We want to make sure that you can jump right back into another game with an updated skill value for your next match.

What determines the magnitude of your skill change is your relative placement in a match compared to the teams you had a significant encounter with (knock or kill) and the skill of the other squad. MMR is a value that falls within a fairly granular range. This is also why CWMM works so well: it starts grabbing those with the closest values of skill when trying to fill a lobby. Matches based on skill will result in fairer games when skill values are specific and granular.

It’s a simple system that works effectively and captures what we think are the most important measures of skill in BR—fighting, surviving and high placement. This model is used in all BR modes except for Ranked.
#### RP MODEL

For Ranked matches, a player’s Ranked Points (RP) value is used for matching players. This was reimplemented in Season 20 as a response to player dissatisfaction of being a high MMR player fighting against other high MMR players (as MM tries to match closest skill value), but in a low rank tier lobby like Bronze.

This combo of using MMR for matching while using RP to determine the progression for players broke the existing player expectation that ‘Bronze lobbies should be easy’ and ‘Masters lobbies should be hard.’ In response, we linked RP and skill, and we are now using RP for matchmaking. There is a loose correlation between actual skill (as measured in MMR) and a player’s RP value. This works fine when a player has plateaued in their seasonal Ranked journey (i.e. when their ‘skill value’ has stabilized for the season), but that isn’t always the case.

This becomes challenging when a high skill player starts their Ranked journey at an RP of 1, and they’re matching mostly with other players that have a very low RP value. That player will quickly stomp their way to higher ranks and make the experience less enjoyable for those getting stomped. It also gives the perception that matchmaking is totally broken, and lowers those players’ trust in Apex and their desire to keep playing.

In the past few seasons, the ‘RP Reset’ has been adjusted in an attempt to keep similarly-skilled players together at the start of the season, reducing skill-mixing. We are also re-evaluating Provisional Matches as a possible solution to initial Division and Tier placement, preventing some of that initial skill mixing while also making it harder for smurf accounts. 

As you may know, your RP value gets updated when you finish each match. That updated value is what is used for your next match, so keep requeuing and hit your best tier!
## RECENT IMPROVEMENTS

![Screenshot of the Pre-Match Skill Display in Apex Legends taken in-game to show rank tiers for each player.](https://drop-assets.ea.com/images/3O4C76tiayiuDEi06nYJ3l/c2efead9c30925f57ff243ee490feae8/pre-match-skill-display.png?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

If you haven’t been in a Ranked match yet this season, Pre-Match Skill Display shows a live display of rank tiers for each player will be shown at the bottom of the screen as the lobby fills for each Ranked match. This was introduced not only for added transparency into your upcoming match, but also to build trust around matchmaking and ensure that it’s working as intended. Bonus: it has given you a tangible way to capture and show us anything that is not balanced. Cheers for sending those through!

While some of the screenshots have been due to pre-made matchmaking, some haven’t been and that’s led to an array of actions from slight tweaks to going back to the drawing board.

We’ve some additional initiatives in the works that tap into that same goal of building trust, especially around consistently fun and fair matchmaking. So heads up: we’re going to be flexing and straining some of the existing systems and how things have historically worked. There may be some bumps in the road as we find the right fit, but we’ll keep you informed and ensure that our changes align with the Apex community.
## WORKING WITH YOUR FEEDBACK

Your feedback is a big part of that process and we often look at ways to act on it. Here’s some comments that we’ve seen the most and some insights on each of them:

- Unexpected High Skill Players: &quot;there’s X tier in my lobby!&quot;
- Ranked Tiers And Matchmaking: “each Ranked tier should only be matched against itself”
- Squadmate Matching: &quot;My squadmates are terrible!&quot;
- Premades Vs. Solo Queuing: “I consistently get rolled by premades as a solo queuer”

### UNEXPECTED HIGH SKILL PLAYERS

This is the most common piece of feedback in regards to why matchmaking is perceived as unfair. You’re chilling in Diamond IV with your squad and what looks like a full 3-stack of players with Pred badges and 20-bombs pops up as the Champion squad. What if you’re playing pub matches or Mixtape and see the same thing? You don’t have the context of anyone&#39;s rank to help understand how skilled these players really are in comparison to you and everyone else in the lobby.

This is further complicated by a decent percentage of our current players having reached Masters at some point in their past (yes, even outside of Season 17), which means they have the badges and stats to prove it. There’s nothing wrong with showing off on your Legend Banner, but that doesn’t always reflect their current seasonal performance. It often takes time for players who have been away for a while for their skills to get back into the groove after jumping in.

There are three major reasons that you’re seeing highly decorated and highly skilled players in your lobby:

1. Their current skill rating is close enough to yours for the matchmaker to put you in the same lobby
2. You‘re in a high-skilled lobby in a premade squad with a player/s higher ranked than yourself
3. You’re playing in a low population queue


The solution to the first is something that we have been actively tuning and are getting more aggressive with by prioritizing close skill matches over queue time. This season’s changes will create a longer average wait time (compared to last season) in favor of getting the lobby to be of closer skill as well as some harder limits on which ranks can be matched together. We are hoping the trade-off meets with the expectation of our most competitive players and will be worth it.

We are constantly monitoring the state of matchmaking, and this will be no exception. We are always ready and willing to make live adjustments if matchmaking times are worse than expected.

The problem of premade squads is something that we try to address in Ranked by restricting squads to be within 2 rank tiers of each other, but matching based on the highest RP value in the squad. This is meant to help counter hard-carries and boosting. In Unranked BR matches, we increase the effective skill value of the squad, to slightly counter the inherent bonus we believe premade squads have. We are looking at adjusting these values up even more and measuring the impact for solo queue players.

While low populations due to time of day or region is something we cannot directly control, we’re looking at ways to allow more players to play together regardless of time or region, and we should have more to share on that topic in the future.
### RANKED TIERS AND MATCHING

Similar to the last topic, we’ve seen the feedback around limiting matchmaking by ranks or tighter ranges of RP. We touched on this in our continuous matchmaking section as well with “rails.” Our current matchmaking system treats all players at 16k+ RP as Masters tier players. Players at this level and above are minimal, so we have to match them all together and consider them to be at the same skill level for the purposes of matchmaking.

We allow for RP to continue to be gained to allow for Masters players to continue to compete for Apex Predator, but it’s important to note that Pred isn’t a ranked tier on its own. It’s a title that we give to the top 750 Masters Ranked players on each platform. 

That said, we are continuing to balance time to find a match vs. how “wide” the match can be in terms of included Ranks in your lobby. At the time of this blog, the Ranked matchmaking system allows for the following maximum match-ups (using Diamond Divisions as the example):

- All Divisions of Diamond can match up to Masters (and therefore Preds)
- Diamond IV can match down to Platinum IV
- Diamond III can match down to Platinum III
- Diamond II can match down to Platinum II
- Diamond I can match down to Platinum I


This doesn’t account for premades though. Ranked premade squad members are allowed to be within two tiers of each other, but they’ll get matched based off the highest rank in the squad. This can result in the above restrictions appearing broken as the effective lowest rank that could be matched is now two tiers lower via a premade squad.

That said, this is also the maximum that the matchmaker will try to match to. It will always try to match the exact Ranked tier if enough players of that tier are actively queuing in your region and on your platform. To continue with our Diamond example, it currently takes about 6 minutes for matches to expand to the maximum in the current configuration.
### SQUADMATE MATCHING

How squadmates are chosen by the matchmaker was covered in [the previous blog](/games/apex-legends/apex-legends/news/matchmaking-2023), and it hasn’t changed since then. TLDR: your squadmates are chosen based on closest skill value matching. Of course, if the overall skill width in the lobby is very wide then there may be a gap between teammates.

When we examine some cases of ‘bad’ matchmaking it becomes clear that a core contributing problem is conflicting motivations and/or playstyles. You may want to push everything, but your squadmate plays more passively. Or you may want to complete sniper challenges, but your squadmate is already sniping and won’t give it up. There are so many individual styles of play and motivations that some level of incompatibility is inevitable. The best thing we can recommend here is to keep communicating, flex when possible, and remember that we’re all just looking for that next W.

The non-social part of this gets improved with overall match width tuning. If there are narrower skill gaps for the entire lobby, your squadmates are going to be very very close to your skill level. Then it’ll be up to you to figure out if you all want to play in the same way.
### PREMADES VS. SOLO QUEUING

It was mentioned above, but worth restating: we give premade squads an effective skill value increase for matchmaking, so they match into higher skilled lobbies. This is to compensate for the inherent benefit of being in a lobby with someone that you’ve presumably played with before and likely have some level of communication and coordination with. We have experimented with preferential matchmaking of ‘solos with solos’ and ‘premades with premades,’ but the results weren’t as clear-cut as you might expect. This is something that we’ll be testing again in the future to hopefully better understand the actual impact and reaction from players.
## CONCLUSION

Apex Legends should be fun, but also a competitive and challenging experience. Both consistently winning and consistently losing is bad for long-term player enjoyment, and the goal is always an optimal experience. We want players to be able to hone their skills and come out stronger as a result.

In order for that to happen, there needs to be some degree of challenge for players which is partially where matchmaking comes in, but it’s a delicate balance. Apex has some of the most skilled and competitive Battle Royale players out there today. We’re working to build up the trust in our systems and design approach, and you can expect to see a new focus on that goal via matchmaking.

As always, we look forward to your feedback and will keep you in the loop about what’s coming next. Until next time, Legends!

---

[Play Apex Legends™ for free](/games/apex-legends/apex-legends/buy)* now on PlayStation 4, PlayStation 5, Xbox One, Xbox Series X|S, Nintendo Switch, and PC via the EA app and Steam.

Follow Apex Legends™ on [Twitter](https://twitter.com/PlayApex), [Instagram](https://www.instagram.com/playapex/), [TikTok](https://www.tiktok.com/@PLAYAPEX), subscribe to our [YouTube channel](https://www.youtube.com/playapex%20), and check out our [forums](https://answers.ea.com/t5/Apex-Legends/ct-p/apex-legends-en).

Sign up for our [newsletter](https://www.ea.com/games/apex-legends/newsletter) today to receive the latest Apex Legends™ news, updates, behind-the-scenes content, exclusive offers, and more (including other EA news, products, events, and promotions) by email.

This announcement may change as we listen to community feedback and continue developing and evolving our Live Service &amp; Content. We will always strive to keep our community as informed as possible. For more information, please refer to EA’s Online Service Updates at [https://www.ea.com/service-updates](https://www.ea.com/service-updates).

*Applicable platform account and platform subscription (sold separately) may be required. A persistent internet connection and EA account required. Age restrictions apply. Includes in-game purchases.

†Not available in all territories.
