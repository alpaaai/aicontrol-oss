"""Agent registry view."""
import os

import pandas as pd
import requests
import streamlit as st

from dashboard.queries import get_agents

_API_BASE = os.environ.get("AICONTROL_API_URL", "http://localhost:8001")
_ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def _patch_approved_tools(agent_id: str, tools: list) -> None:
    """Call the API endpoint to replace approved_tools. Never write DB directly."""
    try:
        resp = requests.patch(
            f"{_API_BASE}/agents/{agent_id}/approved-tools",
            headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"},
            json={"approved_tools": tools},
            timeout=5,
        )
        if resp.status_code == 200:
            st.success("Approved tools updated.")
            st.rerun()
        else:
            st.error(f"Update failed: {resp.status_code} — {resp.text}")
    except requests.RequestException as e:
        st.error(f"Could not reach API: {e}")

STATUS_ICONS = {
    "active": "✅",
    "suspended": "🔴",
}


def render() -> None:
    st.header("Registered Agents")

    agents = get_agents()

    if not agents:
        st.info("No agents registered yet. Run the seed script.")
        return

    df = pd.DataFrame(agents)
    df["status"] = df["status"].map(
        lambda s: f"{STATUS_ICONS.get(s, '')} {s}"
    )
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    st.dataframe(
        df[["name", "owner", "status", "framework", "model_version", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(agents)} agents registered")

    st.divider()
    st.subheader("Agent Detail")

    agent_names = [a["name"] for a in agents]
    selected_name = st.selectbox("Select agent to inspect", agent_names)
    selected = next((a for a in agents if a["name"] == selected_name), None)

    if selected is None:
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Owner:** {selected['owner']}")
        st.markdown(f"**Status:** {selected['status']}")
    with col2:
        if selected.get("framework"):
            st.markdown(f"**Framework:** {selected['framework']}")
        if selected.get("model_version"):
            st.markdown(f"**Model:** {selected['model_version']}")

    st.markdown("**Approved Tools**")
    approved = selected.get("approved_tools")
    if approved:
        for tool in approved:
            st.write(f"✓ `{tool}`")
    else:
        st.warning("No tool restrictions — all tools permitted.")

    with st.expander("Edit approved tools"):
        current_tools = approved or []
        tools_text = st.text_area(
            "One tool name per line. Clear all lines to remove restrictions.",
            value="\n".join(current_tools),
            height=150,
            key=f"approved_tools_edit_{selected['id']}",
        )
        col_save, col_clear = st.columns([1, 1])
        with col_save:
            if st.button("Save", key=f"save_tools_{selected['id']}"):
                new_tools = [t.strip() for t in tools_text.splitlines() if t.strip()]
                _patch_approved_tools(selected["id"], new_tools)
        with col_clear:
            if st.button("Clear all", key=f"clear_tools_{selected['id']}"):
                _patch_approved_tools(selected["id"], [])
