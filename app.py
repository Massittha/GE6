import html
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import json


def format_numeric_columns(df, exclude=None):
    exclude = exclude or ["Date", "From"]
    df = df.copy()

    for col in df.select_dtypes(include="number").columns:
        if col not in exclude:
            df[col] = df[col].map(
                lambda x: f"{x:,.3f}".rstrip("0").rstrip(".")
                if pd.notna(x) else ""
            )
    return df


def short_wallet(address):
    address = str(address)
    return f"{address[:6]}...{address[-4:]}" if len(address) > 14 else address


def render_podium(df, wallet_col, amount_col, rank_col):
    """Render a mobile-friendly top-three ranking using Streamlit HTML rendering."""
    if df.empty:
        return

    top3 = df.sort_values(rank_col).head(3).copy()
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    cards = []

    for _, row in top3.iterrows():
        rank = int(row[rank_col])
        wallet = str(row[wallet_col])
        wallet_short = html.escape(short_wallet(wallet))
        try:
            amount = f"{float(row[amount_col]):,.3f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            amount = html.escape(str(row[amount_col]))

        cards.append(f"""
            <div class="ge6-rank-card">
                <div class="ge6-rank-medal">{medals.get(rank, "🏅")}</div>
                <div class="ge6-rank-number">#{rank}</div>
                <div class="ge6-rank-wallet">{wallet_short}</div>
                <div class="ge6-rank-amount">{amount}</div>
            </div>
        """)

    # st.html renders HTML directly; it avoids Markdown interpreting the markup
    # as literal code in some app/runtime combinations.
    st.html("""
        <style>
        .ge6-podium {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin: 8px 0 16px;
        }
        .ge6-rank-card {
            min-width: 0;
            box-sizing: border-box;
            text-align: center;
            padding: 18px 8px;
            border: 1px solid rgba(128,128,128,.35);
            border-radius: 14px;
            overflow-wrap: anywhere;
        }
        .ge6-rank-medal { font-size: 28px; line-height: 1.3; }
        .ge6-rank-number { font-size: 20px; font-weight: 700; margin-top: 4px; }
        .ge6-rank-wallet { font-size: 13px; margin: 8px 0; }
        .ge6-rank-amount { font-size: 17px; font-weight: 700; }
        @media (max-width: 600px) {
            .ge6-podium {
                grid-template-columns: minmax(0, 1fr);
                gap: 8px;
            }
            .ge6-rank-card {
                display: grid;
                grid-template-columns: 36px 44px minmax(0, 1fr) auto;
                align-items: center;
                gap: 8px;
                text-align: left;
                padding: 12px;
            }
            .ge6-rank-medal { font-size: 23px; }
            .ge6-rank-number { font-size: 16px; margin: 0; }
            .ge6-rank-wallet { margin: 0; }
            .ge6-rank-amount { font-size: 15px; text-align: right; }
        }
        </style>
    """ + '<div class="ge6-podium">' + "".join(cards) + "</div>")

    with st.expander("Show full wallet addresses"):
        for _, row in top3.iterrows():
            st.caption(f"Rank {int(row[rank_col])}")
            st.code(str(row[wallet_col]), language=None)



def render_mobile_leaderboard_cards(
    df,
    rank_col,
    wallet_col,
    amount_col,
    previous_rank_col=None,
):
    """Render leaderboard rows as stacked cards, suitable for mobile screens."""
    if df.empty:
        st.info("No leaderboard data available.")
        return

    for _, row in df.iterrows():
        rank = row.get(rank_col)
        wallet = str(row.get(wallet_col, ""))
        amount = row.get(amount_col)

        try:
            rank_label = f"#{int(rank)}"
        except (TypeError, ValueError):
            rank_label = str(rank)

        try:
            amount_label = f"{float(amount):,.3f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            amount_label = str(amount)

        change_label = ""
        if previous_rank_col and previous_rank_col in df.columns:
            previous = row.get(previous_rank_col)
            if pd.notna(previous) and pd.notna(rank):
                delta = int(previous) - int(rank)
                if delta > 0:
                    change_label = f"▲ {delta} from previous rank #{int(previous)}"
                elif delta < 0:
                    change_label = f"▼ {abs(delta)} from previous rank #{int(previous)}"
                else:
                    change_label = f"— unchanged from #{int(previous)}"
            else:
                change_label = "No previous ranking"

        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.markdown(f"**{rank_label} · {short_wallet(wallet)}**")
            if change_label:
                st.caption(change_label)
        with right:
            st.markdown(f"<div style='text-align:right;font-weight:700;font-size:1.05rem'>{html.escape(amount_label)}</div>", unsafe_allow_html=True)
            st.caption("Votes")

        with st.expander("Wallet address"):
            st.code(wallet, language=None)

        st.divider()

def render_daily_leaderboard(path):
    """Render daily leaderboard with date picker, podium and ranking table."""
    if not path.exists():
        st.warning("Daily top voters data not found.")
        return

    daily = load_top_voters(str(path)).copy()
    required = {"Date", "ranking", "From", "out_bound_vote_amount"}
    missing = required - set(daily.columns)
    if missing:
        st.error(f"Daily leaderboard is missing columns: {', '.join(sorted(missing))}")
        return

    daily["Date"] = pd.to_datetime(daily["Date"], errors="coerce").dt.normalize()
    dates = sorted(daily["Date"].dropna().unique(), reverse=True)
    if not dates:
        st.info("No daily voting data available.")
        return

    selected_date = st.selectbox(
        "Select date",
        options=dates,
        format_func=lambda value: pd.Timestamp(value).strftime("%d %b %Y"),
        key="daily_leaderboard_date",
    )
    selected = (
        daily.loc[daily["Date"] == selected_date]
        .sort_values("ranking")
        .head(20)
        .copy()
    )

    st.subheader(f"Top voters · {pd.Timestamp(selected_date):%d %b %Y}")
    render_podium(
        selected,
        wallet_col="From",
        amount_col="out_bound_vote_amount",
        rank_col="ranking",
    )
    st.divider()
    st.subheader("Full ranking")

    display = selected.rename(columns={
        "ranking": "Ranking",
        "From": "Wallet Address",
        "out_bound_vote_amount": "Vote Amount (Sum By Date)",
    })[["Ranking", "Wallet Address", "Vote Amount (Sum By Date)"]]
    display = format_numeric_columns(display)

    view = st.radio(
        "Display format",
        ["Mobile cards", "Full table"],
        horizontal=True,
        key="daily_leaderboard_view",
        label_visibility="collapsed",
    )
    if view == "Mobile cards":
        render_mobile_leaderboard_cards(
            selected,
            rank_col="ranking",
            wallet_col="From",
            amount_col="out_bound_vote_amount",
        )
    else:
        st.dataframe(display, use_container_width=True, hide_index=True, height=640)


def render_all_time_leaderboard(path):
    """Render a date-filterable all-time snapshot, podium and rank movement table."""
    if not path.exists():
        st.warning("All-time top voters data not found.")
        return

    voters = load_top_voters(str(path)).copy()
    required = {"ranking_by_vote", "From", "accum_vote"}
    missing = required - set(voters.columns)
    if missing:
        st.error(f"All-time leaderboard is missing columns: {', '.join(sorted(missing))}")
        return

    if "Date" not in voters.columns:
        st.error("Cannot filter the all-time leaderboard by date because the data has no 'Date' column.")
        return

    voters["Date"] = pd.to_datetime(voters["Date"], errors="coerce").dt.normalize()
    dates = sorted(voters["Date"].dropna().unique(), reverse=True)
    if not dates:
        st.info("No dated all-time voting snapshots are available.")
        return

    selected_date = st.selectbox(
        "Select snapshot date",
        options=dates,
        format_func=lambda value: pd.Timestamp(value).strftime("%d %b %Y"),
        key="all_time_leaderboard_date",
    )

    voters = voters.loc[voters["Date"] == selected_date].copy()
    voters = voters.sort_values("ranking_by_vote").head(20)

    st.subheader(f"All-time leaders · {pd.Timestamp(selected_date):%d %b %Y}")
    st.caption("Rank movement compares this snapshot with the previous snapshot.")
    render_podium(
        voters,
        wallet_col="From",
        amount_col="accum_vote",
        rank_col="ranking_by_vote",
    )
    st.divider()
    st.subheader("Full ranking")

    columns = ["ranking_by_vote"]
    if "previous_date_ranking" in voters.columns:
        columns.append("previous_date_ranking")
    columns += ["From", "accum_vote"]

    display = voters[columns].rename(columns={
        "ranking_by_vote": "Ranking",
        "previous_date_ranking": "Previous Date Ranking",
        "From": "Wallet Address",
        "accum_vote": "Vote Amount (Cumulative)",
    }).copy()

    if "Previous Date Ranking" in display.columns:
        def rank_change(row):
            current, previous = row["Ranking"], row["Previous Date Ranking"]
            if pd.isna(current) or pd.isna(previous):
                return "—"
            delta = int(previous) - int(current)
            if delta > 0:
                return f"▲ {delta}"
            if delta < 0:
                return f"▼ {abs(delta)}"
            return "—"

        display.insert(1, "Rank Change", display.apply(rank_change, axis=1))

    display = format_numeric_columns(display)

    view = st.radio(
        "Display format",
        ["Mobile cards", "Full table"],
        horizontal=True,
        key="all_time_leaderboard_view",
        label_visibility="collapsed",
    )
    if view == "Mobile cards":
        render_mobile_leaderboard_cards(
            voters,
            rank_col="ranking_by_vote",
            wallet_col="From",
            amount_col="accum_vote",
            previous_rank_col=(
                "previous_date_ranking"
                if "previous_date_ranking" in voters.columns
                else None
            ),
        )
    else:
        st.dataframe(display, use_container_width=True, hide_index=True, height=640)


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

DATA_PATH = Path("data/persist/daily_overview.parquet")
STATUS_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "persist"
    / "pipeline_status.json"
)
CURATE_PATH = Path("data/curate")
TOP_VOTERS_BY_DATE_PATH = CURATE_PATH / "top_voters_by_date.parquet"
TOP_VOTERS_ALL_TIME_PATH = CURATE_PATH / "top_voters_all_time.parquet"


@st.cache_data
def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


@st.cache_data
def load_top_voters(path):
    return pd.read_parquet(path)


df = load_data()
tab_overview, tab_leaderboard = st.tabs(["📊 Overview", "🏆 Leaderboard"])

with tab_overview:
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
        f"{circulation:,.0f}",

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
        margin=dict(l=8, r=8, t=20, b=8),
        xaxis=dict(nticks=5, automargin=True),
        yaxis=dict(automargin=True),
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
        margin=dict(l=8, r=8, t=20, b=8),
        xaxis=dict(nticks=5, automargin=True),
        yaxis=dict(automargin=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
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


    with st.expander("View daily overview data", expanded = True):
        display_df = df.sort_values("Date", ascending=False).copy()

        # Show date only, without time
        display_df["Date"] = pd.to_datetime(
            display_df["Date"]
        ).dt.strftime("%Y-%m-%d")

        # Format numeric columns with thousands separators
        # numeric_cols = [
        #     "token_in_circulation",
        #     "accum_vote_amount",
        #     "token_unspent",
        # ]

        # for col in numeric_cols:
        #     display_df[col] = display_df[col].map(
        #         lambda x: f"{x:,.3f}".rstrip("0").rstrip(".")
        #         if pd.notna(x) else ""
        #     )
        display_df = format_numeric_columns(display_df)

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

with tab_leaderboard:
    st.title("🏆 GE6 Leaderboard")
    st.caption("Rankings based on on-chain voting activity.")

    daily_tab, all_time_tab = st.tabs(
        ["📅 Daily Top Voters", "🌟 All-time Top Voters"]
    )

    with daily_tab:
        render_daily_leaderboard(TOP_VOTERS_BY_DATE_PATH)

    with all_time_tab:
        render_all_time_leaderboard(TOP_VOTERS_ALL_TIME_PATH)
