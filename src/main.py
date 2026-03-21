#!/usr/bin/env python3
import sys
import subprocess
import pdfplumber


def detect_bank(pdf_path: str) -> str:
    """Detect bank type from first page of PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                if "COMMERZBANK" in text.upper() or "Kontoauszug" in text:
                    return "commerzbank"
    except Exception:
        pass
    return "trade_republic"


def run_step(script_path: str, args: list = None):
    cmd = [sys.executable, script_path] + (args or [])
    print(f"\n-> Running {script_path} ...")
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"{script_path} failed with exit code {res.returncode}")
        sys.exit(res.returncode)


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/statement.pdf"
    bank = detect_bank(pdf_path)
    print(f"Detected bank: {bank}")

    if bank == "commerzbank":
        run_step("src/extract_commerzbank.py", [pdf_path])
        run_step("src/analyze_transactions.py")
    else:
        run_step("src/extract_transactions.py", [pdf_path])
        run_step("src/split_transactions.py")
        run_step("src/preprocess_transactions.py")
        run_step("src/analyze_transactions.py")

    print("\nAll steps completed successfully!")


if __name__ == "__main__":
    main()
