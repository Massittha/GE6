

from pathlib import Path
import pandas as pd


# Configuration
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
RAW_PATH = DATA_DIR / "curate" / "GE6_txn_processed.parquet"
DAILY_BALANCE_SHEET_PATH = DATA_DIR / "curate" / "daily_balance_sheet.parquet"
DAILY_OVERVIEW_PATH = DATA_DIR / "persist" / "daily_overview.parquet"
TOP_VOTERS_BY_DATE_PATH = DATA_DIR / "curate" / "top_voters_by_date.parquet"
TOP_VOTERS_ALL_TIME_PATH = DATA_DIR / "curate" / "top_voters_all_time.parquet"

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

def create_top_voters_by_date(daily_balance_sheet):

    top_voters_by_date = daily_balance_sheet.sort_values(by=['Date','out_bound_vote_amount'],ascending=[False,False])[['Date','From','out_bound_vote_amount']].copy()
    top_voters_by_date['ranking'] = top_voters_by_date.groupby('Date')['out_bound_vote_amount'].rank(method='dense',ascending=False).astype(int) 
    #top_voters_by_date.loc[(top_voters_by_date['ranking'] <= 20) & (top_voters_by_date['out_bound_vote_amount'] > 0)].set_index('Date')[['ranking','From','out_bound_vote_amount']]

    return top_voters_by_date

def create_top_voters_all_time(daily_balance_sheet,ex):

    date_df = pd.DataFrame(daily_balance_sheet['Date'].unique().tolist(),columns=['Date'])
    wallet_df = daily_balance_sheet.loc[~daily_balance_sheet['From'].isin(ex)]['From'].drop_duplicates()
    top_voters_all_time = date_df.merge(wallet_df,how='cross')
    top_voters_all_time = top_voters_all_time.sort_values(by=['From','Date']).merge(daily_balance_sheet[['Date','From','out_bound_vote_amount','accum_in_bound_amount','accum_out_bound_amount','balance']],on=['Date','From'],how='left')
    top_voters_all_time['out_bound_vote_amount'] = top_voters_all_time['out_bound_vote_amount'].fillna(0)

    cols_to_ffill = [
        'accum_in_bound_amount',
        'accum_out_bound_amount',
        'balance'
    ]

    top_voters_all_time[cols_to_ffill] = (
        top_voters_all_time
        .groupby('From')[cols_to_ffill]
        .ffill().fillna(0)
    )

    top_voters_all_time = top_voters_all_time.sort_values(by='Date')

    top_voters_all_time['accum_vote'] = top_voters_all_time.groupby('From')['out_bound_vote_amount'].transform('cumsum')
    top_voters_all_time['potential_vote_amount'] = top_voters_all_time['balance']+top_voters_all_time['accum_vote']
    top_voters_all_time = top_voters_all_time.sort_values(by=['Date','accum_vote'],ascending=[True,False])
    top_voters_all_time['ranking_by_vote'] = top_voters_all_time.groupby('Date')['accum_vote'].rank(method='dense',ascending=False).astype(int)
    top_voters_all_time['ranking_by_potential_vote'] = top_voters_all_time.groupby('Date')['potential_vote_amount'].rank(method='dense',ascending=False).astype(int)
    previous_date_ranking_by_vote = top_voters_all_time[['Date','From','ranking_by_vote']].copy().rename(columns={'ranking_by_vote':'previous_date_raking',
                                                                                                })
    previous_date_ranking_by_vote['Date'] = previous_date_ranking_by_vote['Date'] + pd.Timedelta(days=1)

    top_voters_all_time = top_voters_all_time.merge(previous_date_ranking_by_vote,on = ['Date','From'])
    top_voters_all_time = top_voters_all_time.sort_values(by=['Date','ranking_by_vote'],ascending=[False,True])

    return top_voters_all_time

def create_daily_overview(daily_balance_sheet: pd.DataFrame, official_accs: list, ex: list) -> pd.DataFrame:

    daily_token_sold = daily_balance_sheet.loc[daily_balance_sheet["From"].isin(official_accs)].groupby("Date")["out_bound_amount"].sum().sort_index().reset_index()
    daily_token_sold["token_in_circulation"] = daily_token_sold["out_bound_amount"].cumsum()
    
    daily_token_spent = daily_balance_sheet.loc[~daily_balance_sheet["From"].isin(ex)].groupby("Date").agg(vote_amount =("out_bound_vote_amount","sum")).sort_index().reset_index()
    daily_token_spent["accum_vote_amount"] = daily_token_spent["vote_amount"].cumsum()

    daily_overview = pd.merge(left=daily_token_sold,right=daily_token_spent,how='left',on='Date')
    daily_overview['token_unspent'] = daily_overview['token_in_circulation'] - daily_overview['accum_vote_amount']

    daily_overview = daily_overview[['Date','token_in_circulation','accum_vote_amount','token_unspent']]

    return daily_overview


def save_to_parquet(df,df_name,path):
    temp_path = path.with_suffix(".tmp.parquet")
    df.to_parquet(temp_path, index=False)
    temp_path.replace(path)

    print(f"{df_name}: {len(df):,} rows")
    print(f"{df_name} saved to: {path}")
    print(f"{df_name} saved successfully.")
    print("#########################################")


def main() -> None:
    print("Starting creating daily_balance_sheet...")

    df_transfers = pd.read_parquet(RAW_PATH)
    print(f"Processed transfers: {len(df_transfers):,} rows")

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



    daily_balance_sheet = create_daily_balance_sheet(df_transfers)
    save_to_parquet(daily_balance_sheet,'daily balance sheet',DAILY_BALANCE_SHEET_PATH)
    del df_transfers

    df = create_top_voters_by_date(daily_balance_sheet)
    save_to_parquet(df,'top voters by date',TOP_VOTERS_BY_DATE_PATH)

    df = create_top_voters_all_time(daily_balance_sheet,ex)
    save_to_parquet(df,'top voters all time', TOP_VOTERS_ALL_TIME_PATH)

    df = create_daily_overview(daily_balance_sheet,official_accs,ex)
    save_to_parquet(df,'daily overview',DAILY_OVERVIEW_PATH)





if __name__ == "__main__":
    main()
