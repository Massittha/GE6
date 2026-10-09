
from pathlib import Path
import pandas as pd
from utils import fetch_incremental_transfers


# Configuration
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

RAW_PATH = DATA_DIR / "raw" / "GE6_txn.parquet"
PROCESSED_PATH = DATA_DIR / "curate" / "GE6_txn_processed.parquet"

DATA_DIR.mkdir(parents=True, exist_ok=True)

VOTE_ACC = "0x86a1F49e1b1Cbd69971e99B66123264c75Ac2c8F"
OFFICIAL_SOURCE = "0x88dE4a0c186efe75fd359F4EBf36E5C4144E1255"

VOTE_METHODS = ["vote", "transfer", "multipleTransfer"]


def extract_transfers() -> pd.DataFrame:
    """Fetch incremental transfers and persist the cumulative raw data."""

    if RAW_PATH.exists():
        existing_df = pd.read_parquet(RAW_PATH)
    else:
        existing_df = None

    df = fetch_incremental_transfers(
        existing_df_transfers=existing_df
    )

    if df is None:
        raise RuntimeError("fetch_incremental_transfers returned None")

    # Persist raw data before feature engineering.
    # If extraction fails, the existing file is left untouched.
    temp_path = RAW_PATH.with_suffix(".tmp.parquet")
    df.to_parquet(temp_path, index=False)
    temp_path.replace(RAW_PATH)

    return df


def transform_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """Add timestamp, wallet and transaction features."""

    df = df.copy()

    # Convert timestamps to Bangkok time.
    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"],
        utc=True
    )
    df["Datetime"] = df["Timestamp"].dt.tz_convert(
        "Asia/Bangkok"
    )

    # Wallet lists.
    voter_list = (
        df.loc[df["To"].eq(VOTE_ACC), "From"]
        .drop_duplicates()
        .unique()
    )

    official_accs = (
        df.loc[
            df["From"].eq(OFFICIAL_SOURCE),
            "To"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    # Date and time features.
    df["Date"] = df["Datetime"].dt.date
    df["Hour"] = df["Datetime"].dt.floor("h")

    df["in_game"] = df["From"].isin(voter_list).astype("int8")

    # Transaction method flags.
    df["is_vote"] = df["Method"].eq("vote").astype("int8")
    df["is_transfer"] = (
        df["Method"].eq("transfer").astype("int8")
    )
    df["is_multipleTransfer"] = (
        df["Method"].eq("multipleTransfer").astype("int8")
    )

    # Ensure Value is numeric before calculating amounts.
    df["Value"] = pd.to_numeric(df["Value"], errors="raise")

    # Amount features.
    df["vote_amount"] = df["Value"].where(
        df["Method"].eq("vote"), 0
    )
    df["transfer_amount"] = df["Value"].where(
        df["Method"].eq("transfer"), 0
    )
    df["multipleTransfer_amount"] = df["Value"].where(
        df["Method"].eq("multipleTransfer"), 0
    )
    df["minting_amount"] = df["Value"].where(
        ~df["Method"].isin(VOTE_METHODS), 0
    )

    # Per-wallet, per-date aggregates.
    wallet_date = df.groupby(["From", "Date"])

    df["vote_amount_by_wallet_per_date"] = (
        wallet_date["vote_amount"].transform("sum")
    )
    df["multipleTransfer_amount_by_wallet_per_date"] = (
        wallet_date["multipleTransfer_amount"].transform("sum")
    )
    df["num_out_bound_txn_by_wallet_per_date"] = (
        wallet_date["Tx Hash"].transform("count")
    )

    # Preserve the official account list for future pipeline stages.
    df.attrs["official_accs"] = official_accs

    return df


def main() -> None:
    print("Starting GE6 transfer extraction...")

    df_raw = extract_transfers()
    print(f"Raw transfers: {len(df_raw):,} rows")

    df_processed = transform_transfers(df_raw)

    temp_path = PROCESSED_PATH.with_suffix(".tmp.parquet")
    df_processed.to_parquet(temp_path, index=False)
    temp_path.replace(PROCESSED_PATH)

    print(f"Processed transfers: {len(df_processed):,} rows")
    print(f"Raw data saved to: {RAW_PATH}")
    print(f"Processed data saved to: {PROCESSED_PATH}")
    print("GE6 transfer extraction completed successfully.")


if __name__ == "__main__":
    main()
