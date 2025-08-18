import os
import json
import hashlib
from datetime import datetime, timezone

import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

import firebase_admin
from firebase_admin import credentials, firestore

# ------------------------------ Page config
st.set_page_config(
    page_title="Wickz Day Planner",
    layout="wide",
    initial_sidebar_state="auto"
)

# ------------------------------ Firebase Initialization
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

# ------------------------------ Utility Functions
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
    st.rerun()

# ------------------------------ Delete Completed Tasks ------------------------------
def delete_all_completed(tasks_ref, unique_id):
    btn_key = f"del_all_completed_{unique_id}"
    if st.button("❌ Delete All Pending Tasks", key=btn_key):
        docs = list(tasks_ref.where("completed", "==", False).stream())
        if not docs:
            st.info("No completed tasks to delete.")
            return
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        st.toast("❌ Deleted all pending tasks.")
        st.rerun()

def delete_group_completed(group_name, tasks_ref, unique_id):
    btn_key = f"del_group_completed_{group_name}_{unique_id}"
    if st.button(f"❌ Delete Pending Tasks in '{group_name}'", key=btn_key):
        docs = list(
            tasks_ref.where("group", "==", group_name)
                     .where("completed", "==", False)
                     .stream()
        )
        if not docs:
            st.info(f"No completed tasks to delete in '{group_name}'.")
            return
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        st.toast(f"❌ Deleted all Pending tasks in '{group_name}'.")
        st.experimental_rerun()

def delete_task(doc_id, task_text, tasks_ref):
    tasks_ref.document(doc_id).delete()
    st.toast(f"❌ Deleted '{task_text}'.")
    st.rerun()

def fmt_elapsed_since(ts: datetime) -> str:
    if not isinstance(ts, datetime):
        return "N/A"
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    now = datetime.utcnow()
    delta = now - ts
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{days:02d}d {hours:02d}:{minutes:02d}"

def safe_dt_str(dt: datetime) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return "N/A"

# ------------------------------ Session State Defaults
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nickname = ""

# ------------------------------ Authentication
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

# ------------------------------ Main App
nickname  = st.session_state.nickname
tasks_ref = db.collection("tasks").document(nickname).collection("items")
st.markdown("<h1 style='text-align:center;'>📝 Wickz Day Planner</h1>", unsafe_allow_html=True)

# Fetch all tasks
all_docs = list(tasks_ref.stream())

# Initialize counters
pending_count = 0
completed_count = 0

for d in all_docs:
    info = d.to_dict()
    if info.get("completed", False):
        completed_count += 1
    else:
        pending_count += 1
overall_count = pending_count + completed_count

# ------------------------------ Sidebar
with st.sidebar:
    st.markdown(f"# Welcome Back {nickname}")
    st.markdown("## Let's Start Planning Your Day!!")
    if st.button("🔁 Refresh"): st.rerun()
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("# 💻 Tasks Overview")
    st.markdown(f"### Total Tasks Count : {overall_count}")
    st.markdown(f"#### Pending Tasks Count : {pending_count}")
    st.markdown(f"#### Completed Tasks Count : {completed_count}")
    st.markdown("---")
    st.markdown("# 📈 Tasks Status Overview")
    docs_all = list(tasks_ref.stream())
    group_stats = {}
    for d in docs_all:
        info = d.to_dict()
        grp  = info.get("group", "General")
        done = info.get("completed", False)
        group_stats.setdefault(grp, {"total": 0, "completed": 0})
        group_stats[grp]["total"]     += 1
        group_stats[grp]["completed"] += int(done)

    options = ["All"] + list(group_stats.keys())
    sel = st.selectbox("Select task group from the dropdown", options, key="pie_group")
    if sel == "All":
        total = sum(v["total"] for v in group_stats.values())
        comp  = sum(v["completed"] for v in group_stats.values())
    else:
        total = group_stats.get(sel, {}).get("total", 0)
        comp  = group_stats.get(sel, {}).get("completed", 0)

    rem = total - comp
    if total > 0:
        fig, ax = plt.subplots(figsize=(4,4), facecolor="white")
        ax.pie([comp, rem],
               labels=["Completed","Remaining"],
               autopct="%1.0f%%",
               startangle=90,
               colors=sns.color_palette("muted", 2),
               wedgeprops={"edgecolor":"white","linewidth":1.5})
        ax.set_title(f"{sel} Tasks", pad=12)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No tasks to summarize.")

# ------------------------------ Add New Task
st.markdown("# Add New Task")
c1, c2 = st.columns(2)
task_txt   = c1.text_input("Task Name", key="new_task")
group_sel  = c2.selectbox("Choose group", ["Work","Personal","General"], key="group_sel")
group_cust = c2.text_input("Or custom group", key="group_custom")
comment    = st.text_area("Task Description", key="new_comment")
if st.button("Add Task"):
    final_grp = group_cust.strip() or group_sel
    if task_txt.strip():
        add_new_task(task_txt.strip(), final_grp, comment.strip(), tasks_ref)
    else:
        st.error("❌ Task Name cannot be empty.")

# ------------------------------ Toggle Pending / Completed
view_completed = st.toggle("Show Completed Tasks", value=False)

if not view_completed:
    st.markdown(f"## 🗂️ Active Tasks : {pending_count}")
else:
    st.markdown(f"## ✅ Completed Tasks : {completed_count}")

# ------------------------------ Filter helpers
def in_added_range(ts: datetime) -> bool:
    if not isinstance(ts, datetime): return False
    return True  # Keep original filter logic if needed

def in_completed_range(ct: datetime) -> bool:
    if not isinstance(ct, datetime): return False
    return True  # Keep original filter logic if needed

# ------------------------------ Pending Tasks
def render_pending(tasks_ref):
    docs = list(tasks_ref.where("completed", "==", False).stream())
    if not docs:
        st.info("🎉 No pending tasks.")
        return

    grouped = {}
    for d in docs:
        grouped.setdefault(d.to_dict().get("group","General"), []).append((d.id, d.to_dict()))

    for grp, rows in grouped.items():
        grptitle1_html = f"<span style='font-size:20px;'>📂 {grp} (Task Count : {len(rows)})</span>"
        with st.expander("", expanded=True):
            st.markdown(grptitle1_html, unsafe_allow_html=True)

            # Delete completed tasks in this group (button only)
            delete_group_completed(grp, tasks_ref, unique_id=grp)

            h = st.columns([0.28,0.28,0.16,0.10,0.08,0.10])
            h[0].markdown("**Task Name**"); h[1].markdown("**Task Description**")
            h[2].markdown("**Elapsed Time**"); h[3].markdown("**Edit Description**")
            h[4].markdown("**Delete**"); h[5].markdown("**Completed ?**")

            for doc_id, info in rows:
                if f"edit_{doc_id}" not in st.session_state:
                    st.session_state[f"edit_{doc_id}"] = False

                ts = info.get("timestamp")
                c = st.columns([0.28,0.28,0.16,0.10,0.08,0.10])
                c[0].write(info.get("task","—"))
                c[1].write(info.get("comment","—"))
                c[2].write(fmt_elapsed_since(ts))

                if c[3].button("✏️", key=f"edit_btn_{doc_id}"):
                    st.session_state[f"edit_{doc_id}"] = True

                if c[4].button("❌️", key=f"del_{doc_id}"):
                    delete_task(doc_id, info.get("task",""), tasks_ref)

                new_val = c[5].checkbox("", value=info.get("completed",False), key=f"chk_{doc_id}")
                if new_val != info.get("completed",False):
                    payload = {"completed": new_val}
                    if new_val: payload["completed_time"] = datetime.utcnow()
                    else: payload["completed_time"] = firestore.DELETE_FIELD
                    tasks_ref.document(doc_id).update(payload)
                    st.rerun()

                if st.session_state.get(f"edit_{doc_id}", False):
                    ec1, ec2 = st.columns([0.8, 0.2])
                    new_comment = ec1.text_input(
                        "New Description",
                        value=info.get("comment",""),
                        key=f"comm_{doc_id}"
                    )
                    mark_completed = ec2.checkbox(
                        "Mark as completed",
                        value=False,
                        key=f"complete_{doc_id}"
                    )
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        update_payload = {"comment": new_comment}
                        if mark_completed:
                            update_payload["completed"] = True
                            update_payload["completed_time"] = datetime.utcnow()
                        tasks_ref.document(doc_id).update(update_payload)
                        st.toast("✅ Updated.")
                        st.session_state[f"edit_{doc_id}"] = False
                        st.rerun()

# ------------------------------ Completed Tasks
def render_completed(tasks_ref):
    docs = list(tasks_ref.where("completed", "==", True).stream())
    if not docs:
        st.info("✅ No completed tasks.")
        return

    grouped = {}
    for d in docs:
        info = d.to_dict()
        ts, ct = info.get("timestamp"), info.get("completed_time")
        grouped.setdefault(info.get("group","General"), []).append((d.id,{
            "Task": info.get("task",""), "Comment": info.get("comment",""),
            "Added": safe_dt_str(ts), "Completed": safe_dt_str(ct),
            "Duration": str(ct-ts).split(".")[0] if ts and ct else "N/A",
            "Completed": safe_dt_str(ct)
        }))

    for grp, rows in grouped.items():
        grptitle_html = f"<span style='font-size:20px;'>✅ {grp} (Task Count : {len(rows)})</span>"
        with st.expander("", expanded=True):
            st.markdown(grptitle_html, unsafe_allow_html=True)

            h = st.columns([0.26,0.26,0.16,0.16,0.10,0.06])
            h[0].markdown("**Task Name**"); h[1].markdown("**Task Description**")
            h[2].markdown("**Added Date**"); h[3].markdown("**Completed Date**")
            h[4].markdown("**Duration**"); h[5].markdown("**Completed ?**")

            for doc_id, row in rows:
                c = st.columns([0.26,0.26,0.16,0.16,0.10,0.06])
                c[0].write(row["Task"]); c[1].write(row["Comment"])
                c[2].write(row["Added"]); c[3].write(row["Completed"])
                c[4].write(row["Duration"])
                new_val = c[5].checkbox("", value=True, key=f"compchk_{doc_id}")
                if not new_val:
                    tasks_ref.document(doc_id).update({"completed": False,"completed_time": firestore.DELETE_FIELD})
                    st.toast("↩️ Moved back to Pending.")
                    st.rerun()

# ------------------------------ Render
if view_completed:
    render_completed(tasks_ref)
else:
    render_pending(tasks_ref)
    delete_all_completed(tasks_ref, unique_id="main_app")
