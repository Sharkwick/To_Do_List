from datetime import datetime
import streamlit as st
from firebase_admin import firestore
from utils import format_task_timestamp, fmt_elapsed_since, safe_dt_str
from firebase_utils import initialize_firebase

# ------------------------------ Add New Task
def add_new_task(name, group, comment, tasks_ref):
    created_time = datetime.utcnow()
    doc = {
        "task": name,
        "group": group,
        "comment": comment,
        "completed": False,
        "timestamp": created_time,
        "created_str": format_task_timestamp(created_time)
    }
    tasks_ref.add(doc)

# ------------------------------ Delete Tasks
def delete_all_completed(tasks_ref, unique_id, db):
    btn_key = f"del_all_completed_{unique_id}"
    if st.button("❌ Delete All Pending Tasks in All Groups", key=btn_key):
        docs = list(tasks_ref.where("completed", "==", False).stream())
        if not docs:
            st.info("No pending tasks to delete.")
            return
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        st.toast("❌ Deleted all pending tasks.")
        st.rerun()

def delete_group_completed(group_name, tasks_ref, unique_id, db):
    btn_key = f"del_group_completed_{group_name}_{unique_id}"
    if st.button(f"❌ Delete All Pending Tasks in : {group_name}", key=btn_key):
        docs = list(
            tasks_ref.where("group", "==", group_name)
                     .where("completed", "==", False)
                     .stream()
        )
        if not docs:
            st.info(f"No Pending tasks to delete in '{group_name}'.")
            return
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        st.toast(f"❌ Deleted all Pending tasks in '{group_name}'.")
        st.rerun()

def delete_task(doc_id, task_text, tasks_ref):
    tasks_ref.document(doc_id).delete()
    st.toast(f"❌ Deleted '{task_text}'.")
    st.rerun()

def get_pending_count_from_firestore(grp) -> int:
    db = initialize_firebase()
    nickname = st.session_state.nickname
    tasks_ref = db.collection("tasks").document(nickname).collection("items")
    query = tasks_ref.where("completed", "==", False).where("group", "==", grp)
    return len(list(query.stream()))

def get_completed_count_from_firestore(grp) -> int:
    db = initialize_firebase()
    nickname = st.session_state.nickname
    tasks_ref = db.collection("tasks").document(nickname).collection("items")
    query = tasks_ref.where("completed", "==", True).where("group", "==", grp)
    return len(list(query.stream()))

def get_allpending_count_from_firestore() -> int:
    db = initialize_firebase()
    nickname = st.session_state.nickname
    tasks_ref = db.collection("tasks").document(nickname).collection("items")
    query = tasks_ref.where("completed", "==", False)
    return len(list(query.stream()))

# ------------------------------ Pending Tasks Renderer
def render_pending(tasks_ref, db):
    docs = list(tasks_ref.where("completed", "==", False).stream())
    if not docs:
        st.info("🎉 No Active tasks.")
        return

    grouped = {}
    for d in docs:
        grouped.setdefault(d.to_dict().get("group","General"), []).append((d.id, d.to_dict()))

    for grp, rows in grouped.items():
        completedtaskcount = get_completed_count_from_firestore(grp)
        expander_label = f" ▶ {grp}"
        grptitle1_html = f"<span style='font-size:20px;'>📂 Group Name : {grp}</span>"
        grptitle2_html = f"<span style='font-size:20px;'>⌛ Pending Task Count : {len(rows)}</span>"
        grptitle3_html = f"<span style='font-size:20px;'>✅ Completed Task Count : {completedtaskcount}</span>"
        grptitle4_html = f"<span style='font-size:20px;color:orange;'>⚠️ It seems you have {len(rows)} active tasks in {grp}. Consider clearing up some to avoid burnout 😴</span>"
        ptingrp = len(rows)
        with st.expander(expander_label, expanded=True):
            col1, col2, col3, col4 = st.columns([0.25, 0.25, 0.5, 1])
            with col1: st.markdown(grptitle1_html, unsafe_allow_html=True)
            with col2: st.markdown(grptitle2_html, unsafe_allow_html=True)
            with col3: st.markdown(grptitle3_html, unsafe_allow_html=True)
            if len(rows) > 4:
                with col4: st.markdown(grptitle4_html, unsafe_allow_html=True)

            # Delete all group tasks if too many
            if ptingrp > 3:
                delete_group_completed(grp, tasks_ref, unique_id=grp, db=db)

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
                    new_comment = ec1.text_input("New Description", value=info.get("comment",""), key=f"comm_{doc_id}")
                    mark_completed = ec2.checkbox("Mark as completed", value=False, key=f"complete_{doc_id}")
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        update_payload = {"comment": new_comment}
                        if mark_completed:
                            update_payload["completed"] = True
                            update_payload["completed_time"] = datetime.utcnow()
                        tasks_ref.document(doc_id).update(update_payload)
                        st.toast("✅ Updated.")
                        st.session_state[f"edit_{doc_id}"] = False
                        st.rerun()

    getallpendingtaskscount = get_allpending_count_from_firestore()
    if getallpendingtaskscount > 4:
        delete_all_completed(tasks_ref, unique_id="main_app", db=db)

# ------------------------------ Completed Tasks Renderer
def render_completed(tasks_ref,db):
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
        }))

    for grp, rows in grouped.items():
        pendingtaskcount = get_pending_count_from_firestore(grp)
        expander_label = f" ▶ {grp}"
        grptitle1_html = f"<span style='font-size:20px;'>📂 Group Name : {grp}</span>"
        grptitle2_html = f"<span style='font-size:20px;'>✅ Completed Task Count : {len(rows)}</span>"
        grptitle3_html = f"<span style='font-size:20px;'>⌛ Pending Task Count : {pendingtaskcount}</span>"

        with st.expander(expander_label, expanded=True):
            col1, col2, col3 = st.columns([0.2, 0.2, 1])
            with col1: st.markdown(grptitle1_html, unsafe_allow_html=True)
            with col2: st.markdown(grptitle2_html, unsafe_allow_html=True)
            with col3: st.markdown(grptitle3_html, unsafe_allow_html=True)

            # Header row
            h = st.columns([0.26, 0.26, 0.16, 0.16, 0.10, 0.06])
            headers = ["Task Name", "Task Description", "Added Date", "Completed Date", "Duration", "Completed?"]
            for i, title in enumerate(headers):
                h[i].markdown(f"<div class='task-row task-header'>{title}</div>", unsafe_allow_html=True)

            # Data rows
            for doc_id, row in rows:
                c = st.columns([0.26, 0.26, 0.16, 0.16, 0.10, 0.06])

                c[0].markdown(f"<div class='task-row'>{row.get('Task', '—')}</div>", unsafe_allow_html=True)
                c[1].markdown(f"<div class='task-row'>{row.get('Comment', '—')}</div>", unsafe_allow_html=True)
                c[2].markdown(f"<div class='task-row'>{row.get('Added', '—')}</div>", unsafe_allow_html=True)
                c[3].markdown(f"<div class='task-row'>{row.get('Completed', '—')}</div>", unsafe_allow_html=True)
                c[4].markdown(f"<div class='task-row'>{row.get('Duration', '—')}</div>", unsafe_allow_html=True)

                # Interactive checkbox
                new_val = c[5].checkbox("", value=bool(row.get("Completed")), key=f"compchk_{doc_id}")
                if not new_val and row.get("Completed"):
                    tasks_ref.document(doc_id).update({"completed": False, "completed_time": firestore.DELETE_FIELD})
                    st.success("↩️ Moved back to Pending.")
                    st.rerun()
