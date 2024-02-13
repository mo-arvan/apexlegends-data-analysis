import altair as alt
import pandas as pd
import streamlit as st
from altair import datum

from functools import partial
import src.chart_config as chart_config
from src import ttk_analyzer
from src.dynamic_filters import DynamicFilters
import numpy as np

# from st_btn_group import st_btn_group

print(f"Running {__file__}")


def plot_effective_dps(e_dps_plots, chart_x_axis, chart_y_axis):
    single_shot_accuracy_df = e_dps_plots["single_shot_accuracy_df"]
    auto_weapon_accuracy_df = e_dps_plots["auto_weapon_accuracy_df"]
    dps_df = e_dps_plots["dps_df"]

    single_accuracy_cdf_line = alt.Chart(single_shot_accuracy_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("cdf", axis=alt.Axis(title='CDF', format=".2f")),
    ).properties(
        title="Single Shot Accuracy CDF",
        width=400,
        height=400,
    )
    auto_weapon_accuracy_cdf_line = alt.Chart(auto_weapon_accuracy_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("cdf", axis=alt.Axis(title='CDF', format=".2f")),
    ).properties(
        title="Auto Weapon Accuracy CDF",
        width=400,
        height=400,
    )

    single_accuracy_pdf_line = alt.Chart(single_shot_accuracy_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("pdf", axis=alt.Axis(title='PDF', format=".2f")),
    ).properties(
        title="Single Shot Accuracy PDF",
        width=400,
        height=400,
    )
    auto_weapon_accuracy_pdf_line = alt.Chart(auto_weapon_accuracy_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("pdf", axis=alt.Axis(title='PDF', format=".2f")),
    ).properties(
        title="Auto Weapon Accuracy PDF",
        width=400,
        height=400,
    )

    chart_title = f'Effective DPS'

    dps_df["accuracy_quantile"] = dps_df["cdf"].apply(lambda x: round(x * 100, 2))

    if chart_x_axis == "Accuracy Quantile (%)":
        x_axis = alt.X('accuracy_quantile',
                       axis=alt.Axis(title='Accuracy Quantile (%)'), sort=None)
    elif chart_x_axis == "Accuracy (%)":
        x_axis = alt.X('accuracy',
                       axis=alt.Axis(title='Accuracy (%)'), sort=None)
    if chart_y_axis == "eDPS":
        y_axis = alt.Y('dps',
                       axis=alt.Axis(title='eDPS'),
                       scale=alt.Scale(zero=False))
    elif chart_y_axis == "Damage Dealt":
        y_axis = alt.Y('damage_dealt',
                       axis=alt.Axis(title='Damage Dealt'),
                       scale=alt.Scale(zero=False))

    dps_line = alt.Chart(dps_df).mark_line(
    ).encode(
        x=x_axis,
        y=y_axis,
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

    dps_points_line = alt.Chart(dps_df).mark_point().encode(
        x=x_axis,
        y=y_axis,
        shape=alt.Shape('weapon_name', legend=alt.Legend(title="Weapon")),
        color=alt.Color('weapon_name', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='category20')),
        tooltip=['weapon_name',
                 alt.Tooltip('accuracy', format=",.2f"),
                 alt.Tooltip("accuracy_quantile", format=",.2f"),
                 alt.Tooltip('dps', format=",.2f"),
                 alt.Tooltip("damage_dealt", format=",.2f"),
                 "how",
                 "accuracy_model"],
    )

    fig = (alt.layer(
        dps_line, dps_points_line,  # rules,  # points, ,  # , rules,  # text selectors,
    ).resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent',
    ))
    fig = fig.interactive()

    plot_list = [single_accuracy_cdf_line, auto_weapon_accuracy_cdf_line,
                 single_accuracy_pdf_line, auto_weapon_accuracy_pdf_line,
                 fig,
                 ]
    return plot_list

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
        line, selectors, dps_points_line, rules,  # points, ,  # , rules,  # text
    ).resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent',
    ))
    fig = fig.interactive()
    # saving the plot as html file

    return fig


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


@st.cache_data
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


st.set_page_config(
    page_title="Gun Meta Analysis",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
    }
)
gun_df, sniper_stocks_df, standard_stocks_df, fights_df, algs_games_df = load_data()

pre_selected_weapons = []
default_selection = {
    # "tournament_full_name": [order_dict["tournament_full_name"][0]],
    # "tournament_region": ["NA"],
    "weapon_name": ["R-99 SMG",
                    "Volt SMG",
                    "Alternator SMG",
                    "C.A.R. SMG",
                    "Prowler Burst PDW",
                    "Alternator SMG - Disruptor", ]
}

if "selected_weapons" in st.session_state:
    pre_selected_weapons = st.session_state["selected_weapons"]
else:
    pre_selected_weapons = default_selection["weapon_name"]

guns_slice_df = gun_df

guns_slice_df = guns_slice_df[np.logical_or(pd.isna(guns_slice_df["secondary_class"]),
                                            guns_slice_df["secondary_class"] == "Care Package")]

class_name_list = gun_df["class"].unique().tolist()
class_name_list = sorted(class_name_list, key=lambda x: chart_config.class_filter_order_dict.get(x, 0))

row_1_cols = st.columns([10, 85, 10])
row_2_class_columns = st.columns(len(class_name_list) + 1)

buttons = [
    # {"label": "👍",
    #  "value": "like",
    #  # "style": {"border-radius": "22px", "padding": "1px"}
    #  },
    # {"label": "👎",
    #  "value": "dislike",
    #  # "style": {"border-radius": "22px", "padding": "1px"}
    #  }
]

for class_name in class_name_list:
    buttons.append({"label": class_name,
                    "value": class_name,
                    # "style": {"border-radius": "22px", "padding": "1px"}
                    })

buttons_list = []
for i, class_name in enumerate(class_name_list):
    with row_2_class_columns[i + 1]:
        buttons_list.append(st.button(class_name,
                                      key=f"class_{class_name}_button",
                                      help=f"Select all the weapons in the {class_name} class",
                                      use_container_width=True
                                      ))

    if buttons_list[i]:
        weapons_to_add = guns_slice_df[guns_slice_df["class"] == class_name]["weapon_name"].unique().tolist()
        pre_selected_weapons.extend(weapons_to_add)
        pre_selected_weapons = list(set(pre_selected_weapons))

with row_1_cols[2]:
    container = st.container()
    with container:
        # st.write("Z")
        clear_all = st.button("Clear All",
                              key=f"clear_all_button",
                              help=f"Clear all the selected weapons",
                              use_container_width=True
                              )
    if clear_all:
        pre_selected_weapons = []
with row_1_cols[0]:
    st.write("Weapons:")
with row_1_cols[1]:
    pre_selected_weapons = sorted(pre_selected_weapons)
    selected_weapons = st.multiselect("Weapons:",
                                      guns_slice_df["weapon_name"].unique().tolist(),
                                      pre_selected_weapons,
                                      label_visibility="collapsed",
                                      key="selected_weapons")

#
# returned = st_btn_group(buttons=buttons,
#                         key=f"class",
#                         mode='buttons',
#                         theme="dark",
#                         size="small",
#                         align='left',
#                         gap_between_buttons=1,
#                         merge_buttons=True,
#                         return_value=True)


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

# st.session_state["filters"] = default_selection

filters_dict = {
    "class": "Class",
    "weapon_name": "Weapons",
}

# st.multiselect("Weapons:", guns_slice_df["weapon_name"].unique().tolist(), selected_weapons, key="selected_weapons")
misc_weapon_class_list = ["Past Care Package", "Future Reworks"]
class_name_list = filter(lambda x: x not in misc_weapon_class_list, class_name_list)

# plot_container = st.container()
options_container = st.expander(label="Configuration")

mag_button_list = [{"label": name, "value": name} for name in chart_config.mag_list]

with options_container:
    options_rows = []

    options_rows.append(st.columns(4))
    options_rows.append(st.columns(4))
    options_rows.append(st.columns(4))

    with options_rows[0][0]:
        selected_peek_time = st.slider("Peek Time (ms):",
                                       min_value=500,
                                       max_value=5000,
                                       value=2000,
                                       step=250,
                                       key="peek_time")

    with options_rows[0][1]:
        selected_health = st.selectbox("Health",
                                       chart_config.health_values_dict.keys(),
                                       index=4,
                                       key='health')

    with options_rows[0][2]:
        selected_evo_shield = st.selectbox('Evo Shield:', chart_config.evo_shield_dict.keys(), index=4,
                                           key='evo_shield')
    with options_rows[0][3]:
        selected_mag = st.selectbox('Mag (if applicable):',
                                    chart_config.mag_list,
                                    index=3,
                                    key='mag')

    with options_rows[1][3]:
        selected_helmet = st.selectbox('Helmet:', chart_config.helmet_dict.keys(), index=0, key='helmet')
    # with options_rows[0][5]:

    with options_rows[1][0]:
        selected_bolt = st.selectbox('Shotgun Bolt (if applicable):', ['White', 'Blue', 'Purple'], index=2, key='bolt')

    # with options_rows[1][1]:
    #     estimation_method_list = ["Expected Value"]
    #     selected_estimation_method = st.selectbox('Estimation Method:', estimation_method_list,
    #                                               index=0,
    #                                               key='estimation_method')

    # with options_rows[1][1]:
    #     estimation_method_list = ["Expected Value"]
    #     selected_estimation_method = st.selectbox('Estimation Method:', estimation_method_list,
    #                                               index=0,
    #                                               key='estimation_method')
    selected_estimation_method = "Expected Value"
    with options_rows[1][1]:
        selected_ability_modifier = st.selectbox('Ability Modifier:', chart_config.ability_modifier_list, index=0,
                                                 key='ability_modifier')

    with options_rows[1][2]:
        selected_shot_location = st.selectbox('Shot Location:',
                                              chart_config.shot_location_dict.keys(),
                                              index=0,
                                              key='shot_location')
    with options_rows[2][0]:
        chart_x_axis = st.selectbox('X Axis:', ["Accuracy Quantile (%)",
                                                "Accuracy (%)",
                                                ],
                                    index=0, key='x_axis')
    with options_rows[2][1]:
        chart_y_axis = st.selectbox('Y Axis:', ["eDPS",
                                                "Damage Dealt", ],
                                    index=0, key='y_axis')
    with options_rows[2][1]:
        # selected_stock = st.selectbox('Stock:', chart_config.stock_list, index=2, key='stock')
        selected_stock = "Purple"

conditions_dict = {
    "mag": selected_mag,
    "stock": selected_stock,
    "ability_modifier": selected_ability_modifier,
    "bolt": selected_bolt,
    "helmet": selected_helmet,
    "shield": selected_evo_shield,
    "shot_location": selected_shot_location,
    "estimation_method": selected_estimation_method,
    "peek_time": selected_peek_time,
    "health": selected_health,
}

# selected_guns = st.session_state.weapons_filters["weapon_name"]

chart_container = st.container()

if len(selected_weapons) == 0:
    st.write(f"Select at least one weapon.")
else:
    e_dps_plots = ttk_analyzer.get_e_dps_df(selected_weapons,
                                            guns_slice_df,
                                            sniper_stocks_df,
                                            standard_stocks_df,
                                            fights_df,
                                            conditions_dict)
    #
    altair_plot = plot_effective_dps(e_dps_plots, chart_x_axis, chart_y_axis)

    #
    with chart_container:
        st.altair_chart(altair_plot[4], use_container_width=True)
        cdf_cols = st.columns(2)
        cdf_cols[0].altair_chart(altair_plot[0], use_container_width=True)
        cdf_cols[1].altair_chart(altair_plot[1], use_container_width=True)

        pdf_cols = st.columns(2)
        pdf_cols[0].altair_chart(altair_plot[2], use_container_width=True)
        pdf_cols[1].altair_chart(altair_plot[3], use_container_width=True)

#
# expander = plot_container.expander(label='Raw Data')
# expander.dataframe(guns_slice_df)

print(f"Done")
