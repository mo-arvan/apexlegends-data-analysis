import logging

import altair as alt
import streamlit as st

import src.chart_config as chart_config
import src.streamtlit_helper as st_helper
from src import data_helper
from src import ttk_analyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="eDPS Calculator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
    }
)
with st.spinner("Loading data..."):
    gun_df, sniper_stocks_df, standard_stocks_df, fights_df, algs_games_df = data_helper.load_data()


def plot_effective_dps(e_dps_plots, chart_x_axis, chart_y_axis):
    dps_df = e_dps_plots["dps_df"]

    chart_title = f'Effective DPS'

    # dps_df["accuracy_quantile"] = dps_df["cdf"].apply(lambda x: round(x * 100, 2))

    x_axis, y_axis = None, None

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

    dps_line = alt.Chart(dps_df).mark_line(interpolate='step-before'
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

    dps_points_line = alt.Chart(dps_df).mark_point(
        size=100,
    ).encode(
        x=x_axis,
        y=y_axis,
        shape=alt.Shape('weapon_name', legend=alt.Legend(title="Weapon")),
        color=alt.Color('weapon_name', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='category20')),
        tooltip=['weapon_name',
                 alt.Tooltip('accuracy', format=",.2f"),
                 # alt.Tooltip("accuracy_quantile", format=",.2f"),
                 alt.Tooltip('dps', format=",.2f"),
                 alt.Tooltip("damage_dealt", format=",.2f"),
                 "how",
                 # "accuracy_model"
                 "ammo_left"
                 ],
    )

    fig = (alt.layer(
        dps_line, dps_points_line,  # rules,  # points, ,  # , rules,  # text selectors,
    ).resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent',
    ))
    fig = fig.interactive()

    plot_list = [fig,
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

selected_weapons = st_helper.get_gun_filters(gun_df, include_hop_ups=True)

filters_dict = {
    "class": "Class",
    "weapon_name": "Weapons",
}


selected_peek_time = st.sidebar.slider("Peek Time (ms):",
                                       min_value=500,
                                       max_value=5000,
                                       value=2000,
                                       step=250,
                                       key="peek_time")

selected_mag = st.sidebar.selectbox('Mag (if applicable):',
                                    chart_config.mag_list,
                                    index=3,
                                    key='mag')

selected_bolt = st.sidebar.selectbox('Shotgun Bolt (if applicable):',
                                     ['White', 'Blue', 'Purple'],
                                     index=2,
                                     key='bolt')

selected_health = st.sidebar.selectbox("Health",
                                       chart_config.health_values_dict.keys(),
                                       index=4,
                                       key='health')

selected_evo_shield = st.sidebar.selectbox('Evo Shield:',
                                           chart_config.evo_shield_dict.keys(),
                                           index=4,
                                           key='evo_shield')


selected_helmet = st.sidebar.selectbox('Helmet:',
                                       chart_config.helmet_dict.keys(),
                                       index=0,
                                       key='helmet')

selected_ability_modifier = st.sidebar.selectbox('Ability Modifier:',
                                                 chart_config.ability_modifier_list,
                                                 index=0,
                                                 key='ability_modifier')

selected_shot_location = st.sidebar.selectbox('Shot Location:',
                                              chart_config.shot_location_dict.keys(),
                                              index=0,
                                              key='shot_location')
chart_x_axis = st.sidebar.selectbox('X Axis:',
                                    [
                                        # "Accuracy Quantile (%)",
                                        "Accuracy (%)",
                                    ],
                                    index=0,
                                    key='x_axis')

chart_y_axis = st.sidebar.selectbox('Y Axis:',
                                    [
                                        "eDPS",
                                        "Damage Dealt",
                                        # "Rank"
                                    ],
                                    index=0,
                                    key='y_axis')
#     estimation_method_list = ["Expected Value"]
#     selected_estimation_method = st.selectbox('Estimation Method:', estimation_method_list,
#                                               index=0,
#                                               key='estimation_method')

#     estimation_method_list = ["Expected Value"]
#     selected_estimation_method = st.selectbox('Estimation Method:', estimation_method_list,
#                                               index=0,
#                                               key='estimation_method')
selected_estimation_method = "Expected Value"
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
                                            gun_df,
                                            sniper_stocks_df,
                                            standard_stocks_df,
                                            fights_df,
                                            conditions_dict)
    altair_plot = plot_effective_dps(e_dps_plots, chart_x_axis, chart_y_axis)

    with chart_container:
        st.altair_chart(altair_plot[0], use_container_width=True)

#
expander = st.expander(label='Raw Data')
expander.dataframe(gun_df)
