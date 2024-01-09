import sys

# import plotly
import altair as alt
import math
# import matplotlib.pyplot as plt
import pandas as pd
# import seaborn as sns
import streamlit as st
# import bokeh
# import bokeh.plotting
# import plotly.express
from altair import datum


# https://fonts.google.com/specimen/Saira+Extra+Condensed
# https://www.reddit.com/r/apexlegends/comments/13rtny9/the_foundational_flaw_of_apex_legends/
# https://apexlegendsstatus.com/algs/Y3-Split2/ALGS-Championships/Global/Overview#weaponsStats
# https://apexlegends.fandom.com/wiki/R-99_SMG
# The Alternator can be enhanced with Disruptor Rounds Disruptor Rounds, which increases damage dealt against shielded targets by 20%.
# level 1 against sheild 1
# https://docs.google.com/spreadsheets/d/1ipBvNmgK7-u2VJGlbNzsPvqydXhoRGM7Zxf6OBMvkpc/edit#gid=0
# https://docs.streamlit.io/library/api-reference/charts
# https://docs.streamlit.io/library/api-reference/charts/st.bokeh_chart
# https://blog.streamlit.io/host-your-streamlit-app-for-free/
# https://mybinder.org/

# tracking time over damage
# https://www.reddit.com/r/CrucibleGuidebook/comments/vrfvfb/ttk_simulator_based_on_your_weapon_and_estimated/
# high skill, requires high accuracy for lower ttk
# slow rpm, causes missed shots to be more punishing, hence has the highest skill ceiling

def get_effective_ttk(accuracy, total_health, weapon_primary, weapon_secondary):
    # effective accuracy is the accuracy of the weapon
    # if the weapon is the primary weapon
    # else it is the accuracy of the weapon if it is the secondary weapon
    attachment_rarity = 3

    weapon_name = weapon_primary["weapon_name"]
    # primary_damage = weapon_primary["damage"]
    # primary_rpm = weapon_primary["rpm"]
    # primary_mag = weapon_primary[f"magazine_{attachment_rarity + 1}"]
    # primary_reload_time = weapon_primary[f"reload_time_{attachment_rarity + 1}"]
    # primary_shot_interval = 60 / primary_rpm
    primary_head_multiplier = 1.25
    primary_leg_multiplier = 0.8
    # primary_lower_time = 0.35
    # secondary_raise_time = 0.35

    head_body_leg_distribution = [0.15, 0.7, 0.15]

    damage_primary = weapon_primary["damage"]
    damage_secondary = weapon_secondary["damage"]
    # primary_combination_damage = damage_primary * head_body_leg_distribution[0] * primary_head_multiplier + \
    #                              damage_primary * head_body_leg_distribution[1] + \
    #                              damage_primary * head_body_leg_distribution[2] * primary_leg_multiplier

    primary_effective_damage = damage_primary * accuracy

    # secondary_combination_damage = damage_secondary * head_body_leg_distribution[0] * primary_head_multiplier + \
    #                                damage_secondary * head_body_leg_distribution[1] + \
    #                                damage_secondary * head_body_leg_distribution[2] * primary_leg_multiplier

    secondary_effective_damage = damage_secondary * accuracy
    # effective ttk is tkk given the accuracy
    # when accuracy is 100, the effective ttk is equal to the ttk
    # however, when accuracy decreases, the effective ttk increases

    # number of reloads + number of shots required to kill

    if weapon_name == "Alternator Disruptor":
        # the first 125 damage has a 1.2 multiplier
        disruptor_damage = (damage_primary * 1.2) * accuracy
        shots_with_disruptor_damage = 125 / disruptor_damage
        disruptor_shots = math.ceil(shots_with_disruptor_damage)
        overshoot_damage = (disruptor_shots - shots_with_disruptor_damage) * primary_effective_damage
        health_left = total_health - 125 - overshoot_damage
        normal_shots = math.ceil(health_left / primary_effective_damage)
        primary_shots = disruptor_shots + normal_shots
    else:
        primary_shots = math.ceil(total_health / primary_effective_damage)

    primary_mag_size = weapon_primary[f"magazine_{attachment_rarity + 1}"]
    secondary_mag_size = weapon_secondary[f"magazine_{attachment_rarity + 1}"]

    secondary_shots = 0
    deploy_lower_sum_time = 0.
    reload_time = 0.

    if primary_shots > weapon_primary[f"magazine_{attachment_rarity + 1}"]:
        deploy_lower_sum_time = 0.35 + 0.3

        if weapon_name == "Alternator Disruptor":
            disruptor_damage = (damage_primary * 1.2) * accuracy
            shots_with_disruptor_damage = 125 / disruptor_damage
            disruptor_shots = math.ceil(shots_with_disruptor_damage)
            overshoot_damage = (disruptor_shots - shots_with_disruptor_damage) * primary_effective_damage
            health_left = total_health - 125 - overshoot_damage
            remaining_health = health_left - (primary_mag_size - disruptor_shots) * primary_effective_damage
        else:
            remaining_health = total_health - primary_mag_size * primary_effective_damage
        primary_shots = primary_mag_size
        secondary_shots = math.ceil(remaining_health / secondary_effective_damage)

        if secondary_shots > secondary_mag_size:
            reload_time = weapon_primary[f"reload_time_{attachment_rarity + 1}"]
            if secondary_shots > 2 * secondary_mag_size:
                raise Exception("Not enough ammo")

    primary_rpm = weapon_primary["rpm"]
    primary_shot_interval = 60 / primary_rpm
    secondary_rpm = weapon_secondary["rpm"]
    secondary_shot_interval = 60 / secondary_rpm

    ttk = (primary_shot_interval * (
            primary_shots - 1) + secondary_shot_interval * secondary_shots + deploy_lower_sum_time +
           reload_time)

    ttk = ttk * 1000

    return ttk


def get_ttk_over_accuracy(gun_df, shield_rarity, attachment_rarity, shot_location):
    health = 100
    shield_values = [50, 75, 100, 125]

    head_multiplier = 1.25
    leg_multiplier = 0.8
    head_body_leg_distribution = [0.15, 0.7, 0.15]

    # effective_accuracy = 0.75
    ttk_over_accuracy = []
    total_health = health + shield_values[shield_rarity]
    for idx, row in gun_df.iterrows():

        weapon = row["weapon_name"]
        # if weapon == "Alternator Disruptor":
        #     continue
        current_gun_ttk = []
        last_ttk = -1
        for accuracy in range(100, 39, -1):
            ttk = get_effective_ttk(accuracy / 100, total_health, row.to_dict(), row.to_dict())
            if ttk != last_ttk:
                ttk_over_accuracy.append((weapon, accuracy, ttk))
                last_ttk = ttk

    return ttk_over_accuracy


def plot_using_altair(ttk_over_accuracy, shield_attachment_rarity):
    ttk_over_accuracy = pd.DataFrame(ttk_over_accuracy, columns=["weapon", "accuracy", "ttk"])
    ttk_over_accuracy["miss rate"] = 100 - ttk_over_accuracy["accuracy"]
    ttk_over_accuracy["ttk"] = ttk_over_accuracy["ttk"].astype(int)

    # ttk_over_accuracy["symbol"] =

    shield_name = {0: "150", 1: "175", 2: "200", 3: "225"}
    attachment_name = {0: "No", 1: "White", 2: "Blue", 3: "Purple"}

    chart_title = f'Scenario: 1v1 close range, {shield_name[shield_attachment_rarity]} Health, {attachment_name[shield_attachment_rarity]} Mag, Body Shots'
    #
    # Plotting ttk over accuracy with different colors for each weapon
    line = alt.Chart(ttk_over_accuracy).mark_line().encode(
        x=alt.X('miss rate', axis=alt.Axis(title='Miss Rate (%)')),
        y=alt.Y('ttk', axis=alt.Axis(title='Effective TTK (ms) - Lower is Better'), scale=alt.Scale(zero=False)),
        color=alt.Color('weapon', legend=alt.Legend(title="Weapon")),
        shape=alt.Shape('weapon', legend=None),
        tooltip=['weapon', 'accuracy', 'ttk'],
        # strokeDash="symbol",
    ).properties(
        title=chart_title,
        width=800,
        height=600,
    )
    # Create a selection that chooses the nearest point & selects based on x-value
    nearest = alt.selection_point(nearest=True, on='mouseover',
                                  fields=['ttk'], empty=False)
    # # Transparent selectors across the chart. This is what tells us
    # # the x-value of the cursor
    selectors = alt.Chart(ttk_over_accuracy).mark_point().encode(
        y=alt.Y('ttk'),
        opacity=alt.value(0),
    ).add_params(
        nearest
    )
    #
    # # Draw points on the line, and highlight based on selection
    points = line.mark_point().encode(
        # y=alt.Y('ttk', axis=alt.Axis(title='Effective TTK (ms)')),
        opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
    )
    #
    # # Draw text labels near the points, and highlight based on selection
    text = line.mark_text(align='left', dx=-5, dy=10).encode(
        text=alt.condition(nearest, 'miss rate', alt.value(' ')),

    )
    #
    # # Draw a rule at the location of the selection
    rules = alt.Chart(ttk_over_accuracy).mark_rule(color='gray').encode(
        y=alt.Y('ttk'),
    ).transform_filter(
        nearest
    )
    #
    # # Put the five layers into a chart and bind the data
    fig = alt.layer(
        line, selectors, points, rules, text
    )
    fig = fig.interactive()
    # saving the plot as html file
    fig.save(f'plots/altair_effective_ttk_rarity_{shield_attachment_rarity}.html')

    st.altair_chart(fig, use_container_width=False)


def plot_ttk_over_accuracy(gun_df, shield_attachment_rarity=3):
    ttk_over_accuracy = get_ttk_over_accuracy(gun_df, shield_attachment_rarity, shield_attachment_rarity, "body")

    ttk_over_accuracy = pd.DataFrame(ttk_over_accuracy, columns=["weapon", "accuracy", "ttk"])

    # plot_using_seaborn(ttk_over_accuracy, shield_attachment_rarity)
    # plot_using_plotly(ttk_over_accuracy, shield_attachment_rarity)
    plot_using_altair(ttk_over_accuracy, shield_attachment_rarity)
    # plot_using_bokeh(ttk_over_accuracy, shield_attachment_rarity)
    # Set Seaborn style


# def plot_remaining_health_over_time(gun_df, shield_rarity, attachment_rarity, shot_location, accuracy):
#     health = 100
#     shield_values = [50, 75, 100, 125]
#
#     head_multiplier = 1.25
#     leg_multiplier = 0.8
#     head_body_leg_distribution = [0.15, 0.7, 0.15]
#
#     # effective_accuracy = 0.75
#     weapon_health_time_list = []
#
#     for idx, row in gun_df.iterrows():
#
#         weapon = row["weapon_name"]
#         damage = row["damage"]
#         rpm = row["rpm"]
#         mag = row[f"magazine_{attachment_rarity + 1}"]
#         reload_time = row[f"reload_time_{attachment_rarity + 1}"]
#         shield = shield_values[shield_rarity]
#         shot_interval = 60 / rpm
#
#         total_health = health + shield
#
#         effective_damage = damage * accuracy
#
#         if weapon == "Alternator Disruptor":
#             continue
#         weapon_health_time_list.append([weapon, total_health, 0])
#
#         for i in range(1, mag + 1):
#             remaining_health = max(total_health - effective_damage * i, 0)
#             weapon_health_time_list.append([weapon, remaining_health, shot_interval * i * 1000])
#
#         # for accuracy in range(50, 100):
#         #     effective_shot_to_kill = math.ceil(number_of_hits_to_kill / (accuracy / 100))
#         #     number_of_reloads = math.ceil(max(effective_shot_to_kill / mag - 1, 0))
#         #     ttk = shot_interval * effective_shot_to_kill + reload_time * number_of_reloads
#         #     ttk_over_accuracy.append([weapon, accuracy, ttk])
#     weapon_health_time_df = pd.DataFrame(weapon_health_time_list, columns=["weapon", "health", "time"])
#
#     # Set Seaborn style
#     sns.set(style="darkgrid")
#
#     # Plotting ttk over accuracy with different colors for each weapon
#     plt.figure(figsize=(8, 8))
#     sns.lineplot(x='time', y='health', data=weapon_health_time_df, hue='weapon', palette='Set2',
#                  style='weapon', markers=False, dashes=True, drawstyle="steps-post")
#     plt.title('Health over Time')
#     plt.xlabel('Time (ms)')
#     plt.ylabel('Remaining Health')
#     plt.legend(bbox_to_anchor=(.75, 1), loc='upper left')
#
#     # set the font
#     plt.rcParams['font.family'] = 'sans-serif'
#
#     plt.savefig(f'health_over_time_{accuracy}.svg')


def plot_using_altair_damage(damage_over_peak_time_df):
    # ttk_over_accuracy["miss rate"] = 100 - ttk_over_accuracy["accuracy"]
    damage_over_peak_time_df["time"] = damage_over_peak_time_df["time"].astype(int)

    slider = alt.binding_range(min=1, max=100, step=1, name='Accuracy (%):')
    # accuracy = alt.selection_point(name="accuracy", fields=["accuracy"], bind=slider)
    accuracy_param = alt.param(bind=slider, value=50)

    # ttk_over_accuracy["symbol"] =

    # shield_name = {0: "150", 1: "175", 2: "200", 3: "225"}
    # attachment_name = {0: "No", 1: "White", 2: "Blue", 3: "Purple"}
    #
    chart_title = f'Scenario: Jiggle Peak, Purple Mag, Body Shots'
    #
    # Plotting ttk over accuracy with different colors for each weapon
    line = alt.Chart(damage_over_peak_time_df).mark_line().encode(
        x=alt.X('time', axis=alt.Axis(title='Time (ms)')),
        y=alt.Y('damage', axis=alt.Axis(title='Damage')),
        color=alt.Color('weapon', legend=alt.Legend(title="Weapon")),
        shape=alt.Shape('weapon', legend=None),
        tooltip=['weapon', 'damage', 'time'],
        # strokeDash="symbol",
    ).properties(
        title=chart_title,
        width=800,
        height=600,
    ).add_params(
        accuracy_param
    ).transform_filter(
        datum.accuracy == accuracy_param
    )

    fig = line.interactive()

    st.altair_chart(fig, )


def get_damage_over_peak_time(gun_df):
    head_multiplier = 1.25
    leg_multiplier = 0.8
    head_body_leg_distribution = [0.15, 0.7, 0.15]

    # effective_accuracy = 0.75
    weapon_health_time_list = []
    for idx, row in gun_df.iterrows():

        weapon = row["weapon_name"]
        # if weapon == "Alternator Disruptor":
        #     continue

        weapon = row["weapon_name"]
        damage = row["damage"]
        rpm = row["rpm"]
        mag = row[f"magazine_{3 + 1}"]
        shot_interval = 60 / rpm
        current_weapon_damage_time_list = []
        for i in range(1, mag + 1):
            for accuracy in range(1, 101):
                effective_damage = damage * i * accuracy / 100
                if weapon == "Alternator Disruptor":
                    # the first 125 damage has a 1.2 multiplier
                    max_i = 125 / ((damage * 1.2) * accuracy / 100)
                    distrupter_damage = (damage * 0.2) * min(i, max_i) * accuracy / 100
                    effective_damage += distrupter_damage

                if effective_damage > 225:
                    effective_damage = 225
                weapon_health_time_list.append([weapon, effective_damage, accuracy, shot_interval * (i - 1) * 1000])

    return weapon_health_time_list


def plot_damage_over_peak_time(gun_df):
    damage_over_peak_time = get_damage_over_peak_time(gun_df)

    damage_over_peak_time_df = pd.DataFrame(damage_over_peak_time, columns=["weapon", "damage", "accuracy", "time"])

    plot_using_altair_damage(damage_over_peak_time_df)
    # the slower the rpm, the more punishing missed shots are
    # missing Kraber shots is more punishing than missing R99 shots

    # I prefer to


def main():
    print(sys.argv)
    close_gun_df = pd.read_csv("data/guns_close_range.csv")
    long_gun_df = pd.read_csv("data/guns_long_range.csv")

    # for accuracy in range(50, 101, 10):
    #     plot_remaining_health_over_time(close_gun_df, 3, 3, 1, accuracy / 100)

    plot_ttk_over_accuracy(close_gun_df, 3)

    plot_damage_over_peak_time(close_gun_df)

    # plot_ttk_over_accuracy(close_gun_df, 2)
    # plot_ttk_over_accuracy(close_gun_df, 1)
    # plot_ttk_over_accuracy(close_gun_df, 0)


if __name__ == "__main__":
    main()
