import logging

import altair as alt
# import plotly.express as px
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

logger.info("Loading data...")
# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")


def damage_plot_builder(damage_data_df, min_distance, max_distance):
    data_df = damage_data_df.copy()
    data_df = data_df.loc[(data_df["distance_median"] >= min_distance) & (data_df["distance_median"] <= max_distance)]

    bin_count = int(len(damage_data_df["hit_count"].unique()) / 2)

    base_chart = alt.Chart(damage_data_df)

    interval = alt.selection_interval(encodings=['x', 'y'])
    heatmap = base_chart.mark_rect().encode(
        x=alt.X('distance_median:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Distance (m)')),
        y=alt.Y('hit_count:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Hit Count')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Hit Count vs Distance Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=400,

    ).add_params(
        interval
    )

    epdf_line_plot = (base_chart
    .transform_filter(
        interval
    )
    .transform_density(
        density='hit_count',
        groupby=['player_input'],
        as_=['hit_count', 'epdf'],

    )
    .mark_line()
    .encode(
        x=alt.X('hit_count',
                # bin=alt.Bin(maxbins=bin_count),
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)),
        y='epdf:Q',
        color=alt.Color('player_input:N',
                        scale=alt.Scale(scheme='dark2'),
                        ),
        # color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        # tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],

    ).properties(
        title={"text": f"ePDF of Hit Count",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        # height=700,
        width=400,
    )
    )
    epdf_point_plot = (base_chart
    .transform_filter(
        interval
    )
    .transform_density(
        density='hit_count',
        groupby=['player_input'],
        as_=['hit_count', 'epdf'],

    )
    .mark_point(
        filled=True,
        size=25,
    ).encode(
        x=alt.X('hit_count',
                # bin=alt.Bin(maxbins=bin_count),
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)),
        y='epdf:Q',
        color=alt.Color('player_input:N',
                        scale=alt.Scale(scheme='dark2'),
                        ),
        tooltip=["player_input", "hit_count", alt.Tooltip("epdf:Q", format=".2f")],
    ))
    epdf_line_plot = epdf_line_plot + epdf_point_plot

    ecdf_line_plot = (base_chart
    .transform_filter(
        interval
    )
    .transform_density(
        density='hit_count',
        groupby=['player_input'],
        as_=['hit_count', 'ecdf'],
        cumulative=True,
    )
    # .transform_window(
    #     ecdf='cume_dist()',
    #     # as_=['hit_count', 'density'],
    #     groupby=['player_input'],
    #     sort=[{'field': 'hit_count'}],
    #     # cumulative=True
    # )
    .mark_line()
    .encode(
        x=alt.X('hit_count',
                # bin=alt.Bin(maxbins=bin_count),
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)),
        y='ecdf:Q',
        color=alt.Color(
            'player_input:N',
            # legend=None,
            scale=alt.Scale(scheme='dark2'),

        ),
        # color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=["player_input", "hit_count", "ecdf:Q"]
    ).properties(
        title={"text": f"eCDF of Hit Count",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        # height=700,
        width=400,
    )
    )

    ecdf_point_plot = (base_chart
    .transform_filter(
        interval
    )
    .transform_density(
        density='hit_count',
        groupby=['player_input'],
        as_=['hit_count', 'ecdf'],
        cumulative=True,
    )
    .mark_point(
        filled=True,
        size=25,
    ).encode(
        x=alt.X('hit_count',
                # bin=alt.Bin(maxbins=bin_count),
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)),
        y='ecdf:Q',
        color=alt.Color('player_input:N',
                        scale=alt.Scale(scheme='dark2'),
                        ),
        tooltip=["player_input", "hit_count", alt.Tooltip("ecdf:Q", format=".2f")],
    ))

    ecdf_line_plot = ecdf_line_plot + ecdf_point_plot

    # dist_plots = epdf_plot | ecdf_plot
    main_plot = alt.vconcat(heatmap, epdf_line_plot, ecdf_line_plot, center=True)

    # hcat = alt.hconcat(epdf_plot, ecdf_plot)
    # main_plot = alt.vconcat(heatmap, epdf_plot, ecdf_plot)
    # main_plot = edf_pdf_plot
    # print(main_plot)
    # , color_continuous_scale="Viridis"
    #  nbinsx=20, nbinsy=20
    # density_heatmap_plotly = px.density_heatmap(damage_data_df,
    #                                             x="distance_median",
    #                                             y="hit_count",
    #                                             marginal_x="histogram",
    #                                             marginal_y="histogram",
    #                                             # color_continuous_scale="Viridis",
    #                                             color_continuous_scale=px.colors.sequential.Plasma,
    #                                             nbinsx=10,
    #                                             nbinsy=12,
    #                                             # color="count()",
    #                                             title="Hit Count vs Distance Heatmap",
    #                                             labels={"distance_median": "Distance (m)", "hit_count": "Hit Count"},
    #                                             histfunc="sum",
    #                                             width=800,
    #                                             height=800,
    #                                             )

    return [main_plot], damage_data_df

    plot_df = players_grouped_df.sort_values(by="median_accuracy", ascending=False)
    plot_df["median_accuracy_rank"] = range(1, len(plot_df) + 1)

    fights_and_stats_data_df = weapons_data_df.merge(plot_df,
                                                     on=["player_hash", "player_name"],
                                                     how="inner")
    fights_and_stats_data_df = fights_and_stats_data_df.sort_values(by=["median_accuracy_rank"], ascending=True)

    median_accuracy_rank_top_k = fights_and_stats_data_df[
        fights_and_stats_data_df["median_accuracy_rank"] <= min(top_k, len(players_grouped_df))]
    box_plot_color = "gray"

    box_plot = (alt.Chart(median_accuracy_rank_top_k).mark_boxplot(
        extent="min-max",
        color=box_plot_color,
    ).encode(
        alt.X("accuracy:Q", axis=alt.Axis(title='Accuracy (%)'), scale=alt.Scale(zero=False)),
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        color=alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),
        fill=alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),

    ).properties(
        title={"text": f"Accuracy Box Plot",
               "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },

        # width=800,
        # height=700,
    ))

    median_overall_accuracy = weapons_data_df["accuracy"].median()

    high_accuracy_fights = weapons_data_df[weapons_data_df["accuracy"] >= median_overall_accuracy]

    high_accuracy_count_rank = high_accuracy_fights.groupby(["player_hash", "player_name"]).agg(
        high_accuracy_count=("accuracy", "count"),
        sum_opening_damage=("damage_dealt", "sum"),
    ).reset_index()

    high_accuracy_count_rank_merged = high_accuracy_count_rank.merge(players_grouped_df,
                                                                     on=["player_hash",
                                                                         "player_name"],
                                                                     how="left")

    high_accuracy_count_rank_merged["high_accuracy_ratio"] = high_accuracy_count_rank_merged["high_accuracy_count"] / \
                                                             high_accuracy_count_rank_merged["total_fights"]

    high_accuracy_count_rank_merged = high_accuracy_count_rank_merged.sort_values(
        by=["high_accuracy_count", "sum_opening_damage"], ascending=False)

    high_accuracy_count_rank_merged["high_accuracy_count_rank"] = range(1, len(high_accuracy_count_rank_merged) + 1)

    high_accuracy_fights = high_accuracy_fights.merge(high_accuracy_count_rank_merged,
                                                      on=["player_hash", "player_name"],
                                                      how="inner")

    high_accuracy_top_k = high_accuracy_fights[high_accuracy_fights["high_accuracy_count_rank"] <= top_k]

    high_accuracy_top_k = high_accuracy_top_k.sort_values(by=["high_accuracy_count", "sum_opening_damage"],
                                                          ascending=False)

    high_accuracy_top_k["one"] = 1

    players = high_accuracy_top_k["player_name"].unique().tolist()

    players = sorted(players, key=lambda x: x.lower())

    bar_plot = alt.Chart(high_accuracy_top_k).mark_bar().encode(
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        alt.X("one:Q", axis=alt.Axis(title="Count"), scale=alt.Scale(zero=False)),
        alt.Color("damage_dealt:N", legend=None, scale=alt.Scale(scheme='yelloworangered')),
        tooltip=alt.Tooltip(
            ['player_name', "weapon_name", "damage_dealt", 'shots', 'hits', "accuracy", "high_accuracy_count",
             "total_fights",
             "tournament_full_name", "tournament_region", "tournament_day", "game_title"
             ]),
    ).properties(

        title={"text": f"Number of Fights with Higher than Median Accuracy ({median_overall_accuracy:.2f})%",
               "subtitle": f"Text and color encode the damage dealt in the fight",
               "subtitleColor": "gray",
               },

        # width=100,
        # height=500,
    )

    bar_plot_text = bar_plot.mark_text(align="left",
                                       baseline="middle",
                                       color="white",
                                       dx=-20).encode(
        alt.X("one:Q", stack="zero"),
        text="damage_dealt:Q",
        color=alt.value("black")
    )

    bar_plot = bar_plot + bar_plot_text

    high_accuracy_count_rank_merged = high_accuracy_count_rank_merged.sort_values(
        by=["high_accuracy_ratio", "sum_opening_damage"],
        ascending=False)
    high_accuracy_count_rank_merged["high_accuracy_percent"] = high_accuracy_count_rank_merged[
                                                                   "high_accuracy_ratio"] * 100

    high_accuracy_count_rank_merged["high_accuracy_ratio_rank"] = range(1, len(high_accuracy_count_rank_merged) + 1)

    high_accuracy_top_k_ratio = high_accuracy_count_rank_merged[
        high_accuracy_count_rank_merged["high_accuracy_ratio_rank"] <= top_k]

    bar_plot_2 = alt.Chart(high_accuracy_top_k_ratio).mark_bar().encode(
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        alt.X("high_accuracy_percent:Q", axis=alt.Axis(title="%"), scale=alt.Scale(zero=False)),
        alt.Color("high_accuracy_count:N", legend=None, scale=alt.Scale(scheme='yelloworangered')),
        tooltip=alt.Tooltip(
            ['player_name', "sum_opening_damage", "high_accuracy_count",
             "total_fights",
             "mean_accuracy", "median_accuracy", "sum_shots", "sum_hits"
             ]),
    ).properties(
        title={"text": f"% Fights with Higher than Median Accuracy ({median_overall_accuracy:.2f})%",
               "subtitle": f"Text encode the damage dealt in the fight, color encode the number of fights with higher than median accuracy",
               "subtitleColor": "gray",
               },

    )

    sum_opening_damage_text = bar_plot_2.mark_text(align="left",
                                                   baseline="middle",
                                                   color="white",
                                                   dx=-25).encode(
        alt.X("high_accuracy_percent:Q", stack="zero"),
        text="sum_opening_damage:Q",
        color=alt.value("black")
    )

    bar_plot_2 = bar_plot_2 + sum_opening_damage_text

    altair_scatter_2 = alt.Chart(weapons_data_df).mark_circle(size=25).encode(
        alt.Y("shots", axis=alt.Axis(title='Shots'), scale=alt.Scale(zero=True)),
        alt.X('damage_dealt', axis=alt.Axis(title='Damage Dealt'), scale=alt.Scale(zero=True)),
        color=alt.Color('accuracy', legend=None, scale=alt.Scale(scheme='redyellowgreen')),
        tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
        # opacity=alt.Opacity("accuracy", legend=None, scale=alt.Scale(scheme='viridis')),
    ).properties(
        title="Accuracy Scatter Plot",
        # width=800,
        # height=700,
    )

    plot_list = [epdf_line_plot.interactive(), bar_plot, bar_plot_2, box_plot, altair_scatter_2]
    return plot_list, weapons_data_df


filters_container = st.sidebar.container()

damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.get_tournament_filters(
    algs_games_df, gun_stats_df, filters_container)

filter_unknown_inputs = filters_container.checkbox("Filter Unknown Inputs", value=True)

if filter_unknown_inputs:
    valid_inputs = ["Mouse & Keyboard", "Controller"]
    damage_events_filtered_df = damage_events_filtered_df.loc[
        damage_events_filtered_df["player_input"].isin(valid_inputs)]

min_distance = st.sidebar.number_input("Minimum Distance",
                                       min_value=1,
                                       max_value=1000,
                                       value=1,
                                       key="min_distance")
max_distance = st.sidebar.number_input("Maximum Distance",
                                       min_value=1,
                                       max_value=1000,
                                       value=1000,
                                       key="max_distance")

plots, raw_data = damage_plot_builder(damage_events_filtered_df, min_distance, max_distance)

st.altair_chart(plots[0], use_container_width=True)

# st.altair_chart(plots[1], use_container_width=True)

# TODO:
# interval selection
# - ePDF of damage dealt
# - eCDF of damage dealt
# - color per input

expander = st.expander(label='Raw Data')
expander.dataframe(raw_data[[
    "player_name",
    "team_name",
    "tournament_full_name",
    "tournament_day",
    "game_title",
    "game_map",
    "weapon_name",
    "class",
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
                   )
