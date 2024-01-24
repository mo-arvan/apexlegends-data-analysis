import altair as alt
import pandas as pd
import streamlit as st
from altair import datum

import src.chart_config as chart_config
from src import ttk_analyzer
from src.dynamic_filters import DynamicFilters


def plot_effective_ttk(effective_ttk_df, plot_container):
    chart_title = f'Effective TTK (eTTK)'


    line = alt.Chart(effective_ttk_df).mark_line(
    ).encode(
        x=alt.X('accuracy',
                axis=alt.Axis(title='Accuracy (%)'), sort=None),
        y=alt.Y('ttk',
                axis=alt.Axis(title='Effective TTK (ms) - Lower is Better'),
                scale=alt.Scale(zero=False)),
        color=alt.Color('weapon_name:N', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='category20')),
        # shape=alt.Shape('weapon'),
        tooltip=alt.value(None),
        # strokeDash=alt.StrokeDash("weapon", scale=alt.Scale(domain=list(weapon_to_stroke_dash.keys()),
        #                                                     range=list(weapon_to_stroke_dash.values())),
        #                           legend=alt.Legend(title="Weapon")),
        strokeDash=alt.StrokeDash("weapon_name", legend=alt.Legend(title="Weapon")),
        # strokeWidth=alt.value(3),
        # strokeDash="symbol",
    ).properties(
        title=chart_title,
        # width=800,
        height=750,
    )


    points_on_line = alt.Chart(effective_ttk_df).mark_point().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)'), sort=None),
        y=alt.Y('ttk', axis=alt.Axis(title='Effective TTK (ms) - Lower is Better'), scale=alt.Scale(zero=False)),
        shape=alt.Shape('weapon_name', legend=alt.Legend(title="Weapon")),
        color=alt.Color('weapon_name', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='category20')),
        tooltip=['weapon_name', 'accuracy', 'ttk', "how", "damage_dealt"],
    )

    # Create a selection that chooses the nearest point & selects based on x-value
    nearest = alt.selection_point(nearest=True,
                                  on='mouseover',
                                  fields=['accuracy'],
                                  empty=False)
    # # Transparent selectors across the chart. This is what tells us
    # # the x-value of the cursor
    selectors = alt.Chart(effective_ttk_df).mark_point().encode(
        x=alt.X('accuracy'),
        tooltip=alt.value(None),
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
    # text = line.mark_text(align='left', dx=-5, dy=10).encode(
    #     text=alt.condition(nearest, 'miss rate', alt.value(' ')),
    #     # shape=alt.Shape('weapon', legend=None),
    # )
    #
    # # Draw a rule at the location of the selection
    rules = alt.Chart(effective_ttk_df).mark_rule(color='gray').encode(
        x=alt.X('accuracy'),
        # tooltip=None,
    ).transform_filter(
        nearest
    )
    #
    # # Put the five layers into a chart and bind the data
    fig = (alt.layer(
        line, selectors, points_on_line, rules,  # points, ,  # , rules,  # text
    ).resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent',
    ))
    fig = fig.interactive()
    # saving the plot as html file

    plot_container.altair_chart(fig, use_container_width=True)


def plot_effective_ttk_interactive(gun_stats_df, sniper_stocks_df, standard_stocks_df):
    plot_container = st.container()

    guns_slice_df = gun_stats_df

    order_dict = {
        # "tournament_full_name": [
        #     'Pro League - Year 4, Split 1',
        #     'ALGS Championship - Year 3, Split 2',
        #     'LCQ - Year 3, Split 2',
        #     'ALGS Playoffs - Year 3, Split 2',
        #     'Pro League - Year 3, Split 2',
        #     'ALGS Playoffs - Year 3, Split 1',
        #     'Pro League - Year 3, Split 1',
        # ],
    }

    default_selection = {
        # "tournament_full_name": [order_dict["tournament_full_name"][0]],
        # "tournament_region": ["NA"],
        "weapon_name": ["R-99 SMG", "Volt SMG", "Alternator SMG", "C.A.R. SMG"],
    }
    # st.session_state["filters"] = default_selection

    filters_dict = {
        "class": "Class",
        "weapon_name": "Weapons",
    }

    dynamic_filters = DynamicFilters(guns_slice_df,
                                     filters_name="weapons_filters",
                                     filters_dict=filters_dict,
                                     order_dict=order_dict,
                                     default_filters=default_selection, )

    st.sidebar.write("Apply the filters in any order")
    dynamic_filters.display_filters(location="sidebar")

    weapons_filtered = dynamic_filters.filter_df()

    # st.sidebar.write("Batch Add:")
    # class_columns = st.sidebar.columns(2)
    # class_columns[0].button("SMG", use_container_width=True)
    # class_columns[1].button("AR", use_container_width=True)
    # class_columns[2].button("Marksman", use_container_width=True)
    # class_columns[3].button("Sniper")

    st.sidebar.selectbox("Health", chart_config.health_values_dict.keys(), index=0,
                         key='health')
    st.sidebar.selectbox('Evo Shield:', chart_config.evo_shield_dict.keys(), index=2, key='evo')
    st.sidebar.selectbox('Helmet:', chart_config.helmet_dict.keys(), index=1, key='helmet')
    st.sidebar.selectbox('Shot Location:', chart_config.shot_location_dict.keys(), index=0, key='shot_location')
    st.sidebar.selectbox('Mag (if applicable):',
                         chart_config.mag_list,
                         index=2, key='mag')
    st.sidebar.selectbox('Shotgun Bolt (if applicable):', ['White', 'Blue', 'Purple'], index=2, key='bolt')
    st.sidebar.selectbox('Stock:', ['White', 'Blue', 'Purple'], index=2, key='stock')
    st.sidebar.selectbox('Ability Modifier:', chart_config.ability_modifier_list, index=0,
                         key='ability_modifier')
    #
    # columns = st.sidebar.columns(2)
    # columns[0].button("Clear", key="clear_comparison", use_container_width=True)
    # columns[1].button("Add", key="add_to_comparison", use_container_width=True)

    selected_health = st.session_state["health"]
    selected_guns = st.session_state.weapons_filters["weapon_name"]
    selected_helmet = st.session_state["helmet"]
    selected_evo = st.session_state["evo"]
    selected_mag = st.session_state["mag"]
    selected_stock = st.session_state["stock"]
    selected_shot_location = st.session_state["shot_location"]
    selected_ability_modifier = st.session_state["ability_modifier"]
    selected_bolt = st.session_state["bolt"]

    conditions_dict = {"helmet": selected_helmet,
                       "shield": selected_evo,
                       "shot_location": selected_shot_location,
                       "mag": selected_mag,
                       "stock": selected_stock,
                       "health": selected_health,
                       "ability_modifier": selected_ability_modifier,
                       "bolt": selected_bolt}

    # effective_ttk_slice_df = effective_ttk_slice_df[
    #     (effective_ttk_slice_df["helmet"] == selected_helmet) &
    #     (effective_ttk_slice_df["shield"] == selected_evo) &
    #     (effective_ttk_slice_df["mag"] == selected_mag) &
    #     (effective_ttk_slice_df["stock"] == selected_stock) &
    #     (effective_ttk_slice_df["shot_location"] == selected_shot_location) &
    #     (effective_ttk_slice_df["chart_type"] == chart_type) &
    #     (effective_ttk_slice_df["ability_modifier"] == selected_ability_modifier)
    #     ]

    if selected_health == "0 - No Health" and selected_evo == "0 - No Shield":
        plot_container.write("Health and Evo Shield cannot be both 0.")
        return

    guns_data_df = ttk_analyzer.get_ttk_df(weapons_filtered, sniper_stocks_df, standard_stocks_df,
                                           conditions_dict)
    # if len(guns_data_df) == 0:
    #     plot_container.write("Select a scenario to plot")
    #     return

    plot_effective_ttk(guns_data_df, plot_container)
    #

    expander = plot_container.expander(label='Raw Data')
    expander.dataframe(guns_slice_df)
    # with open("data/README.md", "r") as f:
    #     expander.markdown(f.read())

    # on_change()
    # st.button('Hit me')
    # # st.data_editor('Edit data', data)
    # st.checkbox('Check me out')
    # st.selectbox('Select', [1, 2, 3])
    # st.multiselect('Multiselect', [1, 2, 3])
    # st.slider('Slide me', min_value=0, max_value=10)
    # st.select_slider('Slide to select', options=[1, '2'])
    # st.text_input('Enter some text')
    # st.number_input('Enter a number')
    # st.text_area('Area for textual entry')
    # st.date_input('Date input')
    # st.time_input('Time entry')
    # st.file_uploader('File uploader')
    # # st.download_button('On the dl', data)
    # st.camera_input("一二三,茄子!")
    # st.color_picker('Pick a color')


def plot_using_altair_damage(damage_over_peek_time_df):
    # ttk_over_accuracy["miss rate"] = 100 - ttk_over_accuracy["accuracy"]
    damage_over_peek_time_df["time"] = damage_over_peek_time_df["time"].astype(int)

    slider = alt.binding_range(min=1, max=100, step=1, name='Accuracy (%):')
    # accuracy = alt.selection_point(name="accuracy", fields=["accuracy"], bind=slider)
    accuracy_param = alt.param(bind=slider, value=50)

    # ttk_over_accuracy["symbol"] =

    # shield_name = {0: "150", 1: "175", 2: "200", 3: "225"}
    # attachment_name = {0: "No", 1: "White", 2: "Blue", 3: "Purple"}
    #
    chart_title = f'Scenario: Jiggle Peek, Purple Mag, Body Shots'
    #
    # Plotting ttk over accuracy with different colors for each weapon
    line = alt.Chart(damage_over_peek_time_df).mark_line().encode(
        x=alt.X('time', axis=alt.Axis(title='Time (ms)')),
        y=alt.Y('damage', axis=alt.Axis(title='Damage')),
        color=alt.Color('weapon', legend=alt.Legend(title="Weapon")),
        # shape=alt.Shape('weapon', legend=None),
        tooltip=['weapon', 'damage', 'time'],
        strokeDash=alt.StrokeDash("weapon", legend=alt.Legend(title="Weapon")),
        # strokeWidth=alt.value(2),
        # strokeDashOffset="weapon",
        # strokeDash="symbol",
    ).properties(
        title=chart_title,
        # width=800,
        height=600,
    ).add_params(
        accuracy_param
    ).transform_filter(
        datum.accuracy == accuracy_param
    )
    points_on_line = alt.Chart(damage_over_peek_time_df).mark_point().encode(
        x=alt.X('time', axis=alt.Axis(title='Time (ms)')),
        y=alt.Y('damage', axis=alt.Axis(title='Damage')),
        shape=alt.Shape('weapon', legend=alt.Legend(title="Weapon")),
        color=alt.Color('weapon', legend=alt.Legend(title="Weapon")),
    ).add_params(
        accuracy_param
    ).transform_filter(
        datum.accuracy == accuracy_param
    )

    fig = (alt.layer(
        line, points_on_line,
    )
    .resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent', )
    )

    fig = fig.interactive()

    st.altair_chart(fig, use_container_width=True)
    st.slider('Accuracy (%)', min_value=1, max_value=100, value=50, step=1)


def plot_accuracy_histogram(weapons_data_df):
    weapons_data_df["accuracy"] = weapons_data_df["accuracy"].apply(lambda x: int(x))

    altair_chart = alt.Chart(weapons_data_df).mark_bar().encode(
        alt.X('accuracy', bin=alt.Bin(maxbins=100), axis=alt.Axis(title='Accuracy (%)'), scale=alt.Scale(zero=True)),
        y='count()',
        color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
    ).properties(
        title="Accuracy Histogram",
        # width=800,
        height=700,
    )

    weapons_data_df = weapons_data_df.sort_values(by=["accuracy", "shots", "hits"], ascending=False)

    st.altair_chart(altair_chart, use_container_width=True)

    # sorting based on median accuracy of each player
    players_median_accuracy = weapons_data_df.groupby("player_name").agg(median=("accuracy", "median"),
                                                                         count=("accuracy", "count"))

    players_median_accuracy = players_median_accuracy.sort_values(by="median", ascending=False)
    players_median_accuracy["order"] = range(1, len(players_median_accuracy) + 1)

    chart_title_info = ""
    if len(players_median_accuracy) > 20:
        chart_title_info = f" (Top 20 Players)"
    # sort players based on median accuracy
    weapons_data_df = weapons_data_df.merge(players_median_accuracy,
                                            on="player_name",
                                            how="inner")
    weapons_data_df = weapons_data_df.sort_values(by=["order"], ascending=True)

    top_20 = weapons_data_df[weapons_data_df["order"] <= 30]
    print(len(top_20))

    box_plot_color = "red"  # if st.theme() == 'Dark' else "black"

    box_plot = (alt.Chart(top_20).mark_boxplot(
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
        title=f"Accuracy Box Plot{chart_title_info}",
        # width=800,
        # height=700,
    ))

    # weapons_data_df = weapons_data_df.sort_values(by=["count"], ascending=False)
    top_20 = top_20.sort_values(by=["count"], ascending=False)

    bar_plot = alt.Chart(top_20).mark_bar().encode(
        alt.X("player_name:N", axis=alt.Axis(title='Player Name'), sort=None),
        alt.Y("count:Q", axis=alt.Axis(title='Count'), scale=alt.Scale(zero=False)),
        alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),
        tooltip=alt.Tooltip(['player_name', "weapon_name", 'shots', 'hits', "accuracy", "count"]),
    ).properties(
        title=f"Number of Shots{chart_title_info}",
        # width=800,
        # height=700,
    )
    st.altair_chart(box_plot, use_container_width=True)
    st.altair_chart(bar_plot, use_container_width=True)
    expander = st.expander(label='Raw Data')
    expander.dataframe(weapons_data_df, use_container_width=True)


def plot_accuracy_interactive(weapons_data_df, gun_stats_df):
    weapons_slice = weapons_data_df

    # tournament_menu_order_list = ["Pro League", "ALGS Championship", "ALGS Playoffs", "LCQ"]
    region_menu_order_list = ["NA", "EMEA", "APAC_N", "APAC_S", "SA", "Global"]
    # class_menu_order = ["SMG", "Marksman", "AR", "Sniper", "LMG", "Pistol"]
    tournament_full_name_menu_order_list = [
        'Pro League - Year 4, Split 1',
        'ALGS Championship - Year 3, Split 2',
        'LCQ - Year 3, Split 2',
        'ALGS Playoffs - Year 3, Split 2',
        'Pro League - Year 3, Split 2',
        'ALGS Playoffs - Year 3, Split 1',
        'Pro League - Year 3, Split 1',
    ]
    if "tournament_full_name" not in st.session_state:
        st.session_state["tournament_full_name"] = tournament_full_name_menu_order_list[0]
    selected_tournament_full_name = st.session_state["tournament_full_name"]

    tournament_list = weapons_slice["tournament_full_name"].unique().tolist()
    tournament_list = sorted(tournament_list, key=lambda x: tournament_full_name_menu_order_list.index(x))
    weapons_slice = weapons_slice[weapons_slice["tournament_full_name"] == selected_tournament_full_name]

    if "region" not in st.session_state:
        st.session_state["region"] = region_menu_order_list[0]

    selected_region = st.session_state["region"]
    region_list = weapons_slice["tournament_region"].unique().tolist()
    region_list = sorted(region_list, key=lambda x: region_menu_order_list.index(x))

    if selected_region not in region_list:
        selected_region = region_list[0]

    weapons_slice = weapons_slice[weapons_slice["tournament_region"] == selected_region]

    # if "year" not in st.session_state:
    #     st.session_state["year"] = 3
    # selected_year = st.session_state["year"]
    #
    # tournament_years = sorted(weapons_slice["tournament_year"].unique().tolist(), reverse=True)
    #
    # if selected_year not in tournament_years:
    #     selected_year = tournament_years[0]

    # weapons_slice = weapons_slice[weapons_slice["tournament_year"] == selected_year]

    # if "split" not in st.session_state:
    #     st.session_state["split"] = weapons_slice["tournament_split"].max()
    # selected_split = st.session_state["split"]
    #
    # tournament_splits = weapons_slice["tournament_split"].unique().tolist()
    # tournament_splits = sorted(tournament_splits, reverse=True)
    #
    # if selected_split not in tournament_splits:
    #     selected_split = tournament_splits[0]

    # weapons_slice = weapons_slice[weapons_slice["tournament_split"] == selected_split]

    if "day" not in st.session_state:
        st.session_state["day"] = weapons_slice["game_day"].max()

    selected_day = st.session_state["day"]

    tournament_days = weapons_slice["game_day"].unique().tolist()
    tournament_days = sorted(tournament_days, reverse=True)
    if selected_day not in tournament_days:
        selected_day = tournament_days[0]

    weapons_slice = weapons_slice[weapons_slice["game_day"] == selected_day]

    st.sidebar.selectbox("Tournament:", tournament_list, index=tournament_list.index(selected_tournament_full_name),
                         key="tournament")
    st.sidebar.selectbox("Region:", region_list, index=region_list.index(selected_region), key="region")
    # st.sidebar.selectbox("Year:", tournament_years, key="year", index=tournament_years.index(selected_year))
    # st.sidebar.selectbox("Split:", tournament_splits, key="split", index=tournament_splits.index(selected_split))
    st.sidebar.selectbox("Day:", tournament_days, key="day", index=tournament_days.index(selected_day))

    if "players" not in st.session_state:
        st.session_state["players"] = ["All"]

    selected_players = st.session_state["players"]
    missing_filters = []
    players_list = ["All"] + sorted(weapons_slice["player_name"].unique().tolist())
    # if len(selected_players) != 0:
    if len(selected_players) == 0:
        st.write("Select at least one player.")

    elif "All" not in selected_players:
        weapons_slice = weapons_slice[weapons_slice["player_name"].isin(selected_players)]

    st.sidebar.multiselect("Players:", players_list, selected_players, key="players")

    weapons_list = weapons_slice["weapon_name"].unique().tolist()
    if "weapons" not in st.session_state:
        st.session_state["weapons"] = [name for name in weapons_list if "SMG" in name]

    selected_weapons = st.session_state["weapons"]

    selected_weapons = [s for s in selected_weapons if s in weapons_list]

    st.sidebar.multiselect("Weapons:", weapons_list,
                           selected_weapons,
                           key="weapons")

    if len(selected_weapons) == 0:
        st.write(f"Select at least one weapon.")
        return
    else:
        weapons_slice = weapons_slice[weapons_slice["weapon_name"].isin(selected_weapons)]

        if "min_max_shots" not in st.session_state:
            max_shots = weapons_slice.shots.max()
            min_shots = round(weapons_slice.shots.min())
            st.session_state["min_max_shots"] = (min_shots, max_shots)

        min_max_shots = st.session_state["min_max_shots"]

        st.sidebar.slider("Shots Range", min_value=weapons_slice.shots.min(), max_value=weapons_slice.shots.max(),
                          value=(min_max_shots[0], min_max_shots[1]), key="min_max_shots")

        if "min_max_hits" not in st.session_state:
            max_hits = weapons_slice.hits.max()
            min_hits = round(weapons_slice.hits.min())
            st.session_state["min_max_hits"] = (min_hits, max_hits)

        min_max_hits = st.session_state["min_max_hits"]
        st.sidebar.slider("Hits Range", min_value=weapons_slice.hits.min(), max_value=weapons_slice.hits.max(),
                          value=(min_max_hits[0], min_max_hits[1]), key="min_max_hits")

        weapons_slice = weapons_slice[
            (weapons_slice["shots"] >= min_max_shots[0]) & (weapons_slice["shots"] <= min_max_shots[1])]
        weapons_slice = weapons_slice[
            (weapons_slice["hits"] >= min_max_hits[0]) & (weapons_slice["hits"] <= min_max_hits[1])]

        #                        menu_item_list,
        #                        selected_class_list,
        #                        key="class")
        # weapon_to_class_dict = gun_stats_df.set_index("weapon_name")["class"].to_dict()
        # weapons_slice["class"] = weapons_slice["weapon_name"].apply(lambda x: weapon_to_class_dict.get(x, "Unknown"))
        # unknown_counter = len(class_menu_order)
        #
        # def class_item_menu_func(x):
        #     if x not in class_menu_order:
        #         class_menu_order.append(x)
        #     return class_menu_order.index(x)
        #
        # if "class" not in st.session_state:
        #     st.session_state["class"] = [class_menu_order[0]]
        #
        # selected_class_list = st.session_state["class"]
        #
        # menu_item_list = weapons_slice["class"].unique().tolist()
        # menu_item_list = sorted(menu_item_list, key=class_item_menu_func)
        # # st.sidebar.multiselect("Class:",
        # selected_class_list = st.session_state["class"]
        # class_slice_weapons_data_df = weapons_slice[weapons_slice["class"].isin(selected_class_list)]
        #
        # selected_weapons = st.session_state["weapons"]
        # weapons_slice_df = weapons_slice_df[weapons_slice_df["weapon_name"].isin(selected_weapons)]

        # if len(weapons_slice) == 0:
        # else:
        plot_accuracy_histogram(weapons_slice)


# @st.cache_data
def load_data():
    gun_stats_df = pd.read_csv("data/guns_stats.csv")
    sniper_stocks_df = pd.read_csv("data/sniper_stocks.csv")
    standard_stocks_df = pd.read_csv("data/standard_stocks.csv")
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

    return gun_stats_df, sniper_stocks_df, standard_stocks_df, weapons_data_df, algs_games_df


def main():
    st.set_page_config(
        page_title="Effective TTK",
        page_icon="🧊",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            # 'Get Help': 'https://www.extremelycoolapp.com/help',
            # 'Report a bug': "https://www.extremelycoolapp.com/bug",
            # 'About': "# This is a header. This is an *extremely* cool app!"
        }
    )
    gun_stats_df, sniper_stocks_df, standard_stocks_df, weapons_data_df, algs_game_list_df = load_data()

    # st.sidebar.selectbox("Visualization Type:", ["Effective TTK", "Fights Accuracy Breakdown"], index=1,
    #                      key='analysis_type')
    # if "analysis_type" not in st.session_state:
    #     st.session_state["analysis_type"] = "Fights Accuracy Breakdown"
    #
    # st.sidebar.write("Visualization Type:")
    # st.sidebar.button("Effective TTK", key="effective_ttk", on_click=lambda: st.session_state.update(
    #     {"analysis_type": "Effective TTK"}), use_container_width=True)
    # st.sidebar.button("Fights Accuracy Breakdown", key="accuracy_breakdown", on_click=lambda: st.session_state.update(
    #     {"analysis_type": "Fights Accuracy Breakdown"}), use_container_width=True)
    # st.sidebar.divider()

    # analysis_type = st.session_state["analysis_type"]

    # gun_stats_df.to_csv("data/guns_stats.csv", index=False)

    plot_effective_ttk_interactive(gun_stats_df, sniper_stocks_df, standard_stocks_df)

    # if analysis_type == "Effective TTK":
    # else:
    #     plot_accuracy_interactive(weapons_data_df, gun_stats_df)

    # ttk_analyzer.plot_damage_over_peek_time(gun_stats_df)
    # st.divider()
    #
    # ttk_analyzer.visualize_gun_df(gun_stats_df)


if __name__ == "__main__":
    main()
    # st.title('Apex Legends Data Analysis')
    # st.subheader('SMGs In-depth Analysis')
    # st.write(
    #     'This analysis aims to provide a deeper understanding of the SMGs in Apex Legends. By the end of this analysis, we will have a better understanding of the SMGs in Apex Legends.')
    # st.latex(r''' e^{i\pi} + 1 = 0 ''')
    # tab1, tab2 = st.tabs(["Tab 1", "Tab2"])
    # intro = """
    # Ultimately in a fight, a player who deals the most damage wins.
    #
    # Time-to-kill (TTK) is the amount of time it takes to kill an enemy, is a common term in FPS games and is used to describe the amount of time it takes to kill an enemy.
    # The problem is in reality, the actual TTK differs from the theoretical TTK, since no one can hit all their shots.
    #
    # This leaves players to decide which weapon is the best based on "the feel"of the weapon.
    # This works fine for the most part, except it is not based on concrete data.
    # My current findings match the Pro Players' opinions, R99 is the best weapon in the game.
    #
    # But, let's try to figure out why.
    # """
    # # tab1.write(intro)
    # tab1.markdown(intro)  # see #*
    # tab2.write("this is tab 2")
