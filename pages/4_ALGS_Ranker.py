import logging

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import src.data_helper as data_helper
import src.streamtlit_helper as streamlit_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="ALGS Fights Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)


def get_player_ranking(input_df, minimum_damage):
    ranking_df = input_df[["player_id", "team_name", "game_id", "player_input", "hit_count", "damage_sum"]]
    ranking_details_df = input_df.loc[input_df["damage_sum"] >= minimum_damage]
    high_hit_df = ranking_df.loc[ranking_df["damage_sum"] >= minimum_damage]

    high_hit_per_game_df = high_hit_df.groupby(["player_id", "game_id"]).agg(
        hit_count=("hit_count", "count"),
    ).reset_index()

    high_hit_per_game_df = high_hit_per_game_df.groupby(["player_id"]).agg(
        max_hit_count_per_game=("hit_count", "max"),
        mean_hit_count_per_game=("hit_count", "mean"),
        median_hit_count_per_game=("hit_count", "median"),
    ).reset_index()

    high_hit_df = high_hit_df.groupby(["player_id"]).agg(
        high_hit_count=("hit_count", "count"),
    ).reset_index()

    all_hit_df = input_df.groupby(["player_id"]).agg(
        total_fights=("hit_count", "count"),
    ).reset_index()

    hash_character_df = input_df[["player_id", "game_id", "character"]].drop_duplicates()

    # find the most played character for each player
    player_character_count_df = hash_character_df.groupby(by=["player_id", "character"]).size().reset_index(
        name="count")

    # merge team names into a list
    player_id_team_name_df = input_df[["player_id", "team_name", "player_input"]].groupby(
        by=["player_id", "player_input"]).agg(
        team_name=("team_name", set)).reset_index()

    # median_count = player_character_count_df["count"].median()
    #
    # player_character_count_df = player_character_count_df.loc[player_character_count_df["count"] >= median_count]
    #
    # # find the max count for each player
    # # most_played_character = player_character_count_df.groupby("player_id").agg(
    # #     max_count=("count", "max")
    # # ).reset_index()
    #
    # # make a list of characters played
    # hash_character_df = hash_character_df.groupby("player_id").agg(
    #     characters=("character", list)
    # ).reset_index()

    player_character_list = []
    player_id_list = player_character_count_df["player_id"].unique().tolist()
    # for each player, find the top 3 most played characters
    for player_id in player_id_list:
        matching_df = player_character_count_df.loc[player_character_count_df["player_id"] == player_id]
        matching_df = matching_df.sort_values(by="count", ascending=False)
        matching_df = matching_df.head(1)
        # character_list = matching_df["character"].tolist()
        row = matching_df.iloc[0].to_dict()
        # for i, c in enumerate(character_list):
        player_character_list.append(row)

    player_character_df = pd.DataFrame(player_character_list, columns=["player_id", "character", "count"])

    player_character_df = player_character_df.merge(player_id_team_name_df, on="player_id", how="left")
    # most_played_character = most_played_character.
    # filtered_df = input_df.loc[
    #     damage_events_filtered_df["damage_sum"] >= minimum_damage]

    high_hit_df = high_hit_df.merge(all_hit_df, on=[
        "player_id",
        # "team_name",
        # "player_input"
    ], how="inner")

    high_hit_df = high_hit_df.merge(high_hit_per_game_df, on="player_id", how="left")

    high_hit_df = high_hit_df.merge(player_character_df, on="player_id", how="left")

    high_hit_df["high_hit_count_percentage"] = 100 * high_hit_df["high_hit_count"] / high_hit_df["total_fights"]

    high_hit_df["high_hit_count_percentage"] = high_hit_df["high_hit_count_percentage"].apply(
        lambda x: np.round(x, 2))

    high_hit_df["mean_hit_count_per_game"] = high_hit_df["mean_hit_count_per_game"].apply(
        lambda x: np.round(x, 2))
    high_hit_df["median_hit_count_per_game"] = high_hit_df["median_hit_count_per_game"].apply(
        lambda x: np.round(x, 2))

    high_hit_df["high_hit_count_percentage_str"] = high_hit_df[
        "high_hit_count_percentage"].apply(
        lambda x: f"{x:.2f} %")

    high_hit_df = high_hit_df.sort_values(by=[
        "high_hit_count",
        "high_hit_count_percentage"
    ],
        ascending=False)

    input_to_emoji_dict = {
        "Mouse & Keyboard": "💻",
        "Controller": "🎮",
    }

    high_hit_df["player_input"] = high_hit_df["player_input"].apply(lambda x: input_to_emoji_dict.get(x, "?"))

    # high_hit_df["characters"] = high_hit_df["player_id"].apply(lambda x: player_id_to_character_dict.get(x, ["?"]))

    high_hit_df["high_hit_count_rank"] = range(1, len(high_hit_df) + 1)

    high_hit_df = high_hit_df.sort_values(by="max_hit_count_per_game", ascending=False)

    high_hit_df["max_hit_count_per_game_rank"] = range(1, len(high_hit_df) + 1)

    high_hit_df = high_hit_df.sort_values(by="mean_hit_count_per_game", ascending=False)

    high_hit_df["mean_hit_count_per_game_rank"] = range(1, len(high_hit_df) + 1)

    high_hit_df = high_hit_df.sort_values(by="median_hit_count_per_game", ascending=False)

    high_hit_df["median_hit_count_per_game_rank"] = range(1, len(high_hit_df) + 1)

    ranking_details_df = ranking_details_df[[
        "player_id",
        "player_input",
        "team_name",
        "tournament_full_name",
        "tournament_day",
        "game_title",
        "game_map",
        "event_start_time",
        "weapon_name",
        # "class",
        "target",
        "distance_median",
        "hit_count",
        "damage_sum",
        "ammo_used",
        "distance",
        "damage",
        "event_time",
        "player_hash",
        "game_id",
    ]]

    return high_hit_df, ranking_details_df


def get_player_ranking_plot(input_df, minimum_damage, ranking_top_k, rank_column="high_hit_count"):
    high_hit_df, ranking_details_df = get_player_ranking(input_df, minimum_damage)

    high_hit_df = high_hit_df.sort_values(by=rank_column, ascending=False)

    high_hit_df = high_hit_df.head(ranking_top_k)

    # high_hit_ids = high_hit_df["player_id"].tolist()

    legends_df = data_helper.get_legends_data()

    high_hit_df = high_hit_df.merge(legends_df, on="character", how="left")

    # player_character_df["x"] = player_character_df["rank"].apply(lambda x: x * 2)

    # player_character_df = player_character_df.loc[player_character_df["player_id"].isin(high_hit_ids)]

    # height = 800
    height = 40 + ranking_top_k * 40

    chart_title = alt.TitleParams(f"Top Players Ranked based on # High Damage Encounters",
                                  subtitle=[f"Minimum Damage Dealt: {minimum_damage}, color indicates the input type.",
                                            ""],
                                  subtitleColor="#FFFFFF",
                                  fontSize=24,
                                  subtitleFontSize=16,
                                  anchor='start',
                                  # dx=50,
                                  # dy=25
                                  )

    color_scale = alt.Scale(
        # scheme='dark2',
        domain=["💻", "🎮", "?"],
        range=['darkred', 'darkblue', 'purple'],
    )

    # melt the characters list
    rank_bar_plot = alt.Chart(
        high_hit_df,
        title=chart_title
    ).mark_bar(
        cornerRadius=25,
        orient='horizontal',
    ).encode(
        x=alt.X(f"{rank_column}:Q",
                # axis=alt.Axis(chart_title="Count"),
                axis=None,
                # alt.Axis(
                #     title="",
                #     ticks=False,
                #     domain=False,
                #     grid=False,
                #     # offset=500,
                # ),
                scale=alt.Scale(zero=False)),

        y=alt.Y("player_id:N",
                axis=alt.Axis(title='',
                              offset=75,
                              ticks=False,
                              domain=False,
                              labelFontSize=12,
                              # labelFontWeight="bold",
                              labelColor="white"
                              ),
                sort=None,
                ),
        color=alt.Color("player_input:N",
                        legend=None,
                        # scale=alt.Scale(scheme='yelloworangered')
                        # use category10 for colors
                        # scale=alt.Scale(scheme='dark2'),
                        scale=color_scale,

                        ),
        tooltip=alt.Tooltip(
            [
                'player_id',
                # "characters"
                # "weapon_name",
                # "damage_sum:Q",
                # 'shots',
                # 'hits',
                # "accuracy",
                # "high_accuracy_count",
                # "total_fights",
                # "tournament_full_name",
                # "tournament_region",
                # "tournament_day",
                # "game_title"
            ]),
    ).properties(
        # width=100,
        width=800,
        height=height,
    )

    # rank_bar_plot = rank_bar_plot.interactive()

    #
    bar_plot_input_text = (rank_bar_plot.mark_text(
        align="center",
        baseline="middle",
        # color="white",
        fontStyle="bold",
        fontSize=20,
    )
    .encode(
        x=alt.value(-20),
        # text="player_input:N",
        text=alt.Text(
            "player_input:N",
            # axis=alt.Axis(offset=10),
        ),
        # text="damage_dealt:Q",
        # color=alt.value("black")
    ))

    # bar_plot_characters_text = (rank_bar_plot.mark_text(
    #     align="center",
    #     baseline="middle",
    #     # color="white",
    #     fontStyle="bold",
    #     fontSize=8,
    #     dx=-20).encode(
    #     x=alt.value(-5),
    #     text="characters:N",
    #
    #     color=alt.value("white")
    # ))

    legend_circles = (rank_bar_plot.mark_circle(
        size=1200,
        align="center",
        baseline="middle",
        #     # color="white",
        #     fontStyle="bold",
        #     fontSize=8,
        # dx=-200,
        # dy=-400
        # background="white",
        color="white",
    ).encode(
        x=alt.value(-60),
        # x=alt.X("x:Q",
        #         # axis=alt.Axis(title="", offset=-500),
        #         # axis=alt.Axis(offset=500,)
        #         ),
        # y="player_id:N",
        y=alt.Y("player_id:N",
                # axis=alt.Axis(title='',
                #               # offset=-50,
                #               ticks=True,
                #               domain=True,
                #               labelFontSize=12,
                #               # labelFontWeight="bold",
                #               labelColor="white"
                #               ),
                sort=None,
                ),

        # color="color:N",
        color=alt.value("white"),
        # color=alt.value("white"),
        tooltip="character:N"
    ))

    legend_image_mark = (rank_bar_plot.mark_image(
        # size=350,
        align="center",
        baseline="middle",
        #     # color="white",
        #     fontStyle="bold",
        #     fontSize=8,
        # dx=-200,
        # dy=-400
        # background="white",
        color="white",
        width=25,
        height=25
    ).encode(
        x=alt.value(-60),
        # x=alt.X("x:Q",
        #         # axis=alt.Axis(title="", offset=-500),
        #         # axis=alt.Axis(offset=500,)
        #         ),
        # y="player_id:N",
        y=alt.Y("player_id:N",
                # axis=alt.Axis(title='',
                #               # offset=-50,
                #               ticks=True,
                #               domain=True,
                #               labelFontSize=12,
                #               # labelFontWeight="bold",
                #               labelColor="white"
                #               ),
                sort=None,
                ),

        url="image:N",
        # color=alt.value("white"),
        tooltip="character:N"
    ))

    bar_plot_count_text = (rank_bar_plot.mark_text(
        align="center",
        baseline="middle",
        # color="white",
        # fontStyle="bold",
        fontSize=20,
        dx=-20
    ).encode(
        x=alt.X(f"{rank_column}:Q"),
        # y=alt.Y("player_name:N"),
        text=f"{rank_column}:Q",
        color=alt.value("white")
    ))

    bar_plot_percentage_text = rank_bar_plot.mark_text(align="center",
                                                       baseline="middle",
                                                       # color="white",
                                                       # fontStyle="bold",
                                                       fontSize=14,
                                                       dx=0).encode(
        x=alt.value(35),
        # text="high_hit_count_percentage:Q",
        # add percentage sign
        text=alt.Text("high_hit_count_percentage_str:N",
                      # format=".2 %",
                      ),

        color=alt.value("white")
    )

    # source = pd.DataFrame.from_records(
    #     [
    #         # {
    #         #     "x": 10.5,
    #         #     "y": 10.5,
    #         #     # "img": "https://vega.github.io/vega-datasets/data/ffox.png",
    #         #     "img": "https://apexlegendsstatus.com/assets/legends/humanesas/Bloodhound-transparent.png",
    #         # },
    #         {
    #             "x": 1.5,
    #             "y": 1.5,
    #             "img": "https://vega.github.io/vega-datasets/data/gimp.png",
    #         },
    #         {
    #             "x": 2.5,
    #             "y": 2.5,
    #             "img": "https://vega.github.io/vega-datasets/data/7zip.png",
    #         },
    #     ]
    # )
    #
    # p = alt.Chart(source).mark_image(width=50, height=50).encode(x="x", y="y", url="img")

    # bottom_title = alt.TitleParams(
    #     ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #     baseline='bottom',
    #     orient='bottom',
    #     anchor='end',
    #     fontWeight='normal',
    #     fontSize=10
    # )

    # + bar_plot_count_text
    rank_bar_plot = rank_bar_plot + bar_plot_input_text
    rank_bar_plot = rank_bar_plot + bar_plot_count_text
    rank_bar_plot = rank_bar_plot + bar_plot_percentage_text
    rank_bar_plot = rank_bar_plot + legend_circles + legend_image_mark

    # rank_bar_plot = legend_image_mark
    # rank_bar_plot = p
    rank_bar_plot = alt.concat(rank_bar_plot).properties(
        title=alt.TitleParams(
            ['Source: apexlegends-data-analysis.streamlit.app'],
            baseline='bottom',
            orient='bottom',
            anchor='start',
            fontWeight='normal',
            fontSize=10,
            dx=15,
            dy=15
        ),
    )

    # rank_bar_plot = alt.concat(rank_bar_plot).properties(
    #     chart_title=alt.TitleParams(
    #         ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #         baseline='bottom',
    #         orient='bottom',
    #         anchor='end',
    #         fontWeight='normal',
    #         fontSize=10
    #     ))
    # rank_bar_plot = alt.concat([rank_bar_plot, bottom_attribution])

    selected_df = high_hit_df.rename(columns={"player_id": "Name",
                                              "team_name": "Team",
                                              "player_input": "Input",
                                              "high_hit_count_rank": "Rank",
                                              "high_hit_count": "Count",
                                              "total_fights": "Total",
                                              "high_hit_count_percentage": "Percentage"})

    selected_df = selected_df[["Rank", "Name", "Input", "Count", "Total", "Percentage"]]

    response = (rank_bar_plot, selected_df, ranking_details_df)

    return response


def get_team_ranking_plot(input_df, minimum_damage, top_k, rank_column="high_hit_count"):
    high_hit_df, ranking_details_df = get_player_ranking(input_df, minimum_damage)

    # height = 800
    height = 40 + top_k * 40

    title = alt.TitleParams(f"Top Teams Ranked based on # High Damage Encounters",
                            subtitle=[f"Minimum Damage Dealt: {minimum_damage}, color indicates the input type.",
                                      ""],
                            subtitleColor="#FFFFFF",
                            fontSize=24,
                            subtitleFontSize=16,
                            anchor='start',
                            dx=50,
                            dy=25)

    rank_bar_plot = alt.Chart(high_hit_df,
                              title=title).mark_bar().encode(
        x=alt.X(f"{rank_column}:Q",
                # axis=alt.Axis(title="Count"),
                axis=None,
                scale=alt.Scale(zero=False)),
        y=alt.Y("team_name:N",
                axis=alt.Axis(title='',
                              offset=35,
                              ticks=False,
                              domain=False
                              ),
                # sort based on sum hit count
                sort=alt.EncodingSortField(
                    field="high_hit_count",
                    order="descending"
                ),
                ),
        color=alt.Color("player_id:O",
                        legend=None,
                        # scale=alt.Scale(scheme='yelloworangered')
                        # use category10 for colors
                        scale=alt.Scale(scheme='dark2')

                        ),
        tooltip=alt.Tooltip(
            [
                'player_id',
                # "weapon_name",
                # "damage_sum:Q",
                # 'shots',
                # 'hits',
                # "accuracy",
                # "high_accuracy_count",
                # "total_fights",
                # "tournament_full_name",
                # "tournament_region",
                # "tournament_day",
                # "game_title"
            ]),
    ).properties(
        # width=100,
        width=600,

        height=height,
    )

    # rank_bar_plot = rank_bar_plot.interactive()

    #
    bar_plot_input_text = (rank_bar_plot.mark_text(
        align="center",
        baseline="middle",
        # color="white",
        fontStyle="bold",
        fontSize=20,
        dx=-20)
    .encode(
        x=alt.value(-5),
        text="input:N",
        # text="damage_dealt:Q",
        # color=alt.value("black")
    ))

    bar_plot_count_text = (rank_bar_plot.mark_text(
        align="center",
        baseline="middle",
        # color="white",
        fontStyle="bold",
        fontSize=20,
        dx=-20).encode(
        x=alt.X(f"{rank_column}:Q"),
        y=alt.Y("team_name:N"),
        # y=alt.Y("player_name:N"),
        text=f"{rank_column}:Q",
        color=alt.value("white")
    ))

    bar_plot_percentage_text = rank_bar_plot.mark_text(align="center",
                                                       baseline="middle",
                                                       # color="white",
                                                       fontStyle="bold",
                                                       fontSize=12,
                                                       dx=0).encode(
        x=alt.value(35),
        # text="high_hit_count_percentage:Q",
        # add percentage sign
        text=alt.Text("high_hit_count_percentage_str:N",
                      # format=".2 %",
                      ),

        color=alt.value("white")
    )

    # bottom_title = alt.TitleParams(
    #     ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #     baseline='bottom',
    #     orient='bottom',
    #     anchor='end',
    #     fontWeight='normal',
    #     fontSize=10
    # )

    # + bar_plot_count_text
    # rank_bar_plot = rank_bar_plot + bar_plot_input_text
    # rank_bar_plot = rank_bar_plot + bar_plot_count_text
    # rank_bar_plot = rank_bar_plot + bar_plot_percentage_text

    rank_bar_plot = alt.concat(rank_bar_plot).properties(
        title=alt.TitleParams(
            ['Source: apexlegends-data-analysis.streamlit.app'],
            baseline='bottom',
            orient='bottom',
            anchor='start',
            fontWeight='normal',
            fontSize=10,
            dx=15,
            dy=15
        ),
    )

    # rank_bar_plot = alt.concat(rank_bar_plot).properties(
    #     title=alt.TitleParams(
    #         ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #         baseline='bottom',
    #         orient='bottom',
    #         anchor='end',
    #         fontWeight='normal',
    #         fontSize=10
    #     ))
    # rank_bar_plot = alt.concat([rank_bar_plot, bottom_attribution])

    selected_df = high_hit_df.rename(columns={"player_id": "Name",
                                              "team_name": "Team",
                                              "player_input": "Input",
                                              "high_hit_count_rank": "Rank",
                                              "high_hit_count": "Count",
                                              "total_fights": "Total",
                                              "high_hit_count_percentage": "Percentage"})

    selected_df = selected_df[["Rank", "Name", "Team", "Input", "Count", "Total", "Percentage"]]

    response = (rank_bar_plot, selected_df, ranking_details_df)

    return response


algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

filters_container = st.sidebar.container()

damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.get_tournament_filters(
    algs_games_df, gun_stats_df, filters_container)

minimum_damage = st.sidebar.number_input("Minimum Damage Dealt",
                                         min_value=1,
                                         max_value=1000,
                                         value=100,
                                         key="high_hit_count")

top_k = st.sidebar.number_input("Top K Players",
                                min_value=1,
                                max_value=100,
                                value=20,
                                key="top_k")

ranking_scenarios = st.sidebar.selectbox("Ranking Scenarios",
                                         ["Player Ranking", "Team Ranking"],
                                         key="ranking_scenarios")
# rank_column = "high_hit_count"
#     # rank_column = "max_hit_count_per_game"
#     # rank_column = "mean_hit_count_per_game"
#     # rank_column = "median_hit_count_per_game"

rank_by_dict = {
    "Sum High Hit Count": "high_hit_count",
    "Max Hit Count per Game": "max_hit_count_per_game",
    "Mean Hit Count per Game": "mean_hit_count_per_game",
    "Median Hit Count per Game": "median_hit_count_per_game",
}

ranking_by = st.sidebar.selectbox("Ranking By",
                                  rank_by_dict.keys(),
                                  key="ranking_by")

rank_column = rank_by_dict.get(ranking_by, "high_hit_count")

ranking_function = get_player_ranking_plot
if ranking_scenarios == "Team Ranking":
    ranking_function = get_team_ranking_plot

bar_plot, raw_data_1, raw_data_2 = ranking_function(damage_events_filtered_df,
                                                    minimum_damage,
                                                    top_k,
                                                    rank_column)

st.altair_chart(bar_plot, use_container_width=True)

expander = st.expander(label='Raw Data')
expander.dataframe(raw_data_1,
                   hide_index=True,
                   use_container_width=True)

expander.dataframe(raw_data_2)
