"""Agent registry view."""
import pandas as pd
import streamlit as st

from dashboard.queries import get_agents

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
