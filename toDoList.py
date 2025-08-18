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

# ------------------------------
# Page config (first call)
# ------------------------------
st.set_page_config(
    page_title="Wickz Day Planner",
    layout="wide",
    initial_sidebar_state="auto"
)

# ------------------------------
# Firebase Initialization
# ------------------------------
def load_firebase_credentials():
    try:
        return credentials.Certificate("secrets/serviceAccountKey.json")
    except FileNotFoundError:
        raw = os.getenv("FIREBASE_KEY_JSON")
        if not raw:
            raise ValueError("Firebase credentials not found.")
        return credentials.Certificate(json.loads(raw))

def initialize_firebase():
    if not firebase_admin._apps:
        cred = load_firebase_credentials()
        firebase_admin.initialize_app(cred)

initialize_firebase()
db = firestore.client()

# ------------------------------
# Utility Functions
# ------------------------------
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def get_user_doc(nick: str):
    doc = db.collection("users").document(nick).get()
    return doc if doc.exists else None

def add_new_task(text: str, group: str, comment: str, tasks_ref):
    task_id = str(int(datetime.utcnow().timestamp() * 1000))
    tasks_ref.document(task_id).set({
        "task": text,
        "group": group,
        "comment": comment,
        "timestamp": datetime.utcnow(),
        "completed": False
    })
    st.toast(f"✅ Added '{text}' to '{group}'.")

def delete_task(doc_id, task_text, tasks_ref):
    tasks_ref.document(doc_id).delete()
    st.toast(f"🗑️ Deleted '{task_text}'.")
    st.rerun()

def delete_group(group_name, tasks_ref):
    docs = tasks_ref.where("group", "==", group_name).stream()
    for d in docs:
        d.reference.delete()
    st.toast(f"🗑️ Deleted all tasks in group '{group_name}'.")
    st.rerun()

def delete_all_tasks(tasks_ref):
    for d in tasks_ref.stream():
        d.reference.delete()
    st.toast("🗑️ Deleted all tasks.")
    st.rerun()

def toggle_edit(doc_id):
    st.session_state[f"edit_{doc_id}"] = not st.session_state.get(f"edit_{doc_id}", False)

def render_task(doc_id, data, tasks_ref):
    edit_key = f"edit_{doc_id}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    cols = st.columns([0.7, 0.1, 0.1, 0.1])
    done = cols[0].checkbox(
        label=data["task"],
        value=data.get("completed", False),
        key=f"chk_{doc_id}"
    )
    if done != data.get("completed", False):
        tasks_ref.document(doc_id).update({
            "completed": done,
            "completed_time": datetime.utcnow() if done else firestore.DELETE_FIELD
        })
        st.rerun()

    cols[1].button(
        "✏️",
        key=f"edit_btn_{doc_id}",
        on_click=toggle_edit,
        args=(doc_id,)
    )
    cols[2].button(
        "🗑️",
        key=f"del_btn_{doc_id}",
        on_click=delete_task,
        args=(doc_id, data["task"], tasks_ref)
    )

    if st.session_state[edit_key]:
        new_comment = st.text_input(
            "Edit comment",
            value=data.get("comment", ""),
            key=f"comm_{doc_id}"
        )
        if st.button("💾 Save", key=f"save_{doc_id}"):
            tasks_ref.document(doc_id).update({"comment": new_comment})
            st.toast("💬 Comment updated.")
            st.session_state[edit_key] = False
    elif data.get("comment"):
        st.caption(f"💬 {data['comment']}")

# ------------------------------
# Session State Defaults
# ------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nickname = ""

# ------------------------------
# Authentication Flow
# ------------------------------
if not st.session_state.authenticated:
    st.title("📝 Wickz Day Planner")
    st.markdown("## Free forever, as long as Streamlit keeps us online 😉")
    st.markdown("## 🔐 Login or Register")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            nick_in = st.text_input("Nickname", key="login_nick")
            pwd_in  = st.text_input("Password", type="password", key="login_pwd")
            if st.form_submit_button("Login"):
                user = get_user_doc(nick_in)
                if user and user.to_dict().get("password_hash") == hash_password(pwd_in):
                    st.session_state.authenticated = True
                    st.session_state.nickname = nick_in
                    st.success(f"Welcome back, {nick_in}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid nickname or password.")

    with register_tab:
        with st.form("register_form", clear_on_submit=False):
            nick_new = st.text_input("Choose a Nickname", key="reg_nick")
            pwd_new  = st.text_input("Choose a Password", type="password", key="reg_pwd")
            if st.form_submit_button("Create Account"):
                if nick_new and pwd_new and not get_user_doc(nick_new):
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

    st.stop()

# ------------------------------
# Main App Interface
# ------------------------------
nickname  = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

st.markdown("<h1 style='text-align:center;'>📝 Wickz Day Planner</h1>", unsafe_allow_html=True)

# ------------------------------
# Sidebar: Overview + Pie Chart (with "All" option)
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

    docs = list(tasks_ref.stream())
    group_stats = {}
    for d in docs:
        info = d.to_dict()
        grp  = info.get("group", "General")
        done = info.get("completed", False)
        group_stats.setdefault(grp, {"total": 0, "completed": 0})
        group_stats[grp]["total"]     += 1
        group_stats[grp]["completed"] += int(done)

    # add "All"
    options = ["All"] + list(group_stats.keys())
    sel = st.selectbox("Select group to view", options, key="pie_group")

    if sel == "All":
        total = sum(v["total"] for v in group_stats.values())
        comp  = sum(v["completed"] for v in group_stats.values())
    else:
        total = group_stats[sel]["total"]
        comp  = group_stats[sel]["completed"]

    rem = total - comp

    if total > 0:
        fig, ax = plt.subplots(figsize=(4,4), facecolor="white")
        ax.pie(
            [comp, rem],
            labels=["Completed","Remaining"],
            autopct="%1.0f%%",
            startangle=90,
            colors=sns.color_palette("muted", 2),
            wedgeprops={"edgecolor":"white","linewidth":1.5}
        )
        ax.set_title(f"{sel} Tasks", pad=12)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No tasks to summarize.")

# ------------------------------
# Add New Task
# ------------------------------
st.markdown("## ➕ Add New Task")
c1, c2 = st.columns(2)
task_txt   = c1.text_input("Task description", key="new_task")
group_sel  = c2.selectbox("Choose group", ["Work","Personal","General"], key="group_sel")
group_cust = c2.text_input("Or custom group", key="group_custom")
comment    = st.text_area("Optional comment", key="new_comment")

if st.button("Add Task"):
    final_grp = group_cust.strip() or group_sel
    if task_txt.strip():
        add_new_task(task_txt.strip(), final_grp, comment.strip(), tasks_ref)
    else:
        st.error("❌ Task description cannot be empty.")

# ------------------------------
# All Tasks (with delete group/all buttons)
# ------------------------------
st.markdown("## 📋 All Tasks")

# Delete all tasks
if st.button("🗑️ Delete All Tasks"):
    delete_all_tasks(tasks_ref)

docs = list(tasks_ref.stream())
if not docs:
    st.info("No tasks yet.")
else:
    grouped = {}
    for d in docs:
        info = d.to_dict()
        grp  = info.get("group","General")
        grouped.setdefault(grp, []).append((d.id, info))

    for grp, items in grouped.items():
        with st.expander(f"📂 {grp} ({len(items)})", expanded=True):
            # delete this group
            if st.button(f"🗑️ Delete Group '{grp}'", key=f"del_group_{grp}"):
                delete_group(grp, tasks_ref)

            for doc_id, info in items:
                render_task(doc_id, info, tasks_ref)

# ------------------------------
# Completed Tasks as Collapsible Tables
# ------------------------------
st.markdown("## ✅ Completed Tasks")

completed_docs = list(tasks_ref.where("completed", "==", True).stream())
if not completed_docs:
    st.info("No completed tasks yet.")
else:
    comp_by_group = {}
    for d in completed_docs:
        info = d.to_dict()
        grp = info.get("group", "General")
        ts = info.get("timestamp")
        ct = info.get("completed_time")
        if isinstance(ts, datetime) and isinstance(ct, datetime):
            added_date   = ts.strftime("%Y-%m-%d %H:%M:%S")
            completed_date = ct.strftime("%Y-%m-%d %H:%M:%S")
            duration     = str(ct - ts).split(".")[0]
        else:
            added_date = completed_date = duration = "N/A"

        comp_by_group.setdefault(grp, []).append({
            "Task Name": info.get("task",""),
            "Comment": info.get("comment",""),
            "Added Date": added_date,
            "Completed Date": completed_date,
            "Duration": duration
        })

    for grp, rows in comp_by_group.items():
        with st.expander(f"{grp} ({len(rows)})", expanded=False):
            df = pd.DataFrame(rows)
            st.table(df)