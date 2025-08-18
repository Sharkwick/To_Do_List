import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import hashlib
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# --- Firebase Setup ---
firebase_json = os.getenv("FIREBASE_KEY_JSON")
if not firebase_json:
    st.error("❌ Firebase credentials not found. Please set FIREBASE_KEY_JSON in your environment.")
    st.stop()

cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Page Config ---
st.set_page_config(page_title="Wickz To-Do App", layout="wide")
st.markdown("<h1 style='text-align: center;'>📝 Wickz Day Planner App</h1>", unsafe_allow_html=True)

# --- Auth Logic ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

if "nickname" not in st.session_state or "authenticated" not in st.session_state:
    st.session_state.nickname = ""
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    tab_login, tab_register = st.tabs(["🔐 Login", "🆕 Create Account"])

    with tab_login:
        nickname_login = st.text_input("Nickname", key="login_nickname")
        password_login = st.text_input("Password", type="password", key="login_password")
        if st.button("➡️ Login"):
            user_doc = db.collection("users").document(nickname_login).get()
            if user_doc.exists:
                stored_hash = user_doc.to_dict().get("password_hash")
                if stored_hash == hash_password(password_login):
                    st.session_state.nickname = nickname_login
                    st.session_state.authenticated = True
                    st.success(f"✅ Welcome back, {nickname_login}!")
                else:
                    st.error("❌ Incorrect password.")
            else:
                st.error("❌ Nickname not found.")

    with tab_register:
        nickname_new = st.text_input("New Nickname", key="register_nickname")
        password_new = st.text_input("New Password", type="password", key="register_password")
        if st.button("🆕 Create Account"):
            if nickname_new and password_new:
                user_ref = db.collection("users").document(nickname_new)
                if user_ref.get().exists:
                    st.error("❌ Nickname already exists.")
                else:
                    user_ref.set({
                        "password_hash": hash_password(password_new),
                        "created": datetime.now()
                    })
                    db.collection("tasks").document(nickname_new).set({"created": datetime.now()})
                    st.session_state.nickname = nickname_new
                    st.session_state.authenticated = True
                    st.success(f"🎉 Account created for {nickname_new}!")
            else:
                st.warning("Please enter both nickname and password.")
    st.stop()

# --- Sidebar Controls ---
st.sidebar.info(f"👤 Logged in as: {st.session_state.nickname}")
if st.sidebar.button("🔄 Refresh Page"):
    st.experimental_rerun()
if st.sidebar.button("🔒 Log Out"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.experimental_rerun()

# --- Task Reference ---
nickname = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

# --- Top Layout with Chart ---
col_left, col_right = st.columns([2, 1])

with col_right:
    task_docs = tasks_ref.stream()
    group_stats = {}
    for doc in task_docs:
        data = doc.to_dict()
        group = data.get("group", "General")
        completed = data.get("completed", False)
        if group not in group_stats:
            group_stats[group] = {"total": 0, "completed": 0}
        group_stats[group]["total"] += 1
        if completed:
            group_stats[group]["completed"] += 1

    df = pd.DataFrame([
        {"Group": group, "Total Tasks": stats["total"], "Completed Tasks": stats["completed"]}
        for group, stats in group_stats.items()
    ])
    if not df.empty:
        melted_df = df.melt(id_vars="Group", var_name="Task Type", value_name="Count")
        sns.set(style="whitegrid")
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(data=melted_df, x="Group", y="Count", hue="Task Type", ax=ax, palette="viridis")
        ax.set_title("📊 Task Summary by Group")
        ax.set_ylabel("Number of Tasks")
        ax.set_xlabel("Group")
        st.pyplot(fig)

with col_left:
    st.markdown("### ➕ Add a New Task")
    task_input = st.text_input("Task", key="task_input")
    existing_groups = ["Work", "Personal", "General"]
    selected_group = st.selectbox("Choose a group", options=existing_groups)
    custom_group = st.text_input("Or enter a custom group", key="task_group")
    comment_input = st.text_area("Add a comment (optional)", key="task_comment")

    def add_task():
        task = st.session_state["task_input"].strip()
        group = st.session_state["task_group"].strip() or selected_group
        comment = st.session_state["task_comment"].strip()
        if task:
            task_ref = tasks_ref.document(task)
            if not task_ref.get().exists:
                task_ref.set({
                    "task": task,
                    "group": group,
                    "comment": comment,
                    "timestamp": datetime.now(),
                    "completed": False
                })
                st.toast(f"✅ '{task}' added to '{group}' group!", icon="📝")
            else:
                st.error(f"'{task}' already exists!")
        st.session_state["task_input"] = ""
        st.session_state["task_group"] = ""
        st.session_state["task_comment"] = ""

    st.button("Submit Task", on_click=add_task)

# --- Display Tasks ---
st.markdown("<h3 style='text-align: center;'>📃 All Tasks</h3>", unsafe_allow_html=True)
tasks = tasks_ref.stream()
grouped_tasks = {}
for doc in tasks:
    data = doc.to_dict()
    group = data.get("group", "General")
    grouped_tasks.setdefault(group, []).append((doc.id, data))

for group, items in grouped_tasks.items():
    with st.expander(f"📂 {group}", expanded=True):
        for doc_id, data in items:
            task = data["task"]
            completed = data["completed"]
            timestamp = data["timestamp"]
            comment = data.get("comment", "")

            checkbox_key = f"checkbox_{doc_id}"
            delete_key = f"delete_{doc_id}"
            edit_key = f"edit_mode_{doc_id}"
            edit_button_key = f"edit_{doc_id}"
            comment_input_key = f"comment_{doc_id}"
            save_button_key = f"save_{doc_id}"

            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                checked = st.checkbox(task, value=completed, key=checkbox_key)
                if checked and not completed:
                    tasks_ref.document(doc_id).update({
                        "completed": True,
                        "completed_time": datetime.now()
                    })
                elif not checked and completed:
                    tasks_ref.document(doc_id).update({
                        "completed": False,
                        "completed_time": firestore.DELETE_FIELD
                    })
            with col2:
                if st.button("🗑️", key=delete_key):
                    tasks_ref.document(doc_id).delete()
                    st.toast(f"🗑️ '{task}' deleted from '{group}' group.")

            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            if not st.session_state[edit_key]:
                if st.button("✏️", key=edit_button_key):
                    st.session_state[edit_key] = True
            else:
                col_edit, col_save = st.columns([0.85, 0.15])
                with col_edit:
                    new_comment = st.text_input("Edit comment", value=comment, key=comment_input_key)
                with col_save:
                    if st.button("💾", key=save_button_key):
                        tasks_ref.document(doc_id).update({"comment": new_comment})
                        st.toast(f"💬 Comment updated for '{task}'")
                        st.session_state[edit_key] = False

            if comment and not st.session_state[edit_key]:
                st.caption(f"💬 {comment}")

# --- Completed Tasks ---
st.markdown("<h3 style='text-align: center;'>✅ Completed Tasks</h3>", unsafe_allow_html=True)
completed_tasks = tasks_ref.where("completed", "==", True).stream()
completed_grouped = {}
for doc in completed_tasks:
    data = doc.to_dict()
    group = data.get("group", "General")
    completed_grouped.setdefault(group, []).append(data)

for group, items in completed_grouped.items():
    with st.expander(f"📂 {group}", expanded=False)
