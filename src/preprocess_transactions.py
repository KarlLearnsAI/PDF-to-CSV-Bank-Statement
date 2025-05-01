import pandas as pd
from datetime import datetime

MONTH_MAP = {
    "Jan": "Jan", "Feb": "Feb", "März": "Mar", "Mrz": "Mar",
    "Apr": "Apr", "Mai": "May", "Jun": "Jun", "Jul": "Jul",
    "Aug": "Aug", "Sept": "Sep", "Okt": "Oct", "Nov": "Nov", "Dez": "Dec"
}

def parse_date(s: str) -> pd.Timestamp:
    parts = s.split()
    if len(parts) != 3:
        raise ValueError(f"Unexpected date format: {s!r}")
    day, mon, year = parts
    mon_key = mon.rstrip(".")
    if mon_key not in MONTH_MAP:
        raise ValueError(f"Unknown month {mon_key!r}")
    mon_abbrev = MONTH_MAP[mon_key]
    dt_str = f"{day} {mon_abbrev} {year}"
    return datetime.strptime(dt_str, "%d %b %Y")

def main():
    csv_in = "data/raw_transactions.csv"
    df = pd.read_csv(csv_in)

    df["Date"] = df["Date"].apply(parse_date)
    print(f"Successfully preprocessed and saved {len(df)} transactions")
    out_csv = "data/processed_transactions.csv"
    df.to_csv(out_csv, index=False)

if __name__ == "__main__":
    main()