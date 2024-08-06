import logging

import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import src.chart_config as chart_config
import src.streamtlit_helper as st_helper
from src import data_helper
from src import damage_calculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

alt.renderers.enable("svg")

st.set_page_config(
    page_title="Effective Damage Over Accuracy",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
    }
)
with st.spinner("Loading data..."):
    gun_df, sniper_stocks_df, standard_stocks_df, algs_games_df = data_helper.load_data()


def plot_effective_dps_plotly(e_dps_plots, conditions_dict, chart_x_axis, chart_y_axis, chart_height=500):
    dps_df, dps_full_df, pivot_df = e_dps_plots["dps_df"], e_dps_plots["dps_full_df"], e_dps_plots["pivot_df"]

    global datum_to_name_dict
    global name_to_datum_dict

    chart_title = f'Effective {chart_x_axis}<br>Peek Time: {conditions_dict["peek_time_in_ms"]}ms'

    if chart_x_axis not in name_to_datum_dict:
        return None

    data_x_name = name_to_datum_dict[chart_x_axis]
    data_y_name = name_to_datum_dict[chart_y_axis]

    fig = px.line(
        dps_df,
        x=data_x_name,
        y=data_y_name,
        color='weapon_name',
        line_dash='weapon_name',  # Assumption made to replicate `strokeDash` behavior
        symbol='weapon_name',  # This assigns different symbols to different weapons
        title=chart_title,
        height=chart_height,
        color_discrete_sequence=px.colors.qualitative.Light24,
        render_mode='svg',
        # markers=True,
    )

    # Assuming `dps_full_df` has columns specified in tooltips and weapon_name for color encoding
    dps_points = px.scatter(
        dps_full_df,
        x=data_x_name,
        y=data_y_name,
        color='weapon_name',  # Automatically uses default color sequence
        symbol='weapon_name',  # This assigns different symbols to different weapons
        # hover_data={
        #     'weapon_name': True,
        #     'accuracy': ':.2f',
        #     "damage_dealt": ":.2f",
        #     "dps": ":.2f",
        #     "uncapped_damage_dealt": ":.2f",
        #     "uncapped_dps": ":.2f",
        #     "how": True,
        #     "shot_interval": ":.0f",
        #     "firing_time": ":.0f",
        #     "ammo_left": ":.0f",
        #     "reload_time": ":.0f",
        #     "holster_time": ":.0f",
        #     "deploy_time": ":.0f",
        #     "headshot_damage": ":.2f",
        #     "body_damage": ":.2f",
        #     "leg_damage": ":.2f"
        # }
    )

    # Update the existing line plot figure to add scatter plot
    # for data in dps_points.data:
    #     fig.add_trace(data)
    fig.update_traces(mode="markers+lines", hovertemplate=None)
    fig.update_layout(hovermode="x unified")
    # fig.update_traces(hoverinfo='none')
    fig.update_traces(marker={'size': 6})
    # Updating the colors based on 'weapon_name' if similar to dark2 color scheme is desired
    fig.update_traces(line=dict(width=2))  # This sets the line width similar to strokeWidth=3 in Altair
    fig.update_layout(
        # coloraxis_colorscale='dark2',
        legend_title_text='Weapon'  # This sets the legend title
    )

    evo_shield_amount = chart_config.evo_shield_dict[conditions_dict["shield"]]
    base_health_amount = chart_config.health_values_dict[conditions_dict["health"]]

    evo_shield_to_color_map = {
        125: "red",
        100: "mediumpurple",
        75: "blue",
        50: "gray",
        25: "white",
    }
    if evo_shield_amount > 0:
        color = evo_shield_to_color_map[evo_shield_amount]
        fig.add_vline(x=evo_shield_amount, line_dash="dash", line_color=color, annotation_text="Evo Shield")
    if base_health_amount > 0:
        fig.add_vline(x=evo_shield_amount + base_health_amount, line_dash="dash", line_color="pink",
                      annotation_text="Evo Shield + Health")

    # Customize Axis Titles if necessary
    fig.update_xaxes(title_text=chart_x_axis)
    fig.update_yaxes(title_text=chart_y_axis)

    plot_list = [fig,
                 ]

    return plot_list


def plot_effective_dps_altair(e_dps_plots, chart_x_axis, chart_y_axis):
    dps_df, dps_full_df, pivot_df = e_dps_plots["dps_df"].copy(), e_dps_plots["dps_full_df"].copy(), e_dps_plots[
        "pivot_df"].copy()

    weapon_names_list = dps_full_df["weapon_name"].unique().tolist()

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

    # dps_x_nearest = alt.selection_point(nearest=True,
    #                                     on='mouseover',
    #                                     fields=[data_x_name],
    #                                     empty=False)

    # # # Transparent selectors across the chart. This is what tells us
    # # # the x-value of the cursor
    # selectors = alt.Chart(dps_df).mark_point(
    #     color="white"
    # ).encode(
    #     # y=y_axis,
    #     x=x_axis,
    #     tooltip=alt.value(None),
    #     opacity=alt.value(0),
    #     # opacity=alt.condition(dps_x_nearest, alt.value(1), alt.value(0)),
    # ).add_params(
    #     dps_x_nearest
    # )

    dps_min_x_nearest = alt.selection_point(
        nearest=True,
        on='mouseover',
        fields=[f"min_{data_x_name}"],
        empty=False,
    )

    dps_points_plot = (alt.Chart(dps_full_df).mark_point(
        filled=True,
        opacity=1,
    ).encode(
        x=x_axis,
        y=y_axis,
        shape=alt.Shape('weapon_name', legend=alt.Legend(title="Weapon")),
        color=alt.Color('weapon_name', legend=alt.Legend(title="Weapon"), scale=alt.Scale(scheme='dark2')),
        # color=alt.condition(dps_x_nearest, alt.value("white"), alt.value("gray")),
        tooltip=[
            alt.Tooltip('weapon_name', title="Weapon"),
            alt.Tooltip('accuracy', format=",.2f", title="Accuracy (%)"),
            # alt.Tooltip("accuracy_quantile", format=",.2f"),
            alt.Tooltip("damage_dealt", format=",.2f", title="Damage Dealt"),
            alt.Tooltip('dps', format=",.2f", title="eDPS"),
            alt.Tooltip("uncapped_damage_dealt", format=",.2f", title="Uncapped Damage Dealt"),
            alt.Tooltip("uncapped_dps", format=",.2f", title="Uncapped eDPS"),
            alt.Tooltip("how", title="How", ),
            alt.Tooltip("shot_interval", title="Shot Interval (ms)", format=",.0f"),
            alt.Tooltip("firing_time", title="Firing Time (ms)", format=",.0f"),
            # "accuracy_model"
            alt.Tooltip("ammo_left", format=",.0f", title="Ammo Left"),
            alt.Tooltip('reload_time', format=".0f", title="Reload Time (ms)"),
            alt.Tooltip('holster_time', format=",.0f", title="Holster Time (ms)"),
            alt.Tooltip('deploy_time', format=",.0f", title="Deploy Time (ms)"),
            alt.Tooltip('headshot_damage', format=",.2f", title="Headshot Damage"),
            alt.Tooltip('body_damage', format=",.2f", title="Body Damage"),
            alt.Tooltip('leg_damage', format=",.2f", title="Leg Damage"),

        ],
        size=alt.condition(dps_min_x_nearest, alt.value(300), alt.value(100)),
        # opacity=alt.condition(dps_min_x_nearest, alt.value(1), alt.value(0.8))
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
    min_x_tooltip = [alt.Tooltip(f"min_{data_x_name}:Q", format=".2f", title=f"Min {chart_x_axis}")]
    dps_rules = (alt.Chart(pivot_df)
    # .transform_aggregate(
    #     groupby=["weapon_name", data_x_name],
    #     min_y=f"min({data_y_name})",
    # )
    # .transform_pivot(
    #     pivot="weapon_name",
    #     value=data_y_name,
    #     groupby=[f"min_{data_x_name}"]
    # )
    .mark_rule(color='gray').encode(
        # y=y_axis,
        x=f"min_{data_x_name}:Q",
        tooltip=min_x_tooltip + [alt.Tooltip(field=c.replace(".", "\\."), type="quantitative", format=".2f") for c in
                                 weapon_names_list],
        opacity=alt.condition(dps_min_x_nearest, alt.value(1), alt.value(0)),
        # tooltip=None,
    ).add_params(
        dps_min_x_nearest
    )

        # .transform_filter(
        #     dps_x_nearest
        # )
    )
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
    text = (alt.Chart(dps_full_df).transform_aggregate(
        groupby=["weapon_name", data_x_name],
        min_y=f"min({data_y_name})",
    ).transform_calculate(
        line_text=alt.datum.weapon_name + " @ " + alt.datum.min_y + "%"  # + alt.datum[data_x_name] + " " +
    ).mark_text(
        align='center',
        dx=0,
        dy=-25,
        fontSize=14,
        color="white",

    ).encode(
        x=x_axis,
        y="min_y:Q",
        # text=alt.condition(dps_x_nearest,
        #                    alt.Text(data_y_name, format=".0f"),
        #                    alt.value(' ')),
        text=alt.Text("line_text:N"),
        opacity=alt.condition(dps_min_x_nearest, alt.value(1), alt.value(0))
        # shape=alt.Shape('weapon', legend=None),
    ))
    #

    # fig = dps_line
    fig = (alt.layer(
        dps_line, dps_rules, dps_points_plot,  # , text,
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


def get_selection_details(e_dps_plots, event, ):
    dps_df = e_dps_plots["dps_df"]

    selected_point_list = event["selection"]["points"]

    if len(selected_point_list) == 0:
        return None

    out_selected_point_list = []
    for point in selected_point_list:
        selected_weapon = dps_df[dps_df["weapon_name"] == point["legendgroup"]]
        selected_weapon = selected_weapon[selected_weapon[selected_x_axis] == point["x"]]
        selected_weapon = selected_weapon[selected_weapon[selected_y_axis] == point["y"]]
        out_selected_point_list.append(selected_weapon)
    selection_df = pd.concat(out_selected_point_list)
    selection_df = selection_df[column_orders]

    need_rounding = ["shot_interval", "firing_time", "reload_time",
                     "holster_time", "deploy_time",
                     "headshot_damage", "body_damage", "leg_damage",
                     "dps", "uncapped_dps", "damage_dealt",
                     "uncapped_damage_dealt"
                     ]
    for col in need_rounding:
        selection_df[col] = selection_df[col].round(3)

    selection_df.rename(columns=datum_to_name_dict, inplace=True)

    return selection_df


filter_container = st.sidebar.container()

selected_peek_time = filter_container.slider("Peek Time (ms):",
                                             min_value=100,
                                             max_value=5000,
                                             value=1000,
                                             step=50,
                                             key="peek_time_in_ms")

selected_weapons, selected_mag, selected_bolt, selected_stock = st_helper.get_gun_filters(gun_df,
                                                                                          filter_container,
                                                                                          mag_bolt_selection=True,
                                                                                          include_hop_ups=True,
                                                                                          include_reworks=True,
                                                                                          enable_tabs=True,
                                                                                          )

selected_weapons_df = gun_df[gun_df["weapon_name"].isin(selected_weapons)]

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
                                   index=3,
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
                                    "Damage Dealt",
                                    "Damage Dealt (Capped)",
                                    "eDPS",
                                    "eDPS (Capped)",
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

adjustment_expander = st.sidebar.expander("Weapon Adjustments")

base_weapon_condition = np.logical_or(pd.isna(gun_df["secondary_class"]),
                                      gun_df["secondary_class"] == "Care Package")
base_weapon_condition = np.logical_or(base_weapon_condition, gun_df["secondary_class"] == "Hop-Up")

base_weapons_df = gun_df[base_weapon_condition]

with adjustment_expander:
    base_weapon_name = st.selectbox("Base Weapon",
                                    base_weapons_df["weapon_name"].unique().tolist(),
                                    index=None,
                                    key="base_weapon_name")

    if base_weapon_name is None:
        st.write("Select a base weapon.")
    else:
        base_weapon_df = base_weapons_df[base_weapons_df["weapon_name"] == base_weapon_name].copy()

        if len(base_weapon_df) != 1:
            st.write("Report an issue.")
        else:
            base_weapon_damage = base_weapon_df["damage"].iloc[0]
            mag_4 = base_weapon_df["magazine_4"].iloc[0]
            adjusted_damage = st.number_input("Adjusted Damage",
                                              min_value=1,
                                              max_value=200,
                                              value=base_weapon_damage,
                                              step=1,
                                              key="adjusted_damage")
            adjusted_magazine_4 = st.number_input("Purple Magazine Size",
                                                  min_value=1,
                                                  max_value=200,
                                                  value=mag_4,
                                                  step=1,
                                                  key="adjusted_magazine_4")
            base_weapon_df["weapon_name"] = f"Adjusted {base_weapon_name}"
            base_weapon_df["damage"] = adjusted_damage
            base_weapon_df["magazine_4"] = adjusted_magazine_4

            selected_weapons_df = pd.concat([selected_weapons_df, base_weapon_df])

#             alt.Tooltip('weapon_name', title="Weapon"),
#             alt.Tooltip('accuracy', format=",.2f", title="Accuracy (%)"),
#             # alt.Tooltip("accuracy_quantile", format=",.2f"),
#             alt.Tooltip("damage_dealt", format=",.2f", title="Damage Dealt"),
#             alt.Tooltip('dps', format=",.2f", title="eDPS"),
#             alt.Tooltip("uncapped_damage_dealt", format=",.2f", title="Uncapped Damage Dealt"),
#             alt.Tooltip("uncapped_dps", format=",.2f", title="Uncapped eDPS"),
#             alt.Tooltip("how", title="How", ),
#             alt.Tooltip("shot_interval", title="Shot Interval (ms)", format=",.0f"),
#             alt.Tooltip("firing_time", title="Firing Time (ms)", format=",.0f"),
#             # "accuracy_model"
#             alt.Tooltip("ammo_left", format=",.0f", title="Ammo Left"),
#             alt.Tooltip('reload_time', format=".0f", title="Reload Time (ms)"),
#             alt.Tooltip('holster_time', format=",.0f", title="Holster Time (ms)"),
#             alt.Tooltip('deploy_time', format=",.0f", title="Deploy Time (ms)"),
#             alt.Tooltip('headshot_damage', format=",.2f", title="Headshot Damage"),
#             alt.Tooltip('body_damage', format=",.2f", title="Body Damage"),
#             alt.Tooltip('leg_damage', format=",.2f", title="Leg Damage"),

column_orders = ["weapon_name",
                 "accuracy",
                 "uncapped_damage_dealt",

                 "how",
                 "ammo_left",
                 "shot_interval",
                 "firing_time",
                 "headshot_damage", "body_damage", "leg_damage",

                 "holster_time", "deploy_time", "reload_time",
                 "uncapped_dps",
                 "damage_dealt",
                 "dps",

                 ]

datum_to_name_dict = {
    "accuracy": "Accuracy (%)",
    "body_damage": "Body Damage",
    "uncapped_damage_dealt": "Damage Dealt",
    "accuracy_quantile": "Accuracy Quantile (%)",
    "weapon_name": "Weapon",
    "how": "How",
    "ammo_left": "Ammo Left",
    "shot_interval": "Shot Interval (ms)",
    "firing_time": "Firing Time (ms)",
    "reload_time": "Reload Time (ms)",
    "holster_time": "Holster Time (ms)",
    "deploy_time": "Deploy Time (ms)",
    "headshot_damage": "Headshot Damage",
    "leg_damage": "Leg Damage",
    "damage_dealt": "Damage Dealt (Capped)",
    "dps": "eDPS (Capped)",
    "uncapped_dps": "eDPS",

}

name_to_datum_dict = {v: k for k, v in datum_to_name_dict.items()}

selected_x_axis = name_to_datum_dict[chart_x_axis]
selected_y_axis = name_to_datum_dict[chart_y_axis]

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
    "peek_time_in_ms": selected_peek_time,
    "health": selected_health,
}

# selected_guns = st.session_state.weapons_filters["weapon_name"]

chart_container = st.container()

if len(selected_weapons) != 0:
    try:
        with st.spinner("Calculating eDPS..."):
            e_dps_plots = damage_calculator.calculate_damage_over_accuracy(selected_weapons_df,
                                                                           sniper_stocks_df,
                                                                           standard_stocks_df,
                                                                           conditions_dict)

            plotly_plot = plot_effective_dps_plotly(e_dps_plots, conditions_dict, chart_x_axis, chart_y_axis)
        # altair_plot = plot_effective_dps_altair(e_dps_plots, chart_x_axis, chart_y_axis)
        with chart_container:
            event = st.plotly_chart(plotly_plot[0], on_select="rerun")
            # expander = st.expander(label='Selection Details')
            selection_tab, weapon_stats_tab = st.tabs(["Selection Details", "Weapon Statistics"])

            selection_df = get_selection_details(e_dps_plots, event)

            with selection_tab:
                if selection_df is not None and len(selection_df) != 0:
                    st.dataframe(selection_df, hide_index=True)
                else:
                    st.write(
                        "Click on a point or use lasso or box select to see the details of the selection.")

            with weapon_stats_tab:
                gun_df.rename(columns=datum_to_name_dict, inplace=True)

                st.dataframe(gun_df, hide_index=True)

    # alt_chart = st.altair_chart(altair_plot[0], use_container_width=True)
    except Exception as e:
        st.error(f"Error in plotting the chart. {e}")
else:
    st.write(f"Select at least one weapon.")

#
# expander = st.expander(label='Weapon Statistics')
# expander.dataframe(gun_df)
