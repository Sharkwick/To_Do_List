#Steamlit To Do List App
from datetime import datetime

import streamlit as st
checked_items = {}
st.title("To Do List")

if "task_list" not in st.session_state:
    st.session_state["task_list"] = []

New_Task = st.text_input("Add a new task")

if New_Task:
    if New_Task not in st.session_state["task_list"]:
        st.session_state["task_list"].append(New_Task)
        st.session_state[f"{New_Task}_checked"] = False
        st.session_state[f"{New_Task}_timestamp"] = datetime.now()
    st.session_state.task_input = ""

st.subheader("📃 All Tasks")
for task in st.session_state["task_list"]:
    checked = st.checkbox(task, value=st.session_state[f"{task}_checked"])

    if checked and not st.session_state[f"{task}_checked"]:
        st.session_state[f"{task}_timestamp_Completed"] = datetime.now()

    st.session_state[f"{task}_checked"] = checked

st.subheader("✅ Completed Tasks")
for task in st.session_state["task_list"]:
    if st.session_state[f"{task}_checked"] and st.session_state[f"{task}_timestamp"]:
        duration = st.session_state[f"{task}_timestamp_Completed"] - st.session_state[f"{task}_timestamp"]
        seconds = int(duration.total_seconds())
        minutes, seconds = divmod(seconds, 60)
        st.write(f"✔️ {task} — completed in {minutes}m {seconds}s")
