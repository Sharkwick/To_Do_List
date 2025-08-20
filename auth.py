import streamlit as st
from datetime import datetime
from utils import hash_password

def login(db):
    with st.form("login_form", clear_on_submit=False):
        nick_in = st.text_input("Nickname", key="login_nick")
        pwd_in  = st.text_input("Password", type="password", key="login_pwd")
        if st.form_submit_button("Login"):
            user = db.collection("users").document(nick_in).get()
            if user.exists and user.to_dict().get("password_hash") == hash_password(pwd_in):
                st.session_state.authenticated = True
                st.session_state.nickname = nick_in
                st.success(f"Welcome back, {nick_in}!")
                st.rerun()
            else:
                st.error("❌ Invalid nickname or password.")

def register(db):
    with st.form("register_form", clear_on_submit=False):
        nick_new = st.text_input("Choose a Nickname", key="reg_nick")
        pwd_new  = st.text_input("Choose a Password", type="password", key="reg_pwd")
        if st.form_submit_button("Create Account"):
            if nick_new and pwd_new and not db.collection("users").document(nick_new).get().exists:
                db.collection("users").document(nick_new).set({
                    "password_hash": hash_password(pwd_new),
                    "created_at": datetime.utcnow()
                })
                db.collection("tasks").document(nick_new).set({"init": True})
                st.session_state.authenticated = True
                st.session_state.nickname = nick_new
                st.success(f"🎉 Account created. Welcome, {nick_new}!")
                st.rerun()
            else:
                st.error("❌ Nickname taken or invalid inputs.")