---
title: "What Makes Apex Tick: A Developer Deep Dive into Servers and Netcode"
date: 2021-04-28
slug: servers-netcode-developer-deep-dive
type: Game Updates
tags: []
source: https://www.ea.com/en/games/apex-legends/apex-legends/news/servers-netcode-developer-deep-dive
---

# What Makes Apex Tick: A Developer Deep Dive into Servers and Netcode

### Introduction

Hello, I’m [@ricklesauceur](https://twitter.com/ricklesauceur?lang=en), lead engineer on Apex Legends, and today I want to offer you a bit of insight into the online infrastructure that supports Apex Legends.

In the past, we haven’t often talked publicly about servers, netcode, or online infrastructure for Apex Legends, and today we want to begin to change that. In short, today we want to:

- Share a bit about **how we’re working to improve your online experience** in Apex Legends
- Acknowledge and **explain some common online issues** or connectivity problems you may encounter while playing Apex
- Specifically **address commonly-asked questions** about topics like slow-mo servers, hit-registration, and how our lag compensation system works
- Offer some **comprehensive notes on our server tickrate** , and explain our thinking behind what it affects, and what it doesn’t


A warning: This post is *long* because it’s intended as a true deep-dive into the online infrastructure for Apex Legends—something we’ve seen some players requesting for a long time. 

We’re thinking of this as the starting point of a longer conversation, so even though we do cover a lot of ground here, there’s probably plenty of topics (DDOS attacks! Server-crashing bugs! Etc.!) that we could spend more time addressing. By all means, if you like this blog, let us know what you’d like to hear about next time, and we’ll keep it going.

For those of you who are ready to geek out about netcode, servers, tickrate, and more… welcome! Let’s kick things off by talking about some recent improvements we’ve shipped.
### BOOSTING OUR RESPONSE TIME WITH PERFORMANCE METRICS

In Season 6, we introduced the performance display. It looks like this and gives you basic information about your performance.

“In” and “out” are the bandwidth consumed by the game (in kB/s). You also have latency (in milliseconds). Packet loss and packet choke are rendered as a percent of packets per second.

Those numbers help you—and us—understand what you’re experiencing while playing. In other words, we can translate what you’re feeling into actionable and technical information.

Before this addition, we would hear from players that “something” was off, but they couldn’t always tell us much beyond that. Now, you can accurately say, “I have 10% packet loss, 300 ms latency,” etc. It changes *everything* because those numbers are often the best possible indication of what’s going wrong. I’ll come back to this point.

While working on the performance display, we also began tracking key performance metrics for players and servers. This means that **if someone reports problems, we can pull down their match and see everyone’s data** in the game at the time, including information about the specific server hosting the game. 

This represented our first big push to give personalized and targeted means of investigation to our team. We’ve had some successes with this approach, but we think that in the long-term it does not scale. First, we have to hear from you, then dispatch an engineer to see where the issue comes from, and then (depending where the problem lies) we attempt a fix.

In recent seasons, we’ve begun leveraging the help of our awesome data science team to batch and crunch (i.e. gather and analyze) one week of data at a time to detect excessive packet loss and server performance issues. **This approach has been paying off already**. For example, we found out that one piece of network equipment in our datacenter was faulty, causing every game hosted on a handful of servers to have horrible network performances. The server themselves were fine, but the hardware that connected players to the servers in question was causing massive packet loss. We encounter plenty of examples like that.

The main benefit we get from systematically analyzing data is that it lets us cross-reference metrics and players to find patterns. So, week after week, we can confidently say if the health of our server fleet is better or worse. Data analysis is also a great tool to help our partners fix issues when it’s something outside our control. Instead of saying something is wrong, we can say, “this specific thing ** is wrong,” which saves time for everyone involved. (By the way, you can opt-out of this if you like. Just go to “Gameplay” and then “Usage Sharing” in the settings menu.) 

So automation helps a lot. But it’s not enough. 

Indeed, with this approach, we are still somewhat slow to react to problems. We need to wait a week for most data to be reliably gathered and reported to us, then it can often take another week for a full investigation to be conducted. From the moment you start noticing problems, it may take us up to two weeks to find a fix, and even more to deploy the solution if it requires a server patch.

**We can do better. We** ***will*** **do better.** So let’s talk about solutions.

First of all, in addition to our weekly report, we’ve moved to real-time alerting. It will give us the same level of information that we have now, just faster. We will be able to fix hardware problems right away or start investigating and working on a patch. We understand the frustration of having to wait and we try actively to shrink the time between an alert and a fix.

Second, we’re going to introduce a new server unique ID (“SID”) to the performance display that will allow us to find the server you’re playing on faster. At the moment, you give us a time and date and we correlate that with the data we have on you to find the server you were playing on. Soon, we won’t have to do that. 

**We expect both of the above solutions to start rolling out during our upcoming season**, Apex Legends: Legacy. The result for players will be speedier resolution of server issues, sometimes twice as fast as currently.
### A DEEP DIVE INTO COMMON ISSUES

Now to the fun part, let’s broadly categorize server issues you may encounter. The list below is *not* exhaustive, but I hope it answers most of your questions.
### ***The server is running in slow motion.***

Everybody loves this one. Our servers are running at 20Hz. This means that they simulate the entire world state once every 50ms (1 second—or 1,000ms—divided by 20).

We don’t speak about FPS (frame per second) when discussing server performance because a server does not display pictures. Instead, a server computes “states” but the underlying principle is the same. It takes user inputs (from the network), runs the physics, sends back the new world state to clients, then repeats. If this process takes more than 50ms consistently, your game will slow down to permit the server to finish the simulation. Thus, you get slow-mo servers.

![Apex Legends info graph showing frame rates for a server.](https://drop-assets.ea.com/images/4ddXkCqwkW9a7rta9ElVUq/ccd2843ea6c046ea4c224843e8669851/image7.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.17486338797814208,yPosition=0.47198275862068967)

*View of the frametime for a server. Column 5 is the 50ms target. Everything under is faster. You can see that this server was stable and faster than required.* 

![Apex Legends server frametime that has bad match causing lag and other issue.](https://drop-assets.ea.com/images/6datdIFewnwpjQz4RxxyGF/93bfa19d918da31b49ed264bf97665b0/image2.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.7454798331015299,yPosition=0.2552742616033755)

*In comparison, this server never met frametime and was mostly running around 200ms frametime (so 4 times slower). Typically a slow-mo server.*

There are a number of things that can cause this, but it’s sometimes linked to machines in the datacenter not performing as they should. Think about an underclocked CPU, overheating, etc. 

When we detect those, we usually remove those machines. This means we literally call up the service provider, point out the problem with the given machine, and ask them to take it offline. 

The real-time detection solution mentioned earlier in this blog should reduce this issue considerably when we roll it out during the upcoming season. We’re heavily invested in solving this issue, so we’re going to keep a close eye on it. 
### ***My latency is going up and down.***

If you play on WiFi, we can’t do much for you! Otherwise, rapidly changing latency can sometimes be related to our server performance.

We all know that even if a game typically runs at 60fps, that can change when a lot is happening on screen. Even if you&#39;re only dropping a few frames, you feel it. It works similarly for servers. Here, automatic detection does not help much with determining the root cause of the problem. Historically, we’ve had to recreate the conditions of the slowdown on a dev server, but this is pretty time-consuming and always a bit of a shot in the dark—your machine probably doesn’t run on the same server hardware, or with the same settings, so it’s hard to replicate anything one-to-one. 

Thankfully, our operations team produced a tool to let us get what we call a RPROF file. This is basically a view of what the server is doing during every frame (ballistic simulation, network in and out, player movements, etc). Thanks to RPROF files, we’re able to know what’s slowing things down and an engineer can start optimizing. Usually, the problem has something to do with increased performance demands introduced by new features season after season. 

You may remember, for example, the slowdown on the Champion screen at the beginning of the game during Seasons 7 &amp; 8. It was caused by all the players in the match spawning at the same place on top of and even overlapping each other. (And you couldn’t even see them because of the UI!) Physics simulations really hate having some objects overlapping with others and our physics engine was trying to get all the bodies away from each other, causing massive CPU spikes on the server.

![Apex Legends info graph showing percentages of matches affected by servers with low performance.](https://drop-assets.ea.com/images/3AcjqYwkTjylsmsH4KGovN/92052b70b4d5d8f8ea13ea61749eb7a2/image5.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

*Percentage of matches affected by a server with slow performance (not necessarily slow-mo) per regions. You can see that some regions get better with time and other degrades (X axis is time).* 

![Apex Legends info graph showing matches with bad framerates in US west region.](https://drop-assets.ea.com/images/5icvCI24799PHtavlxhL88/114dec685491215fb48de38581bf71b7/image3.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

*A detailed view of the US west region that allows us to detect faulty machines (the X axis is time). Outages are very clear on the charts. Some machines are affected while others remain stable.*

We anticipate that our usage of RPROF files is going to better help us optimize new features we add to the game and **reduce latency more generally in the future**. Lowering latency for all players is a big focus for us, and better tools like this are crucial for helping us get there. 
### ***I have a lot of packet loss / packet choke.***

This one is extremely tricky. It’s probably not your fault, and it’s also usually not ours either! 

It has to do with how internet traffic travels from your box to our datacenter and back to you. At the beginning, your network traffic is on your ISP network. Your ISP may be having a outage where your information, along with other customers&#39; information, is being lost / dropped. This results in the game client not knowing what is happening with the players around you or the game server not knowing that you want to shoot your gun or move in a certain direction. There’s also the connection between your ISP’s network and our Datacenter network. Problems can pop up anywhere along this line.

When things go smoothly, we call this process “peering.” A lot of the time, peering problems result when a connection between two networks has a weak link. There can be multiple hops like this along the way. And then, of course, all the information from the Apex servers needs to get back to you, often by taking a different route. You can start to understand why this gets complex. 

If we want to help resolve this, the first thing for us to do is to be able to detect where the outage is. This is hard to automate because we need data from you, and we need data from the server so we can look at the issue from both “perspectives” and try to probe along the way to see where the problem is. 

As of today, we ask players to provide some kind of network traces, and we do the same on our side from the datacenter to try to detect where the congestion point is. This is extremely time consuming and slow to resolve because, depending on our findings, we have to negotiate with different business partners all over the world. We’re hopeful that automation can help improve this process and we have some improvements in the works that are still in early stages. 

When it comes to network traffic problems like the ones we’re discussing, one good thing is that the problems tend to happen in bulk instead of being tied to any particular individual. This means that fixing the problem for one affected player usually unblocks a lot of others. We are also actively reducing the bandwidth used by the game which helps to mitigate the problem.

**Hosts**

**Local ISP -** Best: 22, Average: 31, Worst: 264

ISP 1 - Best: 27, Average: 185, Worst: 515

ISP 2 - Best: 24, Average: 194, Worst: 652

Game Server - Best: 31, Average: 263, Worst: 522

*This is a network trace (showing latency) of one of our pro players, from his internet modem to one of our servers. We probe multiple times to assess the true health of the internet connection. You can see that he is able to enjoy the game in the best condition with 31ms latency. But the worst is around 522ms. So in this case, his game experience is extremely bad because his connection oscillates with a difference of 500ms. The connection is a bit shaky on his local ISP network, but the average shows us it is pretty rare (Average of 31ms with a worst of 264ms, must be an isolated incident.) But then we see a spike of latency between the local ISP and ISP1, which is one of the nodes in between the player and our Game Server. We can be nearly certain there is packet loss and routing issues between the two. It is outside our control but we can inform those partners of this problem. Usually it is in everyone’s interest to resolve the situation.* 
### ***I am being killed while behind a door/wall, and sometimes I roll back to my previous position.***

This is a spicy topic. It has to do with lag compensation. 

In every game since the dawn of online gaming, the main problem for developers to solve is how to fake real time action in something that is not operating in real-time. Essentially, *everything you do in online games* is delayed because of the latency to the server and back. A lot of things add to this: inputs, rendering, and yes, even server tickrate. 

Even worse, on top of all that is your opponent who almost certainly plays with a different level of latency than yours. To solve this, our servers have to constantly look at not only what’s happening for you and your opponent at that moment, but also what *was* happening from both your perspectives at the time both of you input your actions. Lag compensation is the art of merging slightly different experiences into one shared reality. 

There is no perfect solution. There is not one truth. At the end of the day, the server is a sort of time machine. It constantly rolls back the world state to see if your shot hit someone, and then updates the world for everyone accordingly. 

To better illustrate this principle, my colleague Earl Hammon wrote a little essay about fairness and lag compensation, and how it all works in Apex Legends. I’m sharing it with you below:

*Let&#39;s go through various scenarios with two players in Apex Legends called* ***HIGH*** *and* ***LOW****. Let&#39;s give HIGH a high ping of 300 ms, and LOW a low ping of 50 ms. The difference in their pings is 250 ms.*

*What happens if they shoot at each other at the same real-world time? Well, LOW&#39;s shot will arrive at the server long before HIGH&#39;s shot, so LOW has the advantage.*

*What happens if one of them rounds a corner, so that they can suddenly see each other? Well, LOW has the advantage here as well. LOW is less “into the past,” so they get to see HIGH first. Once again, LOW has the advantage due to their ping. This adds on to the advantage where LOW’s bullets get to the server faster.*

*These cases are &quot;unfair&quot; in the sense that LOW has an advantage, but they are &quot;fair&quot; in the sense that it&#39;s reasonable to expect that the player with lower ping would get the advantage in this situation.*

*Now, what happens if LOW goes behind a corner to get into cover? Well, HIGH is still in the past when LOW is not covered, so HIGH can shoot LOW before they get into cover, but LOW won&#39;t find out about it until HIGH&#39;s packets have made it to the server and then to LOW. By this time, LOW sees that they’re safely in cover, yet LOW still got hit. From LOW&#39;s perspective, this is a bit of nonsense.*

*However, this is exactly symmetrical to some of the earlier nonsense that was in LOW&#39;s favor! When LOW pops out of cover to attack HIGH, LOW gets to see and shoot HIGH while it appears to HIGH that LOW is still in cover. From HIGH&#39;s perspective, this is a bit of nonsense, that they get shot by somebody who was still in cover. This nonsense can’t be eliminated, only transferred between one player or another, because of the simple reality that ping is real and players have different amounts of it.* 

*Some would suggest that it is unfair to LOW that HIGH can shoot them when LOW thinks they are behind cover. The alternative they suggest is that HIGH should have to compensate for their high ping themselves. This would require us to implement an unequal and asymmetrical way of handling latency.* 

*It feels bad to get shot when you think you&#39;re behind cover due to bad ping, which is what can happen to LOW. It also feels bad to get shot by somebody before you could even see them due to bad ping, which is what can happen to HIGH. But the nonsense is distributed symmetrically.*

We want to be super clear: not all online games work the way Apex does. Some games always give the advantage to players with lower ping, but we actively choose not to with our system. It’s a stance we’ve intentionally taken after looking at the tradeoffs and thinking seriously about fairness in online competition. 

To explain our system in simple terms, players with low ping don’t always have an advantage over high-ping players, and sometimes experience nonsense (to us, that’s a technical term). 

That’s a tradeoff which is designed intentionally into our system. But the upside is that you can play Apex Legends and play relatively well even if you have higher than average latency, which is really important for rural players, or for players in regions where connectivity is unstable. We believe we should reduce “nonsense” at every opportunity, but when we have to deal with less-than-ideal experiences, we want to do so in a way that’s equal and fair to all players.

This is the reason that almost any time you deal with a bit of nonsense like getting shot while behind a wall or getting hit right as you come around a corner, it’s probably due to unavoidable variation in latency between players and the way our system distributes it. Still, we’re committed to reducing this at every opportunity we get. Not only do we want everyone to have a fair experience, we also want you all to have a fun one.
### ***Some of my shots aren’t registering.***

Let’s talk about hit registration. A “no reg” or no-registration of a shot means you think you hit your target but the server basically disagreed. From your perspective, you get all sorts of confirmation in the form of blood spray and sounds, but no damage counter shows up. In a shooter like Apex Legends, this is extremely unpleasant. 

It can happen for a multitude of reasons. Sometimes, high latency or packet loss can cause your local simulation to become slightly out of sync with the server. You shot where you saw someone, but actually you were shooting where they had been previously. Unfortunately, you don’t find that out until your version of the world catches back up.

Sometimes, it’s just a bug with the game’s physics simulation. To give you instant feedback, we rely heavily on a concept called prediction. When you shoot, we know the ballistic of the weapon, so we can predict where the bullet is going locally without needing the server to tell you. This makes the game feel more responsive. 

Normally, the client and server agree, and the bullet goes where predicted. In the past, we’ve had some bugs with the way we were computing ballistics and bullet trajectories (for every weapon with a bullet size that was not a point, like sniper rifles for example). This kind of bug can be gnarly to detect, so we put a visual in place for our playtests to help people spot the issue right away. Sadly, this diagnostic code is too heavy to run in the live game (because of bandwidth concerns), so we can only rely on our internal testing.

![Apex Legends in game screenshot showcasing what happens when no reg and rollback happens.](https://drop-assets.ea.com/images/379EvaBghYjAs0SKW5VVzT/fcf373c1d05e48e2f86d530f0b8c22bf/image6.png.adapt.1920w.png?im=AspectCrop=%2816,9%29,xPosition=0.5,yPosition=0.5)

*Everytime a no-reg happens, we draw the hitbox and the trajectory of the bullet (approximately, the trajectory should bend a bit, but good enough!). It is a visual aid for us to know it happened and to help us when we go look at our server logs.*

There’s two ways we’re making progress here:

The first is by constantly digging into the different bugs that result in hit detection issues. We’ve been developing tools to automate detection, as well, so we can help developers avoid introducing any new ones. This will be an ongoing and continuous effort on our part.

**The second is to work with you!** When players send us clips of hit detection issues in action, it can help us figure out if there’s a bug we need to address. Often, we realize that clips we get sent actually have to do with a latency problem instead of a hit detection issue, so be sure to check your performance display before reporting a hit-reg issue. However, as mentioned above, we have found and resolved bugs this way in the past, so reporting can help us make the game better for everyone. Thank you in advance!
### ***What about bugs that prevent me from logging in, like “code:net?”***

“Code:net” is a generic error message that the game displays whenever your game timed out from the server. It can be caused by any number of issues, both on our end and yours. In fact, we’ve found that some of the most serious code:net bugs (and related bugs like code:leaf, etc.) might have more to do with Respawn&#39;s services supporting the game that may need to be investigated.

We’ve taken a number of steps to reduce the likelihood of a code:net bug occurring and many players are able to have their situation resolved after contacting our support team. If you’re unable to log in and are receiving the code:net message or another like it, please consider reporting it using [the EA help site](https://help.ea.com/en/).

Since code:net is a generic message, it might refer to any number of different problems. We’ve had some success in recent weeks of addressing some of these, but we know we have more to do. **Report issues to us and we’ll do our best to resolve them ASAP**. Trust us, we hate this bug as much as you.
### ON SERVER TICKRATE

Here comes the *big* one. We want to tackle it transparently. Plenty of players have asked us about our server tickrate and why we don’t simply increase from 20Hz like some other online shooters have. 

We’ve explained how tickrate impacts the overall refresh rate of what you see on screen, so this is a totally valid question. However, it’s trickier than you might think to compare one game’s tickrate to another’s*.* We’ll try to explain why. 

**The tickrate of a server is the number of simulations that the server runs per second**. It is a fixed number (see the section about slow-mo). Apex uses a snapshot-based replication model. This mostly means that at the end of every tick, the server saves the world state and replicates it to all clients. This includes a *lot* of information that allows our weapon, map, and Legends&#39; design to be of the highest fidelity. 

To be successful in Apex Legends, you have to pay attention to a whole lot of information happening all over the map. Tactical abilities getting used, or passives activating, or ultimates popping off, or care packages dropping in, or a new squad entering within range of Crypto&#39;s drone. We don&#39;t want players to miss any of it. And our designers are able to create toys and tools that can be truly global in nature. Many games *don’t* compute full world states on each tick, making it misleading to try to compare one game with another based on a single figure like “20Hz” vs. “30Hz.” 

The question is: *What exactly is happening during each tick?* We want the world state to be as accurate as possible, which is why our servers save the full world state on each tick. If we didn’t do this, it would probably save some of the CPU costs on our servers, but we would lose accuracy in our simulations, and that isn’t worth the risk. 

Put simply, the higher the tick rate, the higher the bandwidth sent to all players. If we were to move from a 20Hz server to a 60Hz server, it would mean multiplying the bandwidth the game uses by three. As of today, Apex Legends roughly consumes 60kB/s at the beginning of a game. A 60Hz server would consume 180kB/s. That may not sound like a lot, but it’s quite a bit, and we are always looking for ways to reduce the required bandwidth. 

*But why would it matter if the bandwidth went a little higher?* Keeping bandwidth costs low for games is much more critical than, say, for video streaming. For high-bandwidth applications (streaming, downloading, etc), jitter or hitches are easy to hide by buffering minutes of a stream, dropping stream quality, etc. You probably won&#39;t be shown jitter in a download, and you probably don&#39;t care that the speed is variable by a few or even hundreds of milliseconds. 

Games do not have this luxury. Skipping even a couple 50ms intervals can start to feel bad. Skipping a few more can send you into a death spiral of having to send you bigger and bigger updates to catch you back up. There are no exceptions to not getting you those updates, because your client needs a perfect state of the world to be accurate.

The above example shows how comparing tickrate between games is complicated, because the information contained in each tick varies. There’s another complication as well, which is that the limits on inputs that servers can receive and send out aren’t always the same even if they have the same tickrate. To be specific: in many games, if a server runs at 60Hz, it means the client can only send 60Hz inputs. If you run at 60fps it’s fine, but if your client runs at 120fps, you would lose half of your inputs. This is not the case in Apex Legends. We process variable rate of inputs fine. (As a side note, the higher your FPS is in Apex, the higher your bandwidth usage is as a result.)

Okay, so we’ve discussed some possible downsides that come with increasing server tickrate. But what about the upside of going from, say, 20Hz to 60Hz? *Come on, Respawn! Wouldn’t that make the servers three times faster and three times better? Just do it!*

Based on our findings, it would not result in a meaningfully different experience, and we want to explain why. 

For the sake of the argument, let’s assume that you’re averaging about 50ms ping, or latency. Remember that your ping measures the speed of a full round trip between your machine and the server. So assuming there are no other problems like fluctuating latency or hardware lag (eg. display devices introduce 20-50ms delay), the server will receive your input 25ms (half ping) after you press a button or flick your mouse. 

Since our servers are 20Hz, they update the world state every 50ms (1,000ms in each second / 20 ticks per second = 50ms per tick). So in the *worst-case* scenario, your inputs will be processed by the server after 75ms (25ms + 50ms). 

To figure out what that 75ms delay actually means in terms of your experience, you have to think about your frame rate. The math here can get tricky, but remember that in a 60fps game, each frame takes about 16.67ms (1,000ms in each second / 60 frames per second = 16.67ms per frame). If your inputs are being processed by the server after 75ms, as in our example above, and your game is running at 60fps, that means the lag between your input and its impact on the game is about five frames (75ms for each update / 16.67ms per frame = about 4.5 frames, and round it up to 5 frames since there’s no such thing as a half-frame). 

If you do all the same calculations above for a 60Hz server, you get 41.67ms for maximum delay between input and the server processing it (25ms ping + [1,000ms / 60 ticks per second = 16.67ms per tick] = 41.67ms). 

41.67ms is definitely better than 75ms, but what does it result in as far as frame-rate goes? Let’s again assume we’re running at 60fps. Each frame takes 16.67ms, so now the lag between your inputs and the server recognizing them is about three frames (41.67ms for each update / 16.67ms per frame = about 2.5 frames, round it up to 3 frames since there’s still no such thing as a half-frame). 

Put all this math together, and you realize that 20Hz servers result in about five frames of delay, and 60Hz servers result in three frames of delay. **So for triple the bandwidth and CPU costs, you can save two frames worth of latency in the** ***best-case*** **scenario.** The upside is there, but it isn’t massive, and it wouldn’t do anything for issues that are tied to plain old lag (like getting shot while in cover), ISP-level issues, or bugs (like with hit reg and slow-mo servers). 

Our example examined the upside of going from 20Hz to 60Hz. You can follow the math for other jumps, like from 20Hz to 30Hz or even 40Hz, and you’ll find that the gains in frame rate would be similarly quite small. You’d need to increase tick rate very drastically before you could really start to feel it—even the jump from 20Hz to 60Hz would feel like the difference between 58 FPS and 60 FPS. This difference isn’t nothing, but we sincerely believe that it isn’t enough to prioritize tickrate changes over other more efficient improvements we could be making.
### CLOSING THOUGHTS

We want to close by acknowledging something, which is the very real and genuine frustration that online issues cause for players. When you have to deal with lag, or no-regs, or slow-mo servers, it *sucks*. It takes you out of the game, and can feel very demotivating for you when you’re trying to grind ranked, or make some clutch plays with their friends, or just have a relaxing evening. 

Part of the challenge about talking about online issues then is that when we start explaining our systems, or our stance on issues like lag compensation or tickrate, it can start to feel really frustrating for players who just want the game to be better. If you have issues with latency, or server-crashing bugs, or account corruption issues, or any of the other challenges that you can come up against while playing Apex Legends, you probably don’t want to hear about what we’re *not* doing. 

Ultimately, we just want to make the game better. The better the online experience is for you, the more people will play the game, which allows us to keep doing the job we love. 

This is why, throughout this blog we’ve shared a number of improvements that we’re pursuing in the near future, including:

- Using real-time alerting that will allow us to identify problems and respond more quickly
- Implementing tools for identifying servers so we can remove and replace problematic servers rapidly
- Focusing on slow-mo servers—removing problematic servers is one step, but our goal is to make this drastically less common with code changes
- Reducing latency with better optimization of new features
- Fixing hit-reg bugs and building automated detection tools to help us avoid introducing new ones


But we want you to know that these aren’t the only things we’re doing. We’re working with partners from the server level to the ISP level to improve and invest in our online infrastructure, with the ultimate goal of seeing players report fewer issues and a better overall experience. We intend to say more about these efforts in a future post, when we’ve begun to see these efforts come to fruition. 

Our hope is that if we start to communicate more with you about the issues that concern us, we’ll begin to share more of a common language to talk about the root causes of the issues we’re dealing with. That’s why we wrote this blog post. We hope it explains our thought process and demystifies the technicalities of running an online shooter. And we hope it’s the start of more conversations to come.

Thank you for reading! 

- Samy (Ricklesauceur) &amp; the Apex Legends team

---

[*Play Apex Legends for free*](https://www.ea.com/games/apex-legends/play-now-for-free)** now on PlayStation 4, PlayStation 5, Xbox One, Xbox Series X|S, Nintendo Switch, and PC via Origin and Steam.*

*Follow Apex Legends on* [*Twitter*](https://twitter.com/PlayApex) *and* [*Instagram*](https://www.instagram.com/playapex/)*, subscribe to our* [*YouTube channel*](https://www.youtube.com/playapex%20)*, and check out our* [*forums*](https://answers.ea.com/t5/Apex-Legends/ct-p/apex-legends-en)*.*

*Sign up for our* [*newsletter*](https://www.ea.com/games/apex-legends/newsletter) *today to receive the latest Apex Legends news, updates, behind-the-scenes content, exclusive offers, and more (including other EA news, products, events, and promotions) by email.*

*This announcement may change as we listen to community feedback and continue developing and evolving our Live Service &amp; Content. We will always strive to keep our community as informed as possible. For more information, please refer to EA’s Online Service Updates at* [*https://www.ea.com/service-updates*](https://www.ea.com/service-updates)*.*

**Applicable platform account and platform subscription (sold separately) may be required. A persistent internet connection and EA account required. Age restrictions apply. Includes in-game purchases.*
