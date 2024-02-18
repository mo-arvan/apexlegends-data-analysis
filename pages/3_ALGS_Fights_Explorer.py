import logging

import altair as alt
import streamlit as st

import src.data_helper as data_helper
from src.dynamic_filters import DynamicFilters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="Fights Accuracy",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)

with st.spinner("Loading data..."):
    fights_df = data_helper.get_fights_data()


def accuracy_plots_builder(weapons_data_df, top_k):
    weapons_data_df["accuracy"] = weapons_data_df["accuracy"].apply(lambda x: int(x))

    players_grouped_df = weapons_data_df.groupby([
        "player_hash",
        "player_name",
        # "game_id",
    ]).agg(
        sum_shots=("shots", "sum"),
        sum_hits=("hits", "sum"),
        mean_accuracy=("accuracy", "mean"),
        median_accuracy=("accuracy", "median"),
        total_fights=("accuracy", "count")).reset_index()
    fights_count_median = players_grouped_df["total_fights"].median()
    players_grouped_df["mean_accuracy"] = players_grouped_df["mean_accuracy"].apply(lambda x: int(x))
    players_grouped_df["median_accuracy"] = players_grouped_df["median_accuracy"].apply(lambda x: int(x))

    histogram_plot = alt.Chart(weapons_data_df).mark_bar().encode(
        alt.X('accuracy', bin=alt.Bin(maxbins=100), axis=alt.Axis(title='Accuracy (%)'),
              scale=alt.Scale(zero=False)),
        y='count()',
        color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
    ).properties(
        title={"text": f"Accuracy Histogram",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
    )

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

    plot_list = [histogram_plot.interactive(), bar_plot, bar_plot_2, box_plot, altair_scatter_2]
    return plot_list, weapons_data_df


fights_df_slice = fights_df  # .head(1000)

order_dict = {
    "tournament_full_name": [
        'Pro League - Year 4, Split 1',
        'ALGS Championship - Year 3, Split 2',
        'LCQ - Year 3, Split 2',
        'ALGS Playoffs - Year 3, Split 2',
        'Pro League - Year 3, Split 2',
        'ALGS Playoffs - Year 3, Split 1',
        'Pro League - Year 3, Split 1',
    ],
}

default_selection = {
    "tournament_full_name": [order_dict["tournament_full_name"][0]],
    "tournament_region": ["NA"],
    "weapon_name": ["R-99 SMG", "Volt SMG", "Alternator SMG", "C.A.R. SMG"],
    "accuracy": (0, 100),
    "top_k": 20,
    "fights": 1,
}
# st.session_state["filters"] = default_selection

filters_dict = {
    "tournament_full_name": "Tournament",
    "tournament_region": "Region",
    "tournament_day": "Day",
    "player_name": "Player",
    "weapon_name": "Weapon",
    # "shots": "Shots",
    # "hits": "Hits",
    # "accuracy": "Accuracy",
    "game_num": "Game #",
}

dynamic_filters = DynamicFilters(fights_df_slice,
                                 filters_name="algs_filters",
                                 filters_dict=filters_dict,
                                 order_dict=order_dict,
                                 default_filters=default_selection, )

st.sidebar.write("Apply the filters in any order")
dynamic_filters.display_filters(location="sidebar")

weapons_filtered = dynamic_filters.filter_df()

accuracy_slider = st.sidebar.slider("Accuracy Range", min_value=0, max_value=100,
                                    value=(0, 100), key="accuracy")

weapons_filtered = weapons_filtered[weapons_filtered["accuracy"] >= accuracy_slider[0]]
weapons_filtered = weapons_filtered[weapons_filtered["accuracy"] <= accuracy_slider[1]]

fights_min_input = st.sidebar.number_input("Minimum # Fights", min_value=1, key="fights")

fights_per_player = weapons_filtered.groupby(["player_name",
                                              "player_hash"
                                              # "tournament_full_name",
                                              # "tournament_region",
                                              # "game_title",
                                              # "game_day"
                                              ]).agg(
    count=("accuracy", "count"),
).reset_index()

fights_per_player = fights_per_player[fights_per_player["count"] >= fights_min_input]

# if "top_k" not in st.session_state:
#     st.session_state["top_k"] = 19
players_withing_fights_range = weapons_filtered.merge(fights_per_player, on=["player_name",
                                                                             "player_hash",
                                                                             ],
                                                      how="inner")["player_name"].unique().tolist()

weapons_filtered = weapons_filtered[weapons_filtered["player_name"].isin(players_withing_fights_range)]

max_value = max(20, len(players_withing_fights_range))

top_k_slider = st.sidebar.number_input("Top K Players", min_value=1, max_value=max_value,
                                       value=20,
                                       key="top_k")

markdown_message_list = [f"**Warning**: attempting to load {len(weapons_filtered)} rows. \n",
                         "Loading this many rows may take a long time. Please apply more filters to reduce the number of rows.\n",
                         "Alternatively, check the 'Force Load Data' checkbox to load the data."]

# if len(weapons_filtered) > 10000:
#
#     # if "force_load_button" in st.session_state:
#     #     force_load_button = st.session_state["force_load_button"]
#     # else:
#     #     force_load_button = False
#     force_load_button = True
#     if force_load_button:
#         plots, raw_data = accuracy_plots_builder(weapons_filtered, top_k_slider)
#
#         for p in plots:
#             st.altair_chart(p, use_container_width=True)
#
#         expander = st.expander(label='Raw Data')
#         expander.dataframe(raw_data, use_container_width=True)
#
#     else:
#         for m in markdown_message_list:
#             st.markdown(m, unsafe_allow_html=True)
#         st.button("Force Load Data", key="force_load_button")
# else:
plots, raw_data = accuracy_plots_builder(weapons_filtered, top_k_slider)

st.altair_chart(plots[0], use_container_width=True)
st.altair_chart(plots[1], use_container_width=True)
st.altair_chart(plots[2], use_container_width=True)
st.altair_chart(plots[3], use_container_width=True)
st.altair_chart(plots[4], use_container_width=True)

# for p in plots:
# st.altair_chart(p, use_container_width=True)
#
expander = st.expander(label='Raw Data')
expander.dataframe(raw_data, use_container_width=True)

# TODO query params
# https://docs.streamlit.io/library/api-reference/utilities/st.query_params
