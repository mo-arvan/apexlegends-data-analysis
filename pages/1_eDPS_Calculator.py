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

alt.renderers.enable("svg")

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
    datum_to_name_dict = {
        "accuracy": "Accuracy (%)",
        "damage_dealt": "Damage Dealt",
        "dps": "eDPS",
        "uncapped_dps": "Uncapped eDPS",
        "uncapped_damage_dealt": "Uncapped Damage Dealt",
        "accuracy_quantile": "Accuracy Quantile (%)",
    }
    name_to_datum_dict = {v: k for k, v in datum_to_name_dict.items()}

    x_axis, y_axis = None, None

    if chart_x_axis not in name_to_datum_dict:
        return None

    data_x_name = name_to_datum_dict[chart_x_axis]

    x_axis = alt.X(data_x_name,
                   axis=alt.Axis(title=chart_x_axis),
                   sort=None)
    data_y_name = name_to_datum_dict[chart_y_axis]

    y_axis = alt.Y(data_y_name,
                   axis=alt.Axis(title=chart_y_axis),
                   scale=alt.Scale(zero=False))

    # Create a selection that chooses the nearest point & selects based on x-value
    # dps_x_y_nearest = alt.selection_point(nearest=False,
    #                                       on="mouseover",
    #                                       fields=[data_x_name, data_y_name],
    #                                       empty=False)

    dps_x_nearest = alt.selection_point(nearest=True,
                                        on='mouseover',
                                        fields=[data_x_name],
                                        empty=False)

    dps_line = alt.Chart(dps_df).mark_line(
        # interpolate='step-before',
        interpolate="linear",
        strokeWidth=3,
    ).encode(
        x=x_axis,
        y=y_axis,
        color=alt.Color('weapon_name:N',
                        legend=alt.Legend(title="Weapon"),
                        scale=alt.Scale(scheme='dark2')
                        ),
        # shape=alt.Shape('weapon'),
        tooltip=alt.value(None),
        # strokeDash=alt.StrokeDash("weapon", scale=alt.Scale(domain=list(weapon_to_stroke_dash.keys()),
        #                                                     range=list(weapon_to_stroke_dash.values())),
        #                           legend=alt.Legend(title="Weapon")),
        strokeDash=alt.StrokeDash("weapon_name",
                                  legend=alt.Legend(title="Weapon")
                                  ),
        # strokeWidth=alt.value(3),
        # strokeDash="symbol",
    ).properties(
        title=chart_title,
        # width=800,
        height=750,
    )
    # # # Transparent selectors across the chart. This is what tells us
    # # # the x-value of the cursor
    selectors = alt.Chart(dps_df).mark_point(
        color="white"
    ).encode(
        # y=y_axis,
        x=x_axis,
        tooltip=alt.value(None),
        opacity=alt.value(0),
    ).add_params(
        dps_x_nearest
    )

    dps_points_plot = (alt.Chart(dps_df).mark_point(
        filled=True,
        opacity=1,
    ).encode(
        x=x_axis,
        y=y_axis,
        shape=alt.Shape('weapon_name', legend=alt.Legend(title="Weapon")),
        # color=alt.Color('weapon_name', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='dark2')),
        color=alt.condition(dps_x_nearest, alt.value("white"), alt.value("gray")),
        tooltip=['weapon_name',
                 alt.Tooltip('accuracy', format=",.2f"),
                 # alt.Tooltip("accuracy_quantile", format=",.2f"),
                 alt.Tooltip('dps', format=",.2f"),
                 alt.Tooltip("damage_dealt", format=",.2f"),
                 alt.Tooltip("uncapped_dps", format=",.2f"),
                 alt.Tooltip("uncapped_damage_dealt", format=",.2f"),
                 "how",
                 # "accuracy_model"
                 "ammo_left",
                 alt.Tooltip('reload_time', format=",.2f"),
                 alt.Tooltip('holster_time', format=",.2f"),
                 alt.Tooltip('deploy_time', format=",.2f"),
                 alt.Tooltip('headshot_damage', format=",.2f"),
                 alt.Tooltip('body_damage', format=",.2f"),
                 alt.Tooltip('leg_damage', format=",.2f"),

                 ],
        size=alt.condition(dps_x_nearest, alt.value(100), alt.value(50)),
        # opacity=alt.condition(dps_x_nearest, alt.value(1), alt.value(0))
    )
        # .add_params(
        #     dps_x_nearest
        # )
    )

    # # Draw a rule at the location of the selection
    # epdf_rules = alt.Chart(dps_df).transform_pivot(
    #     "weapon_name:N",
    #     value=data_y_name,
    #     groupby=[data_x_name]
    # ).mark_rule(
    #     color="gray",
    #     strokeWidth=2,
    # ).encode(
    #     x=data_x_name,
    #     opacity=alt.condition(dps_nearest, alt.value(1), alt.value(0)),
    #     # tooltip=[alt.Tooltip(c, type="quantitative", format=".2f") for c in columns],
    # ).add_params(dps_nearest)

    # # Create a selection that chooses the nearest point & selects based on x-value

    #

    #
    # # # Draw a rule at the location of the selection
    dps_rules = (alt.Chart(dps_df).mark_rule(color='gray').encode(
        # y=y_axis,
        x=x_axis,
        # tooltip=None,
    ).transform_filter(
        dps_x_nearest
    ))
    #
    # # # Draw points on the line, and highlight based on selection
    # points = dps_line.mark_point().encode(
    #     # y=alt.Y('ttk', axis=alt.Axis(title='Effective TTK (ms)')),
    #     opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
    # )

    # r = dps_df[dps_df["dps"] > 90].groupby("weapon_name").agg({"accuracy": "min"}).reset_index()
    #
    # # plot the text for each line with the min accuracy to achieve at least nearest point y
    # h_line_text = alt.Chart(dps_df).transform_filter(
    #     nearest
    # ).transform_aggregate(
    #     groupby=["weapon_name"],
    #     min_x="min(accuracy)",
    # ).mark_text(align='left', dx=-5, dy=10).encode(
    #     x=alt.value(10),
    #     # y=y_axis,
    #     text=alt.Text('min_x:N', format=".2f"),
    #     color=alt.value("white"),
    # ).add_params(
    #     nearest
    # )

    #

    #
    # # Draw text labels near the points, and highlight based on selection
    text = alt.Chart(dps_df).mark_text(
        align='left',
        dx=-10,
        dy=-15,
        fontSize=14,
        color="white",

    ).encode(
        x=x_axis,
        y=y_axis,
        text=alt.condition(dps_x_nearest, data_x_name, alt.value(' ')),
        # shape=alt.Shape('weapon', legend=None),
    )
    #

    # fig = dps_line
    fig = (alt.layer(
        dps_line, selectors, dps_rules, dps_points_plot, text,
    ).resolve_scale(
        shape='independent',
        color='independent',
        strokeDash='independent',
    )
    )

    fig = fig.interactive()

    plot_list = [fig,
                 ]

    return plot_list




filter_container = st.sidebar.container()

selected_peek_time = filter_container.slider("Peek Time (ms):",
                                             min_value=500,
                                             max_value=5000,
                                             value=2000,
                                             step=100,
                                             key="peek_time")


selected_weapons, selected_mag, selected_bolt, selected_stock = st_helper.get_gun_filters(gun_df,
                                                                                          filter_container,
                                                                                          mag_bolt_selection=True,
                                                                                          include_hop_ups=True,
                                                                                          include_reworks=True,
                                                                                          enable_tabs=True,
                                                                                          )

filters_dict = {
    "class": "Class",
    "weapon_name": "Weapons",
}


with filter_container.expander("Advanced Configurations"):
    selected_health = st.selectbox("Health",
                                                 chart_config.health_values_dict.keys(),
                                                 index=4,
                                                 key='health')

    selected_evo_shield = st.selectbox('Evo Shield:',
                                                     chart_config.evo_shield_dict.keys(),
                                                     index=4,
                                                     key='evo_shield')

    selected_helmet = st.selectbox('Helmet:',
                                                 chart_config.helmet_dict.keys(),
                                                 index=0,
                                                 key='helmet')

    selected_ability_modifier = st.selectbox('Ability Modifier:',
                                                           chart_config.ability_modifier_list,
                                                           index=0,
                                                           key='ability_modifier')

    selected_shot_location = st.selectbox('Shot Location:',
                                                        chart_config.shot_location_dict.keys(),
                                                        index=0,
                                                        key='shot_location')
    chart_x_axis = st.selectbox('X Axis:',
                                              [
                                                  "Uncapped Damage Dealt",
                                                  "Damage Dealt",
                                                  "eDPS",
                                                  "Uncapped eDPS",
                                                  "Accuracy (%)",
                                                  # "Accuracy Quantile (%)",

                                              ],
                                              index=0,
                                              key='x_axis')

    chart_y_axis = st.selectbox('Y Axis:',
                                              [
                                                  # "Accuracy Quantile (%)",
                                                  "Accuracy (%)",
                                                  "eDPS",
                                                  "Damage Dealt",
                                                  "Uncapped eDPS",
                                                  "Uncapped Damage Dealt",
                                              ]

                                              ,
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
