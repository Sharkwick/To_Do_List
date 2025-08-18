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

firebase_key = os.getenv("FIREBASE_KEY_JSON")
if not firebase_key:
    st.error("Firebase credentials not found. Set FIREBASE_KEY_JSON.")
    st.stop()

cred_dict = json.loads(firebase_key)
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

def hash_password(password: str) -> str:
    """Return SHA256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_doc(nickname: str):
    """Fetch user document or return None."""
    doc = db.collection("users").document(nickname).get()
    return doc if doc.exists else None

def add_new_task(task: str, group: str, comment: str, tasks_ref):
    """Write a new task document."""
    task_id = f"{task}_{int(datetime.utcnow().timestamp())}"
    tasks_ref.document(task_id).set({
        "task": task,
        "group": group,
        "comment": comment,
        "timestamp": datetime.utcnow(),
        "completed": False
    })
    st.toast(f"Added '{task}' to '{group}'.")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nickname = ""

if not st.session_state.authenticated:
    st.title("🔐 Wickz Day Planner — Login or Register")
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        nick_in = st.text_input("Nickname", key="login_nick")
        pwd_in = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            user_doc = get_user_doc(nick_in)
            if user_doc and user_doc.to_dict().get("password_hash") == hash_password(pwd_in):
                st.session_state.authenticated = True
                st.session_state.nickname = nick_in
                st.success(f"Welcome back, {nick_in}!")
                st.rerun()
            else:
                st.error("Invalid nickname or password.")

    with register_tab:
        nick_new = st.text_input("Choose a Nickname", key="reg_nick")
        pwd_new = st.text_input("Choose a Password", type="password", key="reg_pwd")
        if st.button("Create Account"):
            if not get_user_doc(nick_new):
                db.collection("users").document(nick_new).set({
                    "password_hash": hash_password(pwd_new),
                    "created_at": datetime.utcnow()
                })
                # Initialize empty task collection
                db.collection("tasks").document(nick_new).set({"init": True})
                st.session_state.authenticated = True
                st.session_state.nickname = nick_new
                st.success(f"Account created. Welcome, {nick_new}!")
                st.rerun()
            else:
                st.error("Nickname already taken.")
    st.stop()

st.set_page_config(page_title="Wickz Day Planner", layout="wide")
st.markdown("<h1 style='text-align:center;'>📝 Wickz Day Planner</h1>", unsafe_allow_html=True)

nickname = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

# Sidebar
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
    st.markdown("## 📊 Task Summary")

    # Build summary dataframe
    docs = list(tasks_ref.stream())
    stats = {}
    for doc in docs:
        d = doc.to_dict()
        grp = d.get("group", "General")
        stats.setdefault(grp, {"total": 0, "completed": 0})
        stats[grp]["total"] += 1
        if d.get("completed"):
            stats[grp]["completed"] += 1

    if stats:
        summary_df = pd.DataFrame([
            {"Group": g, "Total": v["total"], "Completed": v["completed"]}
            for g, v in stats.items()
        ])
        melt = summary_df.melt(id_vars="Group", var_name="Status", value_name="Count")
        fig, ax = plt.subplots(figsize=(4, 3))
        sns.barplot(data=melt, x="Group", y="Count", hue="Status", ax=ax, palette="magma")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        st.pyplot(fig)
    else:
        st.info("No tasks yet.")

# Add Task
st.markdown("## ➕ Add New Task")
col_task, col_group = st.columns(2)
task_text = col_task.text_input("Task description", key="new_task")
group_sel = col_group.selectbox("Select group", ["Work", "Personal", "General", "Other"])
group_custom = col_group.text_input("Or custom group", key="custom_group")
comment = st.text_area("Optional comment", key="new_comment")

if st.button("Add Task"):
    grp_final = group_custom.strip() or group_sel
    if task_text.strip():
        add_new_task(task_text.strip(), grp_final, comment.strip(), tasks_ref)
    else:
        st.error("Task description cannot be empty.")

# Display Tasks
st.markdown("## 📋 All Tasks")
all_docs = list(tasks_ref.stream())
if not all_docs:
    st.info("No tasks to display.")
else:
    grouped = {}
    for doc in all_docs:
        d = doc.to_dict()
        grp = d.get("group", "General")
        grouped.setdefault(grp, []).append((doc.id, d))

    for grp, items in grouped.items():
        with st.expander(f"📂 {grp}", expanded=True):
            for doc_id, data in items:
                cols = st.columns([0.7, 0.1, 0.1, 0.1])
                done = cols[0].checkbox(
                    data["task"],
                    value=data.get("completed", False),
                    key=f"chk_{doc_id}"
                )
                if done != data.get("completed", False):
                    tasks_ref.document(doc_id).update({
                        "completed": done,
                        "completed_time": datetime.utcnow() if done else firestore.DELETE_FIELD
                    })
                    st.rerun()

                if cols[1].button("✏️", key=f"edit_{doc_id}"):
                    st.session_state[f"edit_mode_{doc_id}"] = True

                if cols[2].button("🗑️", key=f"del_{doc_id}"):
                    tasks_ref.document(doc_id).delete()
                    st.toast(f"Deleted '{data['task']}'.")
                    st.rerun()

                # Edit comment
                if st.session_state.get(f"edit_mode_{doc_id}", False):
                    new_c = st.text_input(
                        "Edit comment",
                        value=data.get("comment", ""),
                        key=f"comm_{doc_id}"
                    )
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        tasks_ref.document(doc_id).update({"comment": new_c})
                        st.toast("Comment updated.")
                        st.session_state[f"edit_mode_{doc_id}"] = False

                comment_text = data.get("comment", "")
                if comment_text and not st.session_state.get(f"edit_mode_{doc_id}", False):
                    st.caption(f"💬 {comment_text}")

# Completed Tasks Section
st.markdown("## ✅ Completed Tasks")

completed_docs = list(tasks_ref.where("completed", "==", True).stream())

if not completed_docs:
    st.info("No completed tasks yet.")
else:
    # group by category (optional)
    completed_grouped = {}
    for doc in completed_docs:
        d = doc.to_dict()
        grp = d.get("group", "General")
        completed_grouped.setdefault(grp, []).append(d)

    for grp, items in completed_grouped.items():
        with st.expander(f"{grp} ({len(items)})", expanded=False):
            for data in items:
                created_at   = data.get("timestamp")
                completed_at = data.get("completed_time")

                # now datetime is the class, so check against it
                if isinstance(created_at, datetime) and isinstance(completed_at, datetime):
                    date_str     = completed_at.strftime("%Y-%m-%d")
                    time_str     = completed_at.strftime("%H:%M:%S")
                    duration     = completed_at - created_at
                    duration_str = str(duration).split(".")[0]  # HH:MM:SS

                    st.write(
                        f"{data['task']} completed on {date_str} at {time_str}. "
                        f"Overall task duration {duration_str}"
                    )
                else:
                    st.write(f"{data['task']} completed (timestamp unavailable).")
