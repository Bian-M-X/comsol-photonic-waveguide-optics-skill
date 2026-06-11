from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_table(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"{path}:{lineno}: expected at least 4 numeric columns")
        try:
            freq_ghz = float(parts[0])
            lambda_um = float(parts[1])
            s11 = float(parts[2])
            t21 = float(parts[3])
            t21_db = float(parts[4]) if len(parts) >= 5 else float("nan")
        except ValueError as exc:
            raise ValueError(f"{path}:{lineno}: cannot parse numeric row: {line}") from exc
        rows.append(
            {
                "freq_GHz": freq_ghz,
                "lambda_nm": lambda_um * 1000.0,
                "S11": s11,
                "T21": t21,
                "T21_dB": t21_db,
                "S11_plus_T21": s11 + t21,
            }
        )
    if not rows:
        raise ValueError(f"no data rows parsed from {path}")
    return rows


def extrema(rows: list[dict[str, float]], mode: str, threshold: float) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for i in range(1, len(rows) - 1):
        prev_v = rows[i - 1]["T21"]
        cur_v = rows[i]["T21"]
        next_v = rows[i + 1]["T21"]
        if mode == "max" and cur_v >= prev_v and cur_v >= next_v and cur_v >= threshold:
            out.append(rows[i])
        if mode == "min" and cur_v <= prev_v and cur_v <= next_v:
            out.append(rows[i])
    return out


def summary_row(label: str, rows: list[dict[str, float]], peak_threshold: float) -> dict[str, str]:
    max_row = max(rows, key=lambda row: row["T21"])
    min_row = min(rows, key=lambda row: row["T21"])
    peaks = extrema(rows, "max", peak_threshold)
    valleys = extrema(rows, "min", peak_threshold)
    peak_spacings = [peaks[i + 1]["lambda_nm"] - peaks[i]["lambda_nm"] for i in range(len(peaks) - 1)]
    valley_spacings = [valleys[i + 1]["lambda_nm"] - valleys[i]["lambda_nm"] for i in range(len(valleys) - 1)]
    peak_values = [row["T21"] for row in peaks]
    weak_strong = min(peak_values) / max(peak_values) if peak_values else float("nan")
    return {
        "label": label,
        "row_count": str(len(rows)),
        "max_T21": f"{max_row['T21']:.12g}",
        "max_lambda_nm": f"{max_row['lambda_nm']:.5f}",
        "S11_at_max": f"{max_row['S11']:.12g}",
        "Ssum_at_max": f"{max_row['S11_plus_T21']:.12g}",
        "min_T21": f"{min_row['T21']:.12g}",
        "min_lambda_nm": f"{min_row['lambda_nm']:.5f}",
        "peak_lambdas_nm": "|".join(f"{row['lambda_nm']:.5f}" for row in peaks),
        "peak_T21s": "|".join(f"{row['T21']:.6f}" for row in peaks),
        "peak_spacings_nm": "|".join(f"{value:.5f}" for value in peak_spacings),
        "valley_lambdas_nm": "|".join(f"{row['lambda_nm']:.5f}" for row in valleys),
        "valley_spacings_nm": "|".join(f"{value:.5f}" for value in valley_spacings),
        "weak_strong_ratio": f"{weak_strong:.6g}",
    }


def write_csv(path: Path, rows: list[dict[str, str | float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a COMSOL frequency sweep table and summarize S-parameters.")
    parser.add_argument("table", type=Path)
    parser.add_argument("--label", default=None)
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--trace-csv", type=Path)
    parser.add_argument("--peak-threshold", type=float, default=0.02)
    args = parser.parse_args()

    rows = parse_table(args.table)
    label = args.label or args.table.stem
    summary = summary_row(label, rows, args.peak_threshold)
    write_csv(args.summary_csv, [summary])
    if args.trace_csv:
        write_csv(args.trace_csv, rows)  # type: ignore[arg-type]
    print(f"WROTE {args.summary_csv}")
    if args.trace_csv:
        print(f"WROTE {args.trace_csv}")
    print(summary)


if __name__ == "__main__":
    main()
