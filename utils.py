import requests
import pandas as pd
import time


def clean_and_deduplicate(dataframe, key_column):
    """
    Removes duplicate entries based on a unique key column (e.g., 'Tx Hash' or 'Address').
    """
    if dataframe is None or dataframe.empty:
        return pd.DataFrame(columns=['Tx Hash', 'Block Hash', 'Timestamp', 'From', 'To', 'Value', 'Raw Value', 'Type'])
    initial_count = len(dataframe)
    deduped_df = dataframe.drop_duplicates(subset=[key_column], keep='first').reset_index(drop=True)
    print(f"Removed {initial_count - len(deduped_df)} duplicate rows. Total rows now: {len(deduped_df)}.")
    return deduped_df

def fetch_incremental_transfers(existing_df_transfers=None, token_address='0x2f5c60bdE7A5ebD2b116BB03cB5232fA1Ea55F1C', safety_overlap=20):
    """
    Fetches new token transfers incrementally or performs a full fetch from scratch if no existing dataframe is provided.
    Uses a safety_overlap depth check during incremental runs to prevent data loss.
    """
    base_transfers_url = f'https://scan.tokenx.finance/api/v2/tokens/{token_address}/transfers'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json'
    }

    is_from_scratch = existing_df_transfers is None or existing_df_transfers.empty

    if is_from_scratch:
        print("No pre-existing transfers detected. STARTING TRANSFER SCRAPING FROM SCRATCH...")
        existing_df_transfers = pd.DataFrame(columns=['Tx Hash', 'Block Hash', 'Timestamp','Method','From', 'To', 'Value', 'Raw Value', 'Type'])
    else:
        print(f"Incremental sync detected. Initializing lookback buffer check with safety overlap depth of {safety_overlap}...")

    existing_hashes = set(existing_df_transfers['Tx Hash'].values) if 'Tx Hash' in existing_df_transfers.columns else set()
    new_transfers = []
    params = {}
    page_count = 1
    stop_reached = False
    consecutive_matched_count = 0

    while not stop_reached:
        print(f"Fetching page {page_count}...")
        response = requests.get(base_transfers_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])

        if not items:
            print("No more items returned by the API. Stopping.")
            break

        if page_count == 1 and items:
            token_info = items[0].get('token', {})
            decimals = int(token_info.get('decimals', 18))

        for item in items:
            tx_hash = item.get('tx_hash')

            # Only apply early stopping watermark if we are not building from scratch
            if not is_from_scratch:
                  if tx_hash in existing_hashes:
                      consecutive_matched_count += 1

                      if consecutive_matched_count >= safety_overlap:
                            print(f"Encountered {consecutive_matched_count} consecutive existing transactions. Stopping incremental fetch.")
                            stop_reached = True
                            break
                      else:
                          continue

            else:
                consecutive_matched_count = 0



            from_addr = item.get('from', {}).get('hash')
            to_addr = item.get('to', {}).get('hash')
            raw_value = float(item.get('total', {}).get('value', 0) or item.get('value', 0))
            formatted_value = raw_value / (10 ** decimals)


            new_transfers.append({
                'Tx Hash': tx_hash,
                'Block Hash': item.get('block_hash'),
                'Timestamp': item.get('timestamp'),
                'Method' : item.get('method'),
                'From': from_addr,
                'To': to_addr,
                'Value': formatted_value,
                'Raw Value': raw_value,
                'Type': item.get('type')
            })

        if stop_reached:
            break

        next_page_params = data.get('next_page_params')
        if next_page_params:
            params = next_page_params
            page_count += 1
            time.sleep(0.5)
        else:
            print("Reached the last page of transfers.")
            break

    if new_transfers:
        new_df = pd.DataFrame(new_transfers)
        print(f"Successfully retrieved {len(new_df)} new transfers across {page_count} pages.")
        combined_df = pd.concat([new_df, existing_df_transfers], ignore_index=True)
        return  clean_and_deduplicate(combined_df, 'Tx Hash')
    else:
        print("No new transfers found. System is up to date.")
        return existing_df_transfers