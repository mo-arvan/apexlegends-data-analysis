import streamlit as st

fights_breakdown_info = ""

docs_file_path_list = [
    "README.md",
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
