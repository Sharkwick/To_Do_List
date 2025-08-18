import os
import json
import hashlib
from datetime import datetime

import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

import firebase_admin
from firebase_admin import credentials, firestore

# ------------------------------
# Firebase Initialization
# ------------------------------
def load_firebase_credentials():
    try:
        # local JSON file (secrets/serviceAccountKey.json)
        return credentials.Certificate("secrets/serviceAccountKey.json")
    except FileNotFoundError:
        # fallback to env var
        firebase_key = os.getenv("FIREBASE_KEY_JSON")
        if not firebase_key:
            raise ValueError("Firebase credentials not found.")
        key_dict = json.loads(firebase_key)
        return credentials.Certificate(key_dict)

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

def toggle_edit(doc_id):
    st.session_state[f"edit_{doc_id}"] = True

def render_task(doc_id, data, tasks_ref):
    edit_key = f"edit_{doc_id}"
    # ensure default
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
        label="✏️",
        key=f"edit_btn_{doc_id}",
        on_click=toggle_edit,
        args=(doc_id,)
    )
    cols[2].button(
        label="🗑️",
        key=f"del_btn_{doc_id}",
        on_click=delete_task,
        args=(doc_id, data["task"], tasks_ref)
    )

    # edit comment mode
    if st.session_state.get(edit_key):
        new_c = st.text_input(
            "Edit comment",
            value=data.get("comment", ""),
            key=f"comm_{doc_id}"
        )
        if st.button("💾 Save", key=f"save_{doc_id}"):
            tasks_ref.document(doc_id).update({"comment": new_c})
            st.toast("💬 Comment updated.")
            st.session_state[edit_key] = False
            st.rerun()

    # display comment when not editing
    elif data.get("comment", ""):
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
    st.set_page_config(page_title="Wickz Day Planner", layout="centered")
    st.title("📝 Wickz Day Planner")
    st.markdown("#### Free forever, as long as Streamlit keeps us online 😉")
    st.markdown("## 🔐 Login or Register")

    login_tab, reg_tab = st.tabs(["Login", "Register"])
    with login_tab:
        ln = st.text_input("Nickname", key="login_nick")
        lp = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            user = get_user_doc(ln)
            if user and user.to_dict().get("password_hash") == hash_password(lp):
                st.session_state.authenticated = True
                st.session_state.nickname = ln
                st.success(f"Welcome back, {ln}!")
                st.rerun()
            else:
                st.error("❌ Invalid nickname or password.")

    with reg_tab:
        rn = st.text_input("Choose a Nickname", key="reg_nick")
        rp = st.text_input("Choose a Password", type="password", key="reg_pwd")
        if st.button("Create Account"):
            if rn and rp and not get_user_doc(rn):
                db.collection("users").document(rn).set({
                    "password_hash": hash_password(rp),
                    "created_at": datetime.utcnow()
                })
                # create placeholder doc for tasks
                db.collection("tasks").document(rn).set({"init": True})
                st.session_state.authenticated = True
                st.session_state.nickname = rn
                st.success(f"🎉 Account created. Welcome, {rn}!")
                st.rerun()
            else:
                st.error("❌ Nickname taken or invalid inputs.")
    st.stop()

# ------------------------------
# Main App Interface
# ------------------------------
st.set_page_config(page_title="Wickz Day Planner", layout="wide")
nickname = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

st.markdown("<h1 style='text-align:center;'>📝 Wickz Day Planner</h1>", unsafe_allow_html=True)

# Sidebar: user, refresh, logout, pie chart
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

    all_docs = list(tasks_ref.stream())
    stats = {}
    for d in all_docs:
        info = d.to_dict()
        grp = info.get("group", "General")
        done = info.get("completed", False)
        stats.setdefault(grp, {"total": 0, "completed": 0})
        stats[grp]["total"] += 1
        stats[grp]["completed"] += int(done)

    if stats:
        sel = st.selectbox("Select group", list(stats.keys()), key="pie_group")
        t = stats[sel]["total"]
        c = stats[sel]["completed"]
        rem = t - c

        fig, ax = plt.subplots(figsize=(4, 4), facecolor="white")
        ax.pie([c, rem],
               labels=["Completed", "Remaining"],
               autopct="%1.0f%%",
               startangle=90,
               colors=sns.color_palette("muted", 2),
               wedgeprops={"edgecolor": "white", "linewidth": 1.5})
        ax.set_title(f"{sel} Tasks", pad=12)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No tasks to summarize.")

# Add New Task
st.markdown("## ➕ Add New Task")
c1, c2 = st.columns(2)
t_txt = c1.text_input("Task description", key="new_task")
g_sel = c2.selectbox("Choose group", ["Work", "Personal", "General"], key="group_sel")
g_cus = c2.text_input("Or custom group", key="group_custom")
com = st.text_area("Optional comment", key="new_comment")

if st.button("Add Task"):
    g_final = g_cus.strip() or g_sel
    if t_txt.strip():
        add_new_task(t_txt.strip(), g_final, com.strip(), tasks_ref)
    else:
        st.error("❌ Task description cannot be empty.")

# Display All Tasks
st.markdown("## 📋 All Tasks")
docs = list(tasks_ref.stream())
if not docs:
    st.info("No tasks yet.")
else:
    grouped = {}
    for d in docs:
        info = d.to_dict()
        grp = info.get("group", "General")
        grouped.setdefault(grp, []).append((d.id, info))

    for grp, items in grouped.items():
        with st.expander(f"📂 {grp}", expanded=True):
            for doc_id, info in items:
                render_task(doc_id, info, tasks_ref)

# Completed Tasks with Timestamps & Duration
st.markdown("## ✅ Completed Tasks")
done_docs = list(tasks_ref.where("completed", "==", True).stream())
if not done_docs:
    st.info("No completed tasks yet.")
else:
    comp_grp = {}
    for d in done_docs:
        info = d.to_dict()
        grp = info.get("group", "General")
        comp_grp.setdefault(grp, []).append(info)

    for grp, items in comp_grp.items():
        with st.expander(f"{grp} ({len(items)})", expanded=False):
            for info in items:
                ts = info.get("timestamp")
                ct = info.get("completed_time")
                if isinstance(ts, datetime) and isinstance(ct, datetime):
                    date = ct.strftime("%Y-%m-%d")
                    time = ct.strftime("%H:%M:%S")
                    dur = str(ct - ts).split(".")[0]
                    st.write(
                        f"{info['task']} — completed on {date} at {time}. Duration: {dur}"
                    )
                else:
                    st.write(f"{info['task']} — completed (timestamp unavailable).")