import streamlit as st
import time
st.set_page_config(
    page_title="Apex Legends Data Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.spinner("Redirecting to the eDPS Calculator in 3 seconds..."):
    time.sleep(3)

    st.switch_page("pages/1_Effective_Damage_Calculator.py")
