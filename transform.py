

from pathlib import Path
import pandas as pd


# Configuration
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
RAW_PATH = DATA_DIR / "curate" / "GE6_txn_processed.parquet"
PROCESSED_PATH = DATA_DIR / "curate" / "daily_balance_sheet.parquet"
PERSIST_PATH = DATA_DIR / "persist" / "daily_overview.parquet"

SOURCE_ACC = "0x88dE4a0c186efe75fd359F4EBf36E5C4144E1255"
VOTE_ACC = "0x86a1F49e1b1Cbd69971e99B66123264c75Ac2c8F"
MINT = "0x0000000000000000000000000000000000000000"

def create_daily_balance_sheet(df_transfers: pd.DataFrame) -> pd.DataFrame:
    daily_in_bound_df = df_transfers.groupby(["To","Date"]).agg(in_bound_amount = ("Value","sum"),
                                                in_bound_txns = ("Tx Hash","count"),
                                                in_bound_vote_amount = ("vote_amount","sum"),
                                                in_bound_transfer_amount = ("transfer_amount","sum"),
                                                in_bound_multipleTransfer_amount = ("multipleTransfer_amount","sum"),
                                                in_bound_is_vote = ("is_vote","sum"),
                                                in_bound_is_transfer = ("is_transfer","sum"),
                                                in_bound_is_multipleTransfer = ("is_multipleTransfer","sum"),
                                                max_in_bound_amount = ("Value","max"),
                                                min_in_bound_amount = ("Value","min")).reset_index().rename(columns={"To":"From"})

    daily_out_bound_df = df_transfers.groupby(["From","Date"]).agg(out_bound_amount = ("Value","sum"),
                                                out_bound_txns = ("Tx Hash","count"),
                                                out_bound_vote_amount = ("vote_amount","sum"),
                                                max_vote_amount_per_txn = ("vote_amount","max"),
                                                min_vote_amount_per_txn = ("vote_amount","min"),
                                                max_out_bound_vote_amount = ("vote_amount_by_wallet_per_date","max"),
                                                out_bound_transfer_amount = ("transfer_amount","sum"),
                                                out_bound_multipleTransfer_amount = ("multipleTransfer_amount","sum"),
                                                out_bound_is_vote = ("Method", lambda x: (x == "vote").sum()),
                                                out_bound_is_transfer = ("is_transfer","sum"),
                                                out_bound_is_multipleTransfer = ("is_multipleTransfer","sum"),
                                                max_out_bound_amount = ("Value","max"),
                                                min_out_bound_amount = ("Value","min"),
                                                unique_out_bound_wallet = ("To","nunique")).reset_index()
    

    daily_balance_sheet = pd.merge(daily_in_bound_df, daily_out_bound_df, how="outer", on=["From","Date"]).fillna(0)
    daily_balance_sheet = daily_balance_sheet.reset_index(drop=True)
    daily_balance_sheet = daily_balance_sheet.sort_values(by=["From","Date"])
    daily_balance_sheet["accum_in_bound_amount"] = daily_balance_sheet.groupby(["From"])["in_bound_amount"].cumsum()
    daily_balance_sheet["accum_out_bound_amount"] = daily_balance_sheet.groupby(["From"])["out_bound_amount"].cumsum()
    daily_balance_sheet["balance"] = daily_balance_sheet["accum_in_bound_amount"]-daily_balance_sheet["accum_out_bound_amount"]
    daily_balance_sheet["balance_change_since_last_active_date"] = daily_balance_sheet.groupby(["From"])["balance"].diff().fillna(daily_balance_sheet["balance"])


    return daily_balance_sheet


def create_daily_overview(daily_balance_sheet: pd.DataFrame, official_accs: list, ex: list) -> pd.DataFrame:

    daily_token_sold = daily_balance_sheet.loc[daily_balance_sheet["From"].isin(official_accs)].groupby("Date")["out_bound_amount"].sum().sort_index().reset_index()
    daily_token_sold["token_in_circulation"] = daily_token_sold["out_bound_amount"].cumsum()
    
    daily_token_spent = daily_balance_sheet.loc[~daily_balance_sheet["From"].isin(ex)].groupby("Date").agg(vote_amount =("out_bound_vote_amount","sum")).sort_index().reset_index()
    daily_token_spent["accum_vote_amount"] = daily_token_spent["vote_amount"].cumsum()

    daily_overview = pd.merge(left=daily_token_sold,right=daily_token_spent,how='left',on='Date')
    daily_overview['token_unspent'] = daily_overview['token_in_circulation'] - daily_overview['accum_vote_amount']

    daily_overview = daily_overview[['Date','token_in_circulation','accum_vote_amount','token_unspent']]

    return daily_overview



def main() -> None:
    print("Starting creating daily_balance_sheet...")

    df_transfers = pd.read_parquet(RAW_PATH)
    print(f"Processed transfers: {len(df_transfers):,} rows")

    daily_balance_sheet = create_daily_balance_sheet(df_transfers)

    temp_path = PROCESSED_PATH.with_suffix(".tmp.parquet")
    daily_balance_sheet.to_parquet(temp_path, index=False)
    temp_path.replace(PROCESSED_PATH)

    print(f"daily balance sheet: {len(daily_balance_sheet):,} rows")
    print(f"daily balance sheet saved to: {PROCESSED_PATH}")
    print("daily_balance_sheet saved successfully.")
    print("#########################################")

    official_accs = (
    df_transfers.loc[
        df_transfers['From'].eq(SOURCE_ACC),
        'To'
    ]
    .dropna()
    .unique()
    .tolist()
    )
    ex = official_accs + [SOURCE_ACC, VOTE_ACC, MINT]

    daily_overview = create_daily_overview(daily_balance_sheet,official_accs,ex)

    temp_path = PERSIST_PATH.with_suffix(".tmp.parquet")
    daily_overview.to_parquet(temp_path, index=False)
    temp_path.replace(PERSIST_PATH)

    print(f"daily overview: {len(daily_overview):,} rows")
    print(f"daily balance sheet saved to: {PERSIST_PATH}")
    print("daily_overview saved successfully.")
    print("#########################################")


if __name__ == "__main__":
    main()
