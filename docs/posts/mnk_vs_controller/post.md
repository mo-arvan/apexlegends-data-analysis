# Aim Assist Nerf and Its Effect on MnK vs. Controller Gap

## Abstract

This analysis explores how recent changes to aim assist have affected the performance gap between Mouse and Keyboard (MnK) and controller players in the Apex Legends ALGS tournaments. I analyzed the distribution of successful shots in close-range encounters during the ALGS Playoffs Year 4, Splits 1 and 2, using methods like the Empirical Probability Density Functions (ePDFs) and Empirical Complementary Cumulative Distribution Functions (eCCDFs). The findings indicate that these adjustments have reduced the performance disparities, with controller players maintaining a slight edge. 

## Introduction

The debate about Aim Assist Balance in Apex Legends' competitive scene has been ongoing. Season 22 marked a pivotal change: the developers adjusted controller aim assist and improved inventory management for controller users, potentially narrowing the performance gap between Mouse and Keyboard (MnK) and controller players. This analysis aims to explore the impact of this change on performance gap between MnK and controller players in the ALGS tournaments. 

By leveraging data from [ALS](https://www.patreon.com/hugodev), I can compare the shots hit between the two input methods. Through histograms, ePDFs, and eCCDFs, I can visualize the distribution of shots hit per input method and assess performance gaps. This analysis focuses on close-range engagements within 40 meters, assuming uniform combat scenarios across both inputs. I aim to demonstrate the performance parity between MnK and controller players in close-range fights. 

## Related Work

There has been several attempts to investigate the parity between controller and MnK in Apex Legends. [_sinxl_](reddit.com/user/_sinxl_) conducted a [statsitical analysis](reddit.com/r/CompetitiveApex/comments/10ywjdq/statistical_analysis_of_controllermk_at_algs/) on the performance of controller and MnK players in the ALGS 2023 London tournament using kills per player. They report statistically significant difference between the two input methods. Compared to their work, this analysis is far more granular since it considers shots hit for every time a player deals damage. The combined number of close range (<40 meters) damage events using close range weapons for ALGS Playoffs Y4, Splits 1 and 2 sums up to 62,535. 

In another [analysis](https://www.reddit.com/r/CompetitiveApex/comments/1azzuch/i_charted_out_the_kbm_vs_controller_accuracy_kd/?share_id=RmzGkqlhKSFpDgqNPVz0z), the user [giraffes-are-weird](https://www.reddit.com/user/giraffes-are-weird/) had presented a visualization of accuracy of top 500 R5 Reloaded (aim trainer based on Apex Legends) players. The visualization demonstrates an 8% average accuracy difference between MnK and controller players. This analysis is similar to the current work in that it compares the performance of MnK and controller players, but it focuses on accuracy rather than shots hit. This is because the events feed data does not provide information on shots missed. It is not clear how R5 Reloaded accuracy is reported. Furthermore, the performance in R5 Reloaded might not be directly transferable to the actual game as it lacks the complexity and the pressure of a real game in a tournament. 


## Methodology

Data for this analysis is sourced from the events feed on the [apexlegendsstatus.com/algs](apexlegendsstatus.com/algs) website, which records nearly every in-game action. For instance, to access detailed data for the tenth game of the [ALGS Playoffs Year 4](https://apexlegendsstatus.com/algs/Y4-Split2/ALGS-Playoffs/Global/Overview#tab-scoring):


Navigate to the specific game on the website.

![replay_analysis](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/10_replay_analysis.png?raw=true)


Click on "Indiv. analysis," then select "Events feed."

![events_feed](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/11_events_feed.png?raw=true)


In this section, you can find data entries like damage dealt by selecting a player and looking for the "Dealt X Damage" entries. For example, player MST Wxltzy dealt 54 damage by landing 4 out of 18 shots with a Havoc rifle from about 25 meters away. It's important to note that the ammo data is not always reliable, so I focus on the number of shots hit rather than shooting accuracy.

![damage_dealt](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/12_damage_events.png?raw=true)

This analysis assumes uniform engagement across both input methods in identically staged combat scenarios, though some limitations to this approach is discussed later. I also limit the focus to engagements within 40 meters. The weapons are limited to the list below:

Volt SMG,
R-99 SMG,
Alternator SMG,
C.A.R. SMG,
Prowler Burst PDW,

HAVOC Rifle,
VK-47 Flatline,
R-301 Carbine,

EVA-8 Auto,
Mozambique Shotgun,

Devotion LMG,
L-STAR EMG,
M600 Spitfire,

P2020,
RE-45 Auto

I use histograms to graph the ePDF of shots hit per input method, providing a visual comparison of performance gaps. For instance, an ePDF of 0.1 for 5 shots hit by MnK players implies that in all documented damage events, 10% involved exactly 5 successful hits.

Furthermore, through the eCCDF, I can assess the likelihood of a player hitting more than "X" shots. For example, if the eCCDF for 5 shots by MnK players is 0.3, this suggests that 30% of MnK-related damage events include more than 5 shots landed. Comparing these values between MnK and controller players enables us to explore which group is likelier to achieve higher hit counts.

By the end of this post, I aim to clearly demonstrate any performance gaps and ideally show minimal differences between the inputs across various combat scenarios.

### Results

Below are the ePDFs for shots hit during the ALGS Playoffs Year 4, Split 1 (left) and Split 2 (right). In these charts, red bars represent Controller players and blue bars represent MnK players. The x-axis shows the number of shots hit, and the y-axis indicates the probability density for each value.

![ePDF of shots hit for ALGS Playoffs Year 4, Split 1 and 2](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/13_epdf_algs_playoffs_y4s1_vs_y4s2.png?raw=true)

Following these, the eCCDFs for the same events demonstrate the probability of hitting more than "X" shots.


![eCCDF of shots hit for ALGS Playoffs Year 4, Split 1 and 2](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/14_eccdf_algs_playoffs_y4s1_vs_y4s2.png?raw=true)


In ALGS Playoffs Y4, S1, the eCCDF for 6 shots hit shows MnK players at 0.2 and controller players at 0.28. This means that on average, controller players are more likely to hit 6 consecutive shots compared to MnK players. This trend is consistent across various shot counts, showing a performance advantage for controller players. However, by ALGS Playoffs Y4, S2, this gap has narrowed to just 1%, highlighting a reduced performance disparity between the two inputs.

Visualizing the differences in performance between MnK and controller players offers further insight:

![eCCDF Diff between MnK and Controller players](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/15_eccdf_diff_algs_playoffs_y4s1_vs_y4s2.png?raw=true)

There's a visible reduction in disparity between the two input methods from ALGS Playoffs Y4, S1 to S2, suggesting the changes to Controller mechanics have effectively narrowed the performance gap in close-range combat scenarios.

The comparison between Playoffs Year 4 Split 2 and ALGS Championships Year 3, Split 2 underscores a similar, albeit more pronounced trend.

![ePDF and eCCDF comparison between ALGS Playoffs Y4, S2 and ALGS Championships Y3, S2](https://github.com/mo-arvan/apexlegends-data-analysis/blob/main/docs/posts/mnk_vs_controller/images/16_eccdf_diff_algs_champs_y3s2_vs_playoffs_y4s2.png?raw=true)

It is worth noting there are cases where MnK players outperform controller players, particularly in the 11-15 shots hit range. However, the difference is less than 1%, indicating a near parity in performance.

### Conclusion

The recent changes to aim assist have reduced the performance differences between MnK and controller players in close-range combat. This analysis shows that shots are now more evenly distributed between the two types of controls, although controller players still have a small advantage. The updates in Season 22 have made the game more competitive, allowing both input methods to perform similarly in ALGS tournaments. It's important for the future of the game that there is balance and fairness between the different control methods. Developers should keep reviewing and tweaking the aim assist to ensure the game stays fair and competitive for everyone. They should also make sure that controller players have a smooth experience with actions like looting and opening doors, without sacrificing the game’s integrity.

This analysis has its limitations. For instance, differences between MnK and controller players can vary greatly depending on each player's skills and style. Over time, the perception has grown that MnK is less effective than controllers because of the aim assist feature. Also, mastering the game requires many hours of playing ranked games, which can be more mentally demanding for MnK players. These factors might discourage skilled MnK players from competing at higher levels. Moreover, this analysis assumes that the combat scenarios are the same for both controls, which might not always reflect the true dynamics of the game. Other factors like the choice of weapons and legends might also influence the results.


### Future Work 

I have a few ideas for future work:

- Investigation on Zone Variability 
- Investigation on How Well Teams Predict Zones (e.g. comparing their position on the map at the start of zone 2 to the zone 3)
- The Impact of Successful Zone Predictions on Placement
- Analysis on Effective Time-to-Kill (eTTK) across tournaments and weapon metas. 
- [Follow-up](https://www.reddit.com/r/CompetitiveApex/comments/1enhlsn/apex_legends_s22_shockwave_weapon_meta_mnk_vs/) analysis on Weapon Meta, Providing Suggestions for Balancing

Let me know if you are interested in any of these topics or have other suggestions for future work. I'd be happy to answer any questions about this post. 