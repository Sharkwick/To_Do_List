import streamlit as st
from firebase_utils import initialize_firebase
from auth import login, register
from tasks import render_pending, render_completed, add_new_task, delete_all_completed
from ui import setup_page, sidebar
from styles import load_custom_styles

setup_page()
db = initialize_firebase()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nickname = ""

if not st.session_state.authenticated:
    st.title("Wickz Day Planner")
    st.markdown("---")
    st.markdown("## Free forever, as long as Streamlit keeps us online 😉")
    st.markdown("## 🔐 Login or Register")

    login_tab, register_tab = st.tabs(["Login", "Click Here to Register"])
    with login_tab: login(db)
    with register_tab: register(db)
    st.stop()

nickname  = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")

pending_count, completed_count = sidebar(nickname, tasks_ref, db)

# ------------------------------ Add Task
st.title("Wickz Day Planner")
st.markdown("---")
st.markdown("## 🔰 Create a New Task")
all_docs = list(tasks_ref.stream())
existing_groups = sorted({d.to_dict().get("group", "General") for d in all_docs if d.exists})
if "General" not in existing_groups: existing_groups.append("General")
existing_groups = sorted(existing_groups)

with st.form("add_task_form", clear_on_submit=True):
    task_txt = st.text_input("Task Name")
    c1, c2 = st.columns(2)
    group_cust = c1.text_input("Create New Group")
    group_sel  = c2.selectbox("Or select an existing group", options=existing_groups, index=0)
    comment    = st.text_area("Task Description")
    submitted  = st.form_submit_button("Add Task")
    if submitted:
        final_grp = group_cust.strip() or group_sel
        if task_txt.strip():
            add_new_task(task_txt.strip(), final_grp, comment.strip(), tasks_ref)
            st.success(f"✅ Task added: {task_txt}, Group={final_grp}")
            st.rerun()
        else:
            st.error("❌ Task Name cannot be empty.")

# ------------------------------ Toggle Tasks
st.markdown("---")
st.markdown("## 🔎 View Created Tasks")
st.markdown(load_custom_styles(), unsafe_allow_html=True)

pending_tab, completed_tab = st.tabs(["Pending Tasks", "Completed Tasks"])
with pending_tab: render_pending(tasks_ref, db)
with completed_tab: render_completed(tasks_ref,db)
st.stop()

#if view_completed:
    #render_completed(tasks_ref)
#else:
    #render_pending(tasks_ref, db)
