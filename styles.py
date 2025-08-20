import streamlit as st

def load_custom_styles():
    return """
    <style>
        .stTabs [data-baseweb="tab"] {
            background-color: #000000;
            border-radius: 0px 10px 0px 0px;
            padding: 15px;
            font-weight: bold;
        }
        .stTabs [aria-selected="true"] {
            background-color: #FF7575;
            color: #ffffff;
        }
    </style>
    """
