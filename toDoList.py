import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import requests
import hashlib
import os
import json

# --- Firebase Setup via Environment Variable ---
firebase_json = os.getenv("FIREBASE_KEY_JSON")
if not firebase_json:
    st.error("❌ Firebase credentials not found. Please set FIREBASE_KEY_JSON in your environment.")
    st.stop()

cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Get User IP and Hash It ---
def get_user_ip():
    try:
        ip = requests.get("https://api64.ipify.org?format=json").json()["ip"]
        return hashlib.sha256(ip.encode()).hexdigest()
    except:
        return "unknown_user"

user_id = get_user_ip()
tasks_ref = db.collection("tasks").document(user_id).collection("items")

st.markdown("###### user_id is used to store data")

# --- UI Layout ---
st.set_page_config(page_title="Wickz To-Do App", layout="wide")

# Delete All Tasks button (top-left)
st.markdown("<div style='text-align: left;'>", unsafe_allow_html=True)
if st.button("🗑️ Delete All Tasks"):
    all_tasks = tasks_ref.stream()
    for doc in all_tasks:
        tasks_ref.document(doc.id).delete()
    st.toast("🧹 All tasks deleted!", icon="🗑️")
st.markdown("</div>", unsafe_allow_html=True)

# Centered Title
st.markdown("<h1 style='text-align: center;'>📝Wickz Day Planner App</h1>", unsafe_allow_html=True)

# --- Task Input ---
task_input = st.text_input("Add a new task", key="task_input")
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

            # Unique keys
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
    with st.expander(f"📂 {group}", expanded=False):
        for data in items:
            task = data["task"]
            start = data["timestamp"]
            end = data.get("completed_time", datetime.now())
            duration = end - start
            minutes, seconds = divmod(int(duration.total_seconds()), 60)
            completed_str = end.strftime("%d/%m/%y %H:%M:%S")
            comment = data.get("comment", "")
            st.write(f"✔️ {task} — completed on {completed_str} in {minutes}m {seconds}s")
            if comment:
                st.caption(f"💬 {comment}")
