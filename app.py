"""Streamlit entry point for ECG Learning Coach."""

import streamlit as st


st.set_page_config(page_title="ECG Learning Coach", page_icon="🫀", layout="centered")

st.title("ECG Learning Coach")
st.write(
    "Learn to interpret ECGs by improving your clinical reasoning—not by simply receiving the diagnosis."
)

level = st.selectbox(
    "Choose your learning level",
    ("Beginner", "Intermediate", "Advanced"),
)

if st.button("Start Case", type="primary"):
    st.info("Case engine coming next.")
