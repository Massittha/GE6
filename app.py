
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import json

st.set_page_config(
    page_title="GE6 On-chain Dashboard",
    page_icon="📊",
    layout="wide",
)


if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()


st.title("GE6 On-chain Dashboard")
st.caption("Unofficial community tracker · On-chain data")

# Load processed data
DATA_PATH = Path("data/persist/daily_overview.parquet")

STATUS_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "persist"
    / "pipeline_status.json"
)

@st.cache_data
def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)

df = load_data()


# Latest available snapshot
latest = df.iloc[-1]

circulation = latest["token_in_circulation"]
voted = latest["accum_vote_amount"]
unspent = latest["token_unspent"]

st.caption(f"Latest snapshot: {latest['Date']:%d %b %Y}")

if STATUS_PATH.exists():
    try:
        with STATUS_PATH.open("r", encoding="utf-8") as f:
            pipeline_status = json.load(f)

        if pipeline_status.get("status") == "success":
            last_run = pd.to_datetime(
                pipeline_status["last_successful_run"]
            )

            st.caption(
                "Last successful data update: "
                f"{last_run.strftime('%d %b %Y, %H:%M:%S')} ICT"
            )

        else:
            st.warning("Pipeline has not completed successfully.")

    except (OSError, ValueError, KeyError) as e:
        st.warning(f"Could not read pipeline status: {e}")
else:
    st.caption("Last successful data update: Not available yet")

# Overview metrics
c1, c2, c3 = st.columns(3)

c1.metric(
    "Token in circulation",
    f"{circulation:,.0f}"
)

c2.metric(
    "Used for voting",
    f"{voted:,.2f}",
    f"{voted / circulation:.1%} of circulation"
    if pd.notna(voted) and circulation > 0
    else None,
    delta_arrow="off"
)

c3.metric(
    "Not deployed for voting",
    f"{unspent:,.2f}",
    f"{unspent / circulation:.1%} of circulation"
    if pd.notna(unspent) and circulation > 0
    else None,
    delta_arrow="off"
)

st.divider()

# Chart 1: Token in circulation
st.subheader("Token in Circulation")

fig_circulation = px.line(
    df,
    x="Date",
    y="token_in_circulation",
    markers=True,
    labels={
        "Date": "Date",
        "token_in_circulation": "Tokens",
    },
)

fig_circulation.update_layout(
    hovermode="x unified",
    yaxis_title="Tokens",
    xaxis_title=None,
)

st.plotly_chart(fig_circulation, use_container_width=True)

# Chart 2: Voting deployment vs remaining tokens
st.subheader("Voting Deployment")

chart_df = df.melt(
    id_vars="Date",
    value_vars=["accum_vote_amount", "token_unspent"],
    var_name="Metric",
    value_name="Tokens",
)

chart_df["Metric"] = chart_df["Metric"].map({
    "accum_vote_amount": "Used for voting",
    "token_unspent": "Not deployed",
})

fig_voting = px.line(
    chart_df,
    x="Date",
    y="Tokens",
    color="Metric",
    markers=True,
    labels={
        "Date": "Date",
        "Tokens": "Tokens",
        "Metric": "Metric",
    },
)

fig_voting.update_layout(
    hovermode="x unified",
    xaxis_title=None,
)

st.plotly_chart(fig_voting, use_container_width=True)

# Show underlying data
# Show daily data: latest date first
# with st.expander("View daily data", expanded=True):
#     display_df = df.sort_values("Date", ascending=False)

#     st.dataframe(
#         display_df,
#         use_container_width=True,
#         hide_index=True
#     )


with st.expander("View daily data", expanded = True):
    display_df = df.sort_values("Date", ascending=False).copy()

    # Show date only, without time
    display_df["Date"] = pd.to_datetime(
        display_df["Date"]
    ).dt.strftime("%Y-%m-%d")

    # Format numeric columns with thousands separators
    numeric_cols = [
        "token_in_circulation",
        "accum_vote_amount",
        "token_unspent",
    ]

    for col in numeric_cols:
        display_df[col] = display_df[col].map(
            lambda x: f"{x:,.3f}".rstrip("0").rstrip(".")
            if pd.notna(x) else ""
        )

    # Rename columns for readability
    display_df = display_df.rename(columns={
        "token_in_circulation": "Token in circulation",
        "accum_vote_amount": "Used for voting",
        "token_unspent": "Not deployed for voting",
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )
