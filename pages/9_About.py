import logging

import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="About",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)

fights_breakdown_info = ""

docs_file_path_list = [
    # "README.md",
    "docs/why.md",
    "docs/fights_breakdown.md",
    "docs/limitations.md",
    "docs/credits.md",
    "docs/related_work.md",
]

docs_list = []

for doc_path in docs_file_path_list:
    with open(doc_path, "r") as f:
        docs_list.append(f.read())

for doc in docs_list:
    st.markdown(doc, unsafe_allow_html=True)
