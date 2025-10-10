#!/usr/bin/env python3
import pandas as pd
import re

def split_raw_transactions(input_csv: str, output_csv: str):
    """
    Reads the raw, merged CSV and correctly splits each row into multiple
    transaction lines. This script focuses *only* on splitting and does not
    validate or filter data, ensuring every transaction is preserved.
    """
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"Input file not found: {input_csv}. Cannot split.")
        pd.DataFrame(columns=['TransactionText']).to_csv(output_csv, index=False)
        return
    
    if df.empty:
        print("Input file is empty. Nothing to split.")
        pd.DataFrame(columns=['TransactionText']).to_csv(output_csv, index=False)
        return

    all_split_lines = []
    
    # This regex is the key. It looks for the start of a transaction, which is
    # a date pattern like "13 Sept.". The `(?=...)` part is a "positive lookahead",
    # which allows `re.split` to break the string *before* this pattern,
    # keeping the delimiter with the text that follows it.
    months_str = r"(?:Jan|Feb|März|Mrz|Apr|Mai|Jun|Jul|Aug|Sept|Okt|Nov|Dez)"
    split_pattern = re.compile(rf"(?=\b\d{{1,2}}\s+{months_str}\.?)")

    for index, row in df.iterrows():
        # Get the year from the original 'Date' column to re-apply it later.
        original_date_str = str(row.get('Date', ''))
        year_match = re.search(r'(\d{4})', original_date_str)
        year = year_match.group(1) if year_match else ''
        
        # Combine all columns of the row into a single string.
        full_text_block = " ".join(str(c) for c in row.dropna().values)
        
        # Split the block into a list of strings using the date pattern.
        split_transactions = split_pattern.split(full_text_block)
        
        for text_part in split_transactions:
            text_part = " ".join(text_part.split()).strip()
            
            if not text_part:
                continue

            # Re-attach the year to each split part to form a complete date.
            # This handles cases where the year is not already in the split text.
            if year and not re.search(r'\b\d{4}\b', text_part):
                # Find the month and insert the year after it.
                text_part = re.sub(rf"({months_str}\.?)", rf"\1 {year}", text_part, 1)

            all_split_lines.append({"TransactionText": text_part})

    # Create a new DataFrame with a single column for the split transaction text.
    final_df = pd.DataFrame(all_split_lines)
    final_df = final_df[final_df['TransactionText'].str.contains('€', na=False)] # Final cleanup of non-transactional text
    final_df.to_csv(output_csv, index=False)
    print(f"Successfully split {len(df)} raw lines into {len(final_df)} transaction lines in {output_csv}")

def main():
    split_raw_transactions(
        input_csv="data/raw_transactions.csv",
        output_csv="data/splitted_raw_transactions.csv"
    )

if __name__ == "__main__":
    main()