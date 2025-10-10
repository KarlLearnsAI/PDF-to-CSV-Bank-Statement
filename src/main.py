#!/usr/bin/env python3
import sys
import subprocess

def run_step(script_path: str):
    print(f"\n→ Running {script_path} …")
    res = subprocess.run([sys.executable, script_path], check=False)
    if res.returncode != 0:
        print(f"{script_path} failed with exit code {res.returncode}")
        sys.exit(res.returncode)

def main():
    steps = [
        "src/extract_transactions.py",
        "src/split_transactions.py",      # <-- Add the new splitting script here
        "src/preprocess_transactions.py",
        "src/analyze_transactions.py",
    ]
    for step in steps:
        run_step(step)
    print("\nAll steps completed successfully!")

if __name__ == "__main__":
    main()