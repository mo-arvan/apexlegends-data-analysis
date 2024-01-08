import streamlit as st
import pandas as pd
from src import ttk_analyzer
# https://apexlegends-data-analysis.streamlit.app/
def main():



    st.title('Apex Legends Data Analysis')
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
    # This leaves players to decide which weapon is the best based on "the feel" of the weapon.
    # This works fine for the most part, except it is not based on concrete data.
    # My current findings match the Pro Players' opinions, R99 is the best weapon in the game.
    #
    # But, let's try to figure out why.
    # """
    # # tab1.write(intro)
    # tab1.markdown(intro)  # see #*
    # tab2.write("this is tab 2")

    close_gun_df = pd.read_csv("data/guns_close_range.csv")

    ttk_analyzer.plot_ttk_over_accuracy(close_gun_df)
    ttk_analyzer.plot_damage_over_peak_time(close_gun_df)



if __name__ == "__main__":
    main()
