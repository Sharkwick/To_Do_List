import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

def setup_page():
    st.set_page_config(page_title="Wickz Day Planner", layout="wide")
    st.markdown("""
        <style>.custom-button {font-size: 18px;font-weight: bold;background-color: #4CAF50;color: white;border-radius: 12px;padding: 8px 24px;}</style>
    """, unsafe_allow_html=True)

def sidebar(nickname, tasks_ref, db):
    docs_all = list(tasks_ref.stream())
    pending_count, completed_count = 0, 0
    group_stats = {}

    for d in docs_all:
        info = d.to_dict()
        grp  = info.get("group", "General")
        done = info.get("completed", False)
        if done: completed_count += 1
        else: pending_count += 1
        group_stats.setdefault(grp, {"total": 0, "completed": 0})
        group_stats[grp]["total"]     += 1
        group_stats[grp]["completed"] += int(done)

    overall_count = pending_count + completed_count

    with st.sidebar:
        st.markdown(f"# Welcome Back {nickname}")
        if st.button("🔁 Refresh"): st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("# 💻 Tasks Overview")
        st.markdown(f"### 🔎 Total Tasks Count : {overall_count}")
        st.markdown(f"#### ⌛ Pending Tasks Count : {pending_count}")
        st.markdown(f"#### ✅ Completed Tasks Count : {completed_count}")
        st.markdown("---")

        st.markdown("# 📈 Tasks Status Overview")
        options = ["All"] + list(group_stats.keys())
        sel = st.selectbox("Select task group", options, key="pie_group")
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

        st.markdown("---")
        st.markdown("<p style='font-size:12px;color:gray;text-align:center;'>&copy; 2025 Wickz Day Planner. All rights reserved.</p>", unsafe_allow_html=True)

    return pending_count, completed_count
