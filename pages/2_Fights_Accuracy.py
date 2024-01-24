import altair as alt
import pandas as pd
import streamlit as st

from src.dynamic_filters import DynamicFilters


def plot_accuracy_histogram(weapons_data_df):
    weapons_data_df["accuracy"] = weapons_data_df["accuracy"].apply(lambda x: int(x))

    grouped_df = weapons_data_df.groupby(["player_name"]).agg(
        shots=("shots", "sum"),
        hits=("hits", "sum"),
        accuracy=("accuracy", "mean"),
        count=("accuracy", "count")).reset_index()
    fights_count_median = grouped_df["count"].median()

    histogram_plot = alt.Chart(weapons_data_df).mark_bar().encode(
        alt.X('accuracy', bin=alt.Bin(maxbins=100), axis=alt.Axis(title='Accuracy (%)'),
              scale=alt.Scale(zero=False)),
        y='count()',
        color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
    ).properties(
        title="Accuracy Histogram",
        # width=800,
        # height=700,
    )

    st.altair_chart(histogram_plot, use_container_width=True)
    # markdown_text = f"25% Quantile: {weapons_data_df['accuracy'].quantile(0.25):.2f}%\n" \
    #                 f"50% Quantile: {weapons_data_df['accuracy'].quantile(0.50):.2f}%\n" \
    #                 f"75% Quantile: {weapons_data_df['accuracy'].quantile(0.75):.2f}%\n"
    # st.markdown(markdown_text, unsafe_allow_html=True)

    weapons_data_df = weapons_data_df.sort_values(by=["accuracy", "shots", "hits"], ascending=False)
    # sorting based on median accuracy of each player
    players_median_accuracy = weapons_data_df.groupby("player_name").agg(median=("accuracy", "median"),
                                                                         # count=("accuracy", "count")
                                                                         )

    players_median_accuracy = players_median_accuracy.sort_values(by="median", ascending=False)
    players_median_accuracy["median_accuracy_rank"] = range(1, len(players_median_accuracy) + 1)

    # sort players based on median accuracy
    weapons_data_df = weapons_data_df.merge(players_median_accuracy,
                                            on="player_name",
                                            how="inner")
    weapons_data_df = weapons_data_df.sort_values(by=["median_accuracy_rank"], ascending=True)

    k_top = min(30, len(players_median_accuracy))

    top_30 = weapons_data_df[weapons_data_df["median_accuracy_rank"] <= k_top]
    box_plot_color = "gray"  # if st.theme() == 'Dark' else "black"

    box_plot = (alt.Chart(top_30).mark_boxplot(
        extent="min-max",
        color=box_plot_color,
    ).encode(
        alt.X("player_name:N", axis=alt.Axis(title='Player Name'), sort=None),
        alt.Y("accuracy:Q", axis=alt.Axis(title='Accuracy (%)'), scale=alt.Scale(zero=False)),
        # alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),
        # tooltip=alt.Tooltip(['player_name', "weapon_name", 'shots', 'hits', "accuracy"]),
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

    high_accuracy_count_rank = high_accuracy_fights.groupby("player_name").agg(
        high_accuracy_count=("accuracy", "count"),
    ).reset_index()

    high_accuracy_count_rank = high_accuracy_count_rank.sort_values(by="high_accuracy_count", ascending=False)
    high_accuracy_count_rank["high_accuracy_count_rank"] = range(1, len(high_accuracy_count_rank) + 1)

    high_accuracy_fights = high_accuracy_fights.merge(high_accuracy_count_rank, on="player_name", how="inner")

    high_accuracy_top_30 = high_accuracy_fights[high_accuracy_fights["high_accuracy_count_rank"] <= 30]

    high_accuracy_top_30 = high_accuracy_top_30.sort_values(by=["high_accuracy_count"], ascending=False)

    high_accuracy_top_30["one"] = 1
    # weapons_data_df = weapons_data_df.sort_values(by=["count"], ascending=False)
    # top_30 = top_30.sort_values(by=["count"], ascending=False)

    bar_plot = alt.Chart(high_accuracy_top_30).mark_bar().encode(
        alt.X("player_name:N", axis=alt.Axis(title='Player Name'), sort=None),
        alt.Y("one:Q", axis=alt.Axis(title='Count'), scale=alt.Scale(zero=False)),
        alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=alt.Tooltip(
            ['player_name', "weapon_name", "damage_dealt", 'shots', 'hits', "accuracy", "high_accuracy_count"]),
    ).properties(
        title={"text": f"Number of Fights with Higher than Median Accuracy ({median_overall_accuracy:.2f})%",
               # "subtitle": f"Median Accuracy: {median_overall_accuracy:.2f}%",
               # "subtitleColor": "gray",
               },

        # width=800,
        # height=700,
    )

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

    st.altair_chart(bar_plot, use_container_width=True)
    st.altair_chart(box_plot, use_container_width=True)
    st.altair_chart(altair_scatter_2, use_container_width=True)

    expander = st.expander(label='Raw Data')
    expander.dataframe(weapons_data_df, use_container_width=True)


def plot_accuracy_interactive(weapons_data_df, gun_stats_df):
    weapons_slice = weapons_data_df  # .head(1000)

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
        "accuracy": (int(weapons_slice["accuracy"].quantile(0.75)), 100),
    }
    # st.session_state["filters"] = default_selection

    filters_dict = {
        "tournament_full_name": "Tournament",
        "tournament_region": "Region",
        "game_day": "Day",
        "player_name": "Player",
        "weapon_name": "Weapon",
        # "shots": "Shots",
        # "hits": "Hits",
        # "accuracy": "Accuracy",
        "game_num": "Game #",
    }

    dynamic_filters = DynamicFilters(weapons_slice,
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

    fights_per_player = weapons_filtered.groupby("player_name").agg(
        count=("accuracy", "count"),
    ).reset_index()
    min_fights = fights_per_player["count"].min()
    max_fights = fights_per_player["count"].max()
    fights_median = int(round(fights_per_player["count"].median()))

    fights_slider = st.sidebar.slider("Fights Range", min_value=min_fights, max_value=max_fights,
                                      value=(min_fights, max_fights), key="fights")

    fights_per_player = fights_per_player[fights_per_player["count"] >= fights_slider[0]]
    fights_per_player = fights_per_player[fights_per_player["count"] <= fights_slider[1]]

    players_withing_fights_range = fights_per_player["player_name"].tolist()

    weapons_filtered = weapons_filtered[weapons_filtered["player_name"].isin(players_withing_fights_range)]

    markdown_message_list = [f"**Warning**: attempting to load {len(weapons_filtered)} rows. \n",
                             "Loading this many rows may take a long time. Please apply more filters to reduce the number of rows.\n",
                             "Alternatively, check the 'Force Load Data' checkbox to load the data."]

    if len(weapons_filtered) > 10000:

        if "force_load_button" in st.session_state:
            force_load_button = st.session_state["force_load_button"]
        else:
            force_load_button = False

        if force_load_button:
            plot_accuracy_histogram(weapons_filtered)
        else:
            for m in markdown_message_list:
                st.markdown(m, unsafe_allow_html=True)
            st.button("Force Load Data", key="force_load_button")
    else:
        plot_accuracy_histogram(weapons_filtered)


@st.cache_data
def load_data():
    gun_stats_df = pd.read_csv("data/guns_stats.csv")
    # sniper_stocks_df = pd.read_csv("data/sniper_stocks.csv")
    # standard_stocks_df = pd.read_csv("data/standard_stocks.csv")
    weapons_data_df = pd.read_csv("data/weapons_data.csv")
    algs_games_df = pd.read_csv("data/algs_games.csv")

    gun_stats_df = gun_stats_df.sort_values(by=["weapon_name", "class"])
    # gun_stats_df.to_csv("data/guns_stats.csv", index=False)

    weapons_data_df = weapons_data_df[~pd.isna(weapons_data_df["weapon_name"])]
    # filter when hits > shots
    weapons_data_df = weapons_data_df[weapons_data_df["hits"] <= weapons_data_df["shots"]]

    weapons_data_df["accuracy"] = weapons_data_df["hits"] / weapons_data_df["shots"] * 100

    def map_weapon_name(name):
        relpace_dict = {
            # "R-99": "R99",
            "HAVOC": "HAVOC Turbo",
        }
        if name != "Charge Rifle":
            if name in relpace_dict:
                name = relpace_dict[name]
        return name

    invalid_weapon_names = ["Smoke Launcher", "Thermite Grenade", "Arc Star", "Frag Grenade", "Melee"]

    weapons_data_df = weapons_data_df[~weapons_data_df["weapon_name"].isin(invalid_weapon_names)]
    weapons_data_df["weapon_name"] = weapons_data_df["weapon_name"].apply(map_weapon_name)

    algs_games_df.loc[pd.isna(algs_games_df["tournament_region"]), "tournament_region"] = "NA"

    weapons_data_df = weapons_data_df.merge(algs_games_df, on=["game_id"], how="inner")

    return gun_stats_df, weapons_data_df  # , algs_games_df


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

main_gun_stats_df, main_weapons_data_df = load_data()
plot_accuracy_interactive(main_weapons_data_df, main_gun_stats_df)
