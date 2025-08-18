import os
import json
import hashlib
from datetime import datetime

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import firebase_admin
from firebase_admin import credentials, firestore
from PIL import Image

# ------------------------------
#  Firebase Initialization
# ------------------------------
firebase_key = os.getenv("FIREBASE_KEY_JSON")
if not firebase_key:
    st.error("❌ Firebase credentials not found. Set FIREBASE_KEY_JSON.")
    st.stop()

cred_dict = json.loads(firebase_key)
cred = credentials.Certificate(cred_dict)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------------------
#  Utility Functions
# ------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_doc(nick: str):
    doc = db.collection("users").document(nick).get()
    return doc if doc.exists else None

def add_new_task(text: str, group: str, comment: str, tasks_ref):
    task_id = f"{int(datetime.utcnow().timestamp() * 1000)}"
    tasks_ref.document(task_id).set({
        "task": text,
        "group": group,
        "comment": comment,
        "timestamp": datetime.utcnow(),
        "completed": False
    })
    st.toast(f"✅ Added '{text}' to '{group}'.")

# ------------------------------
#  Session State Defaults
# ------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nickname = ""

# ------------------------------
#  Authentication Flow
# ------------------------------
if not st.session_state.authenticated:
    st.image(
    "https://ibb.co/8DZ2PvJW",
    width=300,
    height=300 # fixed width in pixels
    )
    st.title("Wickz Day Planner")
    st.markdown("### For All Your Planning Needs. It's Free Forever As Long as Stremlit Keeps the app online 😉")
    st.markdown("## 🔐 Login or Register")
    login_tab, register_tab = st.tabs(["Login", "Register"])
    with login_tab:
        nick_in   = st.text_input("Nickname", key="login_nick")
        pwd_in    = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            user_doc = get_user_doc(nick_in)
            if user_doc and user_doc.to_dict().get("password_hash") == hash_password(pwd_in):
                st.session_state.authenticated = True
                st.session_state.nickname     = nick_in
                st.success(f"Welcome back, {nick_in}!")
                st.rerun()
            else:
                st.error("❌ Invalid nickname or password.")

    with register_tab:
        nick_new = st.text_input("Choose a Nickname", key="reg_nick")
        pwd_new  = st.text_input("Choose a Password", type="password", key="reg_pwd")
        if st.button("Create Account"):
            if not get_user_doc(nick_new) and nick_new and pwd_new:
                db.collection("users").document(nick_new).set({
                    "password_hash": hash_password(pwd_new),
                    "created_at": datetime.utcnow()
                })
                db.collection("tasks").document(nick_new).set({"init": True})
                st.session_state.authenticated = True
                st.session_state.nickname     = nick_new
                st.success(f"🎉 Account created. Welcome, {nick_new}!")
                st.rerun()
            else:
                st.error("❌ Nickname taken or invalid inputs.")
    st.stop()

# ------------------------------
#   Main App Interface
# ------------------------------
st.set_page_config(page_title="Wickz Day Planner", layout="wide")
st.markdown("<h1 style='text-align:center;'>📝 Wickz Day Planner</h1>", unsafe_allow_html=True)
nickname  = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

# ------------------------------
#   Sidebar with Pie Chart
# ------------------------------
with st.sidebar:
    st.markdown("## 👤 User")
    st.write(f"`{nickname}`")
    st.markdown("---")

    if st.button("🔁 Refresh"):
        st.rerun()
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📊 Tasks Overview")

    # Build group_stats
    docs = list(tasks_ref.stream())
    group_stats = {}
    for doc in docs:
        data  = doc.to_dict()
        grp   = data.get("group", "General")
        done  = data.get("completed", False)
        group_stats.setdefault(grp, {"total": 0, "completed": 0})
        group_stats[grp]["total"]     += 1
        group_stats[grp]["completed"] += 1 if done else 0

    if group_stats:
        selected_group = st.selectbox("Select group to view", list(group_stats.keys()), key="pie_group")
        stats    = group_stats[selected_group]
        completed = stats["completed"]
        remaining = stats["total"] - completed

        labels = ["Completed", "Remaining"]
        values = [completed, remaining]
        colors = sns.color_palette("muted", 2)

        fig, ax = plt.subplots(figsize=(4, 4), facecolor="white")
        ax.pie(
            values,
            labels=labels,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5}
        )
        ax.set_title(f"{selected_group} Tasks", fontsize=12, pad=12)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No tasks to summarize.")

# ------------------------------
#   Add New Task
# ------------------------------
st.markdown("## ➕ Add New Task")
col1, col2 = st.columns(2)
task_text   = col1.text_input("Task description", key="new_task")
group_sel   = col2.selectbox("Choose group", ["Work", "Personal", "General"], key="group_sel")
group_custom= col2.text_input("Or custom group", key="group_custom")
comment     = st.text_area("Optional comment", key="new_comment")

if st.button("Add Task"):
    grp_final = group_custom.strip() or group_sel
    if task_text.strip():
        add_new_task(task_text.strip(), grp_final, comment.strip(), tasks_ref)
    else:
        st.error("❌ Task description cannot be empty.")

# ------------------------------
#   Display All Tasks
# ------------------------------
st.markdown("## 📋 All Tasks")
all_docs = list(tasks_ref.stream())
if not all_docs:
    st.info("No tasks yet.")
else:
    grouped = {}
    for doc in all_docs:
        d   = doc.to_dict()
        grp = d.get("group", "General")
        grouped.setdefault(grp, []).append((doc.id, d))

    for grp, items in grouped.items():
        with st.expander(f"📂 {grp}", expanded=True):
            for doc_id, data in items:
                cols = st.columns([0.7, 0.1, 0.1, 0.1])
                done = cols[0].checkbox(data["task"], value=data.get("completed", False), key=f"chk_{doc_id}")
                if done != data.get("completed", False):
                    tasks_ref.document(doc_id).update({
                        "completed": done,
                        "completed_time": datetime.utcnow() if done else firestore.DELETE_FIELD
                    })
                    st.rerun()

                if cols[1].button("✏️", key=f"edit_{doc_id}"):
                    st.session_state[f"edit_{doc_id}"] = True

                if cols[2].button("🗑️", key=f"del_{doc_id}"):
                    tasks_ref.document(doc_id).delete()
                    st.toast(f"🗑️ Deleted '{data['task']}'.")
                    st.rerun()

                # Edit comment mode
                if st.session_state.get(f"edit_{doc_id}", False):
                    new_c = st.text_input(
                        "Edit comment",
                        value=data.get("comment", ""),
                        key=f"comm_{doc_id}"
                    )
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        tasks_ref.document(doc_id).update({"comment": new_c})
                        st.toast("💬 Comment updated.")
                        st.session_state[f"edit_{doc_id}"] = False

                # Display existing comment
                if data.get("comment", "") and not st.session_state.get(f"edit_{doc_id}", False):
                    st.caption(f"💬 {data['comment']}")

# ------------------------------
#   Completed Tasks with Timestamps & Duration
# ------------------------------
st.markdown("## ✅ Completed Tasks")
completed_docs = list(tasks_ref.where("completed", "==", True).stream())

if not completed_docs:
    st.info("No completed tasks yet.")
else:
    completed_grouped = {}
    for doc in completed_docs:
        d   = doc.to_dict()
        grp = d.get("group", "General")
        completed_grouped.setdefault(grp, []).append(d)

    for grp, items in completed_grouped.items():
        with st.expander(f"{grp} ({len(items)})", expanded=False):
            for data in items:
                created_at   = data.get("timestamp")
                completed_at = data.get("completed_time")
                if isinstance(created_at, datetime) and isinstance(completed_at, datetime):
                    date_str     = completed_at.strftime("%Y-%m-%d")
                    time_str     = completed_at.strftime("%H:%M:%S")
                    duration_str = str(completed_at - created_at).split(".")[0]
                    st.write(
                        f"{data['task']} completed on {date_str} at {time_str}. "
                        f"Overall task duration {duration_str}"
                    )
                else:
                    st.write(f"{data['task']} completed (timestamp unavailable).")
