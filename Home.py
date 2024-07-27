import streamlit as st
import time
st.set_page_config(
    page_title="Apex Legends Data Analysis",
    page_icon="📊",
    layout="wide",
    # initial_sidebar_state="expanded",
    initial_sidebar_state="collapsed",
)

# with st.spinner("Redirecting to the main page in 3 seconds..."):
#     time.sleep(1)
#     st.switch_page("pages/1_Effective_Damage_Calculator.py")


st.title("Apex Legends Data Analysis Dashboard")
row_1_cols = st.columns(3)

page_url_list = ["pages/1_Effective_Damage_Over_Time.py",
                 "pages/2_Effective_Damage_Over_Accuracy.py",
                 "pages/3_Weapons_Grid_Rank.py",
                 "pages/4_ALGS_Ranker.py",
                 "pages/5_Game_Input_Discrepancy.py"
                 ]


with row_1_cols[0]:
    st.image("resources/plots/damage_over_time.png", use_column_width=True)
    damage_over_time_button = st.button("Effective Damage Over Time", use_container_width=True, type="primary")
    if damage_over_time_button:
        st.switch_page(page_url_list[0])
    # st.page_link(page_url_list[0], use_container_width=True)
    st.write("Visualizes the effective damage dealt given *accuracy* over time")

with row_1_cols[1]:
    st.image("resources/plots/damage_over_accuracy.png", use_column_width=True)
    damage_over_accuracy_button = st.button("Effective Damage Over Accuracy", use_container_width=True, type="primary")
    if damage_over_accuracy_button:
        st.switch_page(page_url_list[1])
    st.write("Visualizes the effective damage dealt given *time* over accuracy")

with row_1_cols[2]:
    st.image("resources/plots/weapons_grid_rank.png", use_column_width=True)
    weapon_ranker_button = st.button("Weapons Grid Rank", use_container_width=True, type="primary")
    if weapon_ranker_button:
        st.switch_page(page_url_list[2])
    st.write("Compare the rank of weapons based on damage dealt over time and accuracy")

