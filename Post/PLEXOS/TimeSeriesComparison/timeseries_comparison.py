"""
Compare 2–4 time-series files and write results to an output directory.

Focused script — analysis and output generation only. No DataHub operations.
Chain with upload_to_datahub.py if you need to push results to DataHub.

Environment variables used:
    output_path      – default output directory if -o is not provided
    simulation_path  – used to resolve relative file paths
"""
import math
import os
import sys
import json
import time
import argparse
import warnings
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe in cloud containers
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")
sns.set_style("whitegrid")

OUTPUT_PATH = Path(os.environ.get("output_path", "./output"))
SIM_PATH    = Path(os.environ.get("simulation_path", "/simulation"))

# Alignment option → pandas join type
ALIGNMENT_MAP = {
    "intersection":    "inner",
    "union":           "outer",
    "use-first-file":  "left",
    "use-last-file":   "right",
}


def _json_safe(obj):
    """Recursively replace NaN/Inf floats with None for valid JSON serialization."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


# ── File loader ───────────────────────────────────────────────────────────────

class FileLoader:
    """Loads time-series files in CSV, Parquet, Excel or JSON format."""

    @staticmethod
    def load(path: str) -> Optional[pd.DataFrame]:
        p = Path(path)
        if not p.is_file():
            print(f"[ERROR] File not found: {path}")
            return None
        try:
            suffix = p.suffix.lower()
            if suffix == ".csv":
                try:
                    return pd.read_csv(path, encoding="utf-8")
                except UnicodeDecodeError:
                    print(f"[INFO]  UTF-8 failed, retrying with latin-1: {p.name}")
                    return pd.read_csv(path, encoding="latin-1")
            elif suffix == ".parquet":
                return pd.read_parquet(path)
            elif suffix in (".xlsx", ".xls"):
                return pd.read_excel(path)
            elif suffix == ".json":
                return pd.read_json(path)
            else:
                print(f"[ERROR] Unsupported format: {suffix}")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to load {p.name}: {e}")
            return None


# ── Datetime detector ─────────────────────────────────────────────────────────

class DatetimeDetector:
    """Detects and parses datetime from a DataFrame column or component columns."""

    COMMON_NAMES = {"timestamp", "datetime", "date", "time", "dt", "date_time"}
    COMPONENT_PATTERNS = {
        "year":   ["year", "yr", "yyyy"],
        "month":  ["month", "mon", "mm"],
        "day":    ["day", "dd"],
        "hour":   ["hour", "hr", "hh"],
        "minute": ["minute", "min"],
        "second": ["second", "sec", "ss"],
    }

    @classmethod
    def detect_column(cls, df: pd.DataFrame, label: str) -> Optional[str]:
        """Return the most likely single datetime column name."""
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
            if col.lower() in cls.COMMON_NAMES:
                return col
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() / len(df) > 0.7:
                    return col
            except Exception:
                continue
        return None

    @classmethod
    def detect_components(cls, df: pd.DataFrame) -> Optional[List[str]]:
        """Return list of datetime component column names if found (e.g. year/month/day)."""
        found = {}
        for comp, patterns in cls.COMPONENT_PATTERNS.items():
            for col in df.columns:
                if col.lower().strip() in patterns:
                    found[comp] = col
                    break
        return list(found.values()) if "year" in found else None

    @classmethod
    def parse_column(cls, df: pd.DataFrame, col: str, label: str) -> Optional[pd.DataFrame]:
        """Parse a datetime column into _parsed_datetime."""
        df = df.copy()
        df["_parsed_datetime"] = pd.to_datetime(df[col], format="mixed", errors="coerce")
        valid = df["_parsed_datetime"].notna().sum() / len(df)
        if valid < 0.5:
            print(f"[ERROR] {label}: only {valid*100:.1f}% of '{col}' parsed as datetime")
            return None
        print(f"[OK]    {label}: parsed datetime column '{col}' ({valid*100:.1f}% valid)")
        return df

    @classmethod
    def parse_components(cls, df: pd.DataFrame, components: List[str], label: str) -> Optional[pd.DataFrame]:
        """Build _parsed_datetime from component columns (year, month, day, …)."""
        df = df.copy()
        comp_map: Dict[str, int] = {}
        for col in components:
            col_lower = col.lower().strip()
            for comp, patterns in cls.COMPONENT_PATTERNS.items():
                if col_lower in patterns:
                    comp_map[comp] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                    break
        dt_dict = {
            "year":   comp_map.get("year",   1970),
            "month":  comp_map.get("month",  1),
            "day":    comp_map.get("day",    1),
            "hour":   comp_map.get("hour",   0),
            "minute": comp_map.get("minute", 0),
            "second": comp_map.get("second", 0),
        }
        df["_parsed_datetime"] = pd.to_datetime(dt_dict, errors="coerce")
        valid = df["_parsed_datetime"].notna().sum() / len(df)
        print(f"[OK]    {label}: built datetime from components {components} ({valid*100:.1f}% valid)")
        return df


# ── Main comparator ───────────────────────────────────────────────────────────

class TimeSeriesComparator:
    """
    Loads, aligns and compares 2–4 time-series files.

    Args:
        file_args:        List of 'filepath[:label]' strings.
        output_dir:       Root directory for results.
        prefix:           Optional folder-name prefix.
        join_type:        pandas join type for alignment.
        missing_strategy: How to handle NaNs after alignment.
        drop_zero_diff:   Drop rows where all differences are zero/NaN.
        datetime_alias:   Rename _parsed_datetime in the output Parquet.
    """

    def __init__(
        self,
        file_args: List[str],
        output_dir: Path,
        prefix: Optional[str] = None,
        join_type: str = "outer",
        missing_strategy: str = "none",
        drop_zero_diff: bool = True,
        datetime_alias: Optional[str] = None,
    ):
        if len(file_args) < 2:
            raise ValueError("At least 2 files are required.")
        if len(file_args) > 4:
            print(f"[WARN]  {len(file_args)} files provided — only first 4 used")
            file_args = file_args[:4]

        self.entries: List[Tuple[str, str]] = []
        for arg in file_args:
            arg_str = arg.strip("'\"")
            raw_path_str = arg_str
            label: Optional[str] = None

            # Parse "filepath[:label]" safely for Windows drive paths like "C:\foo\bar.csv"
            if ":" in arg_str:
                first_colon = arg_str.find(":")
                colon_count = arg_str.count(":")
                # A single colon at position 1 followed by \ or / is a Windows drive letter — not a label separator
                is_drive_only = (colon_count == 1 and first_colon == 1 and len(arg_str) > 2 and arg_str[2] in ("\\", "/"))
                if not is_drive_only:
                    path_part, label_part = arg_str.rsplit(":", 1)
                    raw_path_str = path_part.strip()
                    label_part = label_part.strip().strip("'\"")
                    if label_part:
                        label = label_part

            raw_path = unquote(raw_path_str.strip())
            if label is None:
                label = Path(raw_path).stem
            path     = Path(raw_path) if Path(raw_path).is_absolute() else SIM_PATH / raw_path
            self.entries.append((str(path), label))

        self.output_root      = output_dir
        self.prefix           = prefix
        self.join_type        = join_type
        self.missing_strategy = missing_strategy
        self.drop_zero_diff   = drop_zero_diff
        self.datetime_alias   = datetime_alias

        self.df_list: List[Tuple[pd.DataFrame, str]] = []
        self.prepared: List[pd.DataFrame]            = []
        self.aligned: Optional[pd.DataFrame]         = None
        self.output_dir: Optional[Path]              = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detect_value_columns(self, df: pd.DataFrame, exclude: set) -> List[str]:
        exclude.add("_parsed_datetime")
        return [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]

    def _validate_join_missing(self) -> None:
        """Auto-fix incompatible outer+drop combination."""
        if self.join_type != "inner" and self.missing_strategy == "drop":
            print(f"[WARN]  join='{self.join_type}' + missing='drop' would destroy data.")
            print(f"[AUTO]  Switching missing strategy to 'interpolate'.")
            self.missing_strategy = "interpolate"

    # ── Step 1: Load ──────────────────────────────────────────────────────────

    def _load(self) -> bool:
        t = time.perf_counter()
        print("\n[1/6] Loading files...")
        for path, label in self.entries:
            df = FileLoader.load(path)
            if df is None:
                print(f"[SKIP]  {label} ({path}) — skipped")
                continue
            print(f"       {label}: {len(df):,} rows × {len(df.columns)} cols")
            self.df_list.append((df, label))
        if len(self.df_list) < 2:
            print(f"[ERROR] Need ≥2 files, only {len(self.df_list)} loaded.")
            return False
        print(f"⏱  {time.perf_counter()-t:.2f}s")
        return True

    # ── Step 2: Parse datetime ────────────────────────────────────────────────

    def _parse_datetime(self) -> bool:
        t = time.perf_counter()
        print("\n[2/6] Parsing datetime columns...")
        for df, label in self.df_list:
            components = DatetimeDetector.detect_components(df)
            if components:
                df = DatetimeDetector.parse_components(df, components, label)
                exclude = set(components)
            else:
                col = DatetimeDetector.detect_column(df, label)
                if col is None:
                    print(f"[ERROR] {label}: cannot detect datetime column")
                    return False
                df = DatetimeDetector.parse_column(df, col, label)
                exclude = {col}
            if df is None:
                return False
            df = df.dropna(subset=["_parsed_datetime"])
            value_cols = self._detect_value_columns(df, exclude)
            if not value_cols:
                print(f"[ERROR] {label}: no numeric value columns found")
                return False
            print(f"       {label}: value columns = {value_cols}")
            series = (
                df.set_index("_parsed_datetime")[value_cols]
                  .add_prefix(f"{label}_")
            )
            self.prepared.append(series)
        print(f"⏱  {time.perf_counter()-t:.2f}s")
        return True

    # ── Step 3: Align ─────────────────────────────────────────────────────────

    def _align(self) -> bool:
        t = time.perf_counter()
        print(f"\n[3/6] Aligning ({self.join_type} join)...")
        self._validate_join_missing()
        aligned = self.prepared[0]
        for s in self.prepared[1:]:
            aligned = aligned.join(s, how=self.join_type)
        print(f"       Aligned rows: {len(aligned):,}  |  columns: {list(aligned.columns)}")
        self.aligned = aligned
        print(f"⏱  {time.perf_counter()-t:.2f}s")
        return True

    # ── Step 4: Handle missing ────────────────────────────────────────────────

    def _handle_missing(self) -> bool:
        t = time.perf_counter()
        missing_before = int(self.aligned.isna().sum().sum())
        print(f"\n[4/6] Missing values: {missing_before} | strategy: {self.missing_strategy}")
        if missing_before == 0 or self.missing_strategy == "none":
            print(f"⏱  {time.perf_counter()-t:.2f}s")
            return True
        n_before = len(self.aligned)
        if self.missing_strategy == "drop":
            self.aligned = self.aligned.dropna()
        elif self.missing_strategy == "forward_fill":
            self.aligned = self.aligned.ffill().dropna()
        elif self.missing_strategy == "backward_fill":
            self.aligned = self.aligned.bfill().dropna()
        elif self.missing_strategy == "interpolate":
            num_cols = self.aligned.select_dtypes(include=[np.number]).columns
            self.aligned[num_cols] = self.aligned[num_cols].interpolate(method="linear")
            self.aligned = self.aligned.dropna()
        removed = n_before - len(self.aligned)
        print(f"       Rows removed: {removed}  |  Remaining: {len(self.aligned):,}")
        if len(self.aligned) == 0:
            print("[ERROR] No rows remain after missing-value handling.")
            return False
        print(f"⏱  {time.perf_counter()-t:.2f}s")
        return True

    # ── Step 5: Detect gaps & anomalies ──────────────────────────────────────

    def _detect_gaps(self) -> None:
        diffs = self.aligned.index.to_series().diff()
        valid = diffs[diffs.notna() & (diffs > pd.Timedelta(0))]
        if len(valid) == 0:
            return
        try:
            mode_diff = valid.dt.round("1s").mode()[0]
        except Exception:
            mode_diff = valid.median()
        gaps = diffs[diffs > mode_diff * 3]
        if len(gaps):
            print(f"[WARN]  {len(gaps)} gap(s) detected (threshold: {mode_diff * 3})")

    def _detect_anomalies(self, series: pd.Series) -> int:
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        return int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())

    # ── Step 6: Compare & output ──────────────────────────────────────────────

    def _calculate_metrics(self, a: pd.Series, b: pd.Series) -> dict:
        mask  = a.notna() & b.notna()
        if mask.sum() == 0:
            return {"note": "no overlapping data", "valid_points": 0}
        ya, yb   = a[mask].values, b[mask].values
        diff     = ya - yb
        mae      = float(np.mean(np.abs(diff)))
        rmse     = float(np.sqrt(np.mean(diff ** 2)))
        corr     = float(np.corrcoef(ya, yb)[0, 1]) if len(ya) > 1 else float("nan")
        mean_bias = float(np.mean(yb - ya))
        ss_res   = np.sum(diff ** 2)
        ss_tot   = np.sum((ya - np.mean(ya)) ** 2)
        r2       = float(1 - ss_res / ss_tot) if ss_tot != 0 else float("nan")
        nz       = np.abs(ya) > 1e-9
        mape     = float(np.mean(np.abs(diff[nz] / ya[nz])) * 100) if nz.sum() > 0 else float("nan")
        return {
            "valid_points": int(mask.sum()),
            "mae":          round(mae,       4),
            "rmse":         round(rmse,      4),
            "correlation":  round(corr,      4),
            "r_squared":    round(r2,        4),
            "mape_pct":     round(mape,      4),
            "max_error":    round(float(np.max(np.abs(diff))), 4),
            "mean_bias":    round(mean_bias, 4),
        }

    def _save_plot(self, col_a: str, col_b: str, metrics: dict) -> None:
        try:
            fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
            idx = self.aligned.index

            # Panel 1 — overlay
            valid_mask = self.aligned[col_a].notna() & self.aligned[col_b].notna()
            axes[0].plot(idx, self.aligned[col_a], label=col_a, linewidth=1)
            axes[0].plot(idx, self.aligned[col_b], label=col_b, linewidth=1, linestyle="--")
            if (~valid_mask).sum():
                for region_idx in idx[~valid_mask]:
                    axes[0].axvline(region_idx, color="grey", alpha=0.1, linewidth=0.5)
            axes[0].set_title(f"Overlay: {col_a} vs {col_b}")
            axes[0].legend(); axes[0].grid(True, alpha=0.3)

            # Panel 2 — difference
            diff = self.aligned[col_b] - self.aligned[col_a]
            axes[1].plot(idx[valid_mask], diff[valid_mask], color="red", linewidth=0.8)
            axes[1].axhline(0, color="black", linewidth=0.5, linestyle="--")
            axes[1].fill_between(idx[valid_mask], 0, diff[valid_mask],
                                 where=(diff[valid_mask] >= 0), color="green", alpha=0.3)
            axes[1].fill_between(idx[valid_mask], 0, diff[valid_mask],
                                 where=(diff[valid_mask] < 0),  color="red",   alpha=0.3)
            axes[1].set_title(f"Difference (B − A)")
            axes[1].grid(True, alpha=0.3)

            # Panel 3 — scatter
            va = self.aligned.loc[valid_mask, col_a]
            vb = self.aligned.loc[valid_mask, col_b]
            axes[2].scatter(va, vb, alpha=0.4, s=15, color="purple")
            if len(va) > 0:
                lo, hi = min(va.min(), vb.min()), max(va.max(), vb.max())
                axes[2].plot([lo, hi], [lo, hi], "r--", linewidth=1.5, label="Perfect")
                if len(va) > 1:
                    try:
                        z = np.polyfit(va, vb, 1)
                        axes[2].plot(va, np.poly1d(z)(va), "b-", linewidth=1.2,
                                     label=f"Fit: y={z[0]:.2f}x+{z[1]:.2f}")
                    except Exception:
                        pass
            corr_str = f"{metrics.get('correlation', float('nan')):.4f}"
            axes[2].set_title(f"Scatter  |  Corr={corr_str}  |  R²={metrics.get('r_squared', 'n/a')}")
            axes[2].set_xlabel(col_a); axes[2].set_ylabel(col_b)
            axes[2].legend(); axes[2].grid(True, alpha=0.3)

            plt.tight_layout()
            safe = (
                f"{col_a}_vs_{col_b}"
                .replace("/", "_").replace("\\", "_").replace(":", "_")
                .replace("*", "_").replace("?", "_").replace('"', "_")
                .replace("<", "_").replace(">", "_").replace("|", "_")
                .replace(" ", "_")
            )
            out  = self.output_dir / f"{safe}.png"
            plt.savefig(out, dpi=100, bbox_inches="tight")
            plt.close(fig)
            print(f"[OK]    Plot saved: {out.name}")
        except Exception as e:
            print(f"[WARN]  Plot failed for {col_a} vs {col_b}: {e}")
            plt.close("all")

    def _compare(self) -> List[dict]:
        t = time.perf_counter()
        print("\n[6/6] Computing statistics and plots...")
        cols       = self.aligned.columns.tolist()
        all_stats  = []
        diff_cols  = []

        for col_a, col_b in combinations(cols, 2):
            metrics = self._calculate_metrics(self.aligned[col_a], self.aligned[col_b])
            all_stats.append({"pair": f"{col_a} vs {col_b}", **metrics})
            anom_a = self._detect_anomalies(self.aligned[col_a].dropna())
            anom_b = self._detect_anomalies(self.aligned[col_b].dropna())
            print(
                f"       {col_a} vs {col_b}  |  "
                f"MAE={metrics.get('mae','n/a')}  RMSE={metrics.get('rmse','n/a')}  "
                f"Corr={metrics.get('correlation','n/a')}  R²={metrics.get('r_squared','n/a')}  "
                f"Anomalies=({anom_a},{anom_b})"
            )
            self._save_plot(col_a, col_b, metrics)

            # Difference column for output Parquet
            dc = f"Diff_{col_a}_vs_{col_b}"
            self.aligned[dc] = self.aligned[col_b] - self.aligned[col_a]
            diff_cols.append(dc)

        # Optional: drop rows where all diffs are zero/NaN
        if self.drop_zero_diff and diff_cols:
            before = len(self.aligned)
            mask = ~(
                ((self.aligned[diff_cols] == 0) | self.aligned[diff_cols].isna()).all(axis=1)
            )
            self.aligned = self.aligned[mask]
            print(f"       Dropped {before - len(self.aligned)} zero-diff rows  |  Remaining: {len(self.aligned):,}")

        print(f"⏱  {time.perf_counter()-t:.2f}s")
        return all_stats

    # ── Public run method ─────────────────────────────────────────────────────

    def run(self) -> bool:
        start = time.perf_counter()
        print("\n" + "=" * 70)
        print("TIME SERIES COMPARISON".center(70))
        print("=" * 70)

        # Create output directory
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder      = f"{self.prefix}_Analysis_{ts}" if self.prefix else f"Analysis_{ts}"
        self.output_dir = self.output_root / folder
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[PATH] Output directory: {self.output_dir}")

        if not self._load():          return False
        if not self._parse_datetime(): return False
        if not self._align():         return False
        if not self._handle_missing(): return False

        print("\n[5/6] Detecting gaps and anomalies...")
        t = time.perf_counter()
        self._detect_gaps()
        print(f"⏱  {time.perf_counter()-t:.2f}s")

        all_stats = self._compare()

        # Save aligned Parquet
        output_df = self.aligned.reset_index()
        if self.datetime_alias:
            output_df = output_df.rename(columns={"_parsed_datetime": self.datetime_alias})
        parquet_path = self.output_dir / "aligned_data.parquet"
        output_df.to_parquet(parquet_path, index=False)
        print(f"\n[OK]   Aligned data saved: {parquet_path.name}  ({len(output_df):,} rows)")

        # Save JSON summary
        summary = {
            "generated_at": datetime.now().isoformat(),
            "files":        [{"path": p, "label": lbl} for p, lbl in self.entries],
            "join_type":    self.join_type,
            "missing_strategy": self.missing_strategy,
            "row_count":    len(output_df),
            "statistics":   all_stats,
        }
        summary_path = self.output_dir / "analysis_summary.json"
        summary_path.write_text(json.dumps(_json_safe(summary), indent=2))
        print(f"[OK]   Summary saved: {summary_path.name}")

        print(f"\n{'='*70}")
        print(f"DONE  —  total time: {time.perf_counter()-start:.2f}s".center(70))
        print(f"Results: {self.output_dir}")
        print("=" * 70 + "\n")
        return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare 2–4 time-series files and write results to an output directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n\n"
            "  Basic — two local files:\n"
            "    python3 timeseries_comparison.py \\\n"
            "      -f baseline.csv:Baseline -f result.csv:Simulation \\\n"
            "      -o C:/Output\n\n"
            "  Full options:\n"
            "    python3 timeseries_comparison.py \\\n"
            "      -f baseline.csv:Baseline -f result.parquet:Run2 \\\n"
            "      -o C:/Output -p Study3 \\\n"
            "      -j intersection -m interpolate -ta Timestamp -k\n\n"
            "  Chain — compare then upload results:\n"
            "    python3 timeseries_comparison.py -f f1.csv -f f2.csv -o output_path\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Analysis"
        ),
    )
    parser.add_argument(
        "-f", "--file", dest="files", action="append", required=True,
        metavar="PATH[:LABEL]",
        help="File to compare. Repeat 2–4 times. Optionally append :Label.",
    )
    parser.add_argument(
        "-o", "--output-path", default=None,
        help=(
            "Directory to write results into. "
            "Defaults to the output_path environment variable. "
            "Pass 'output_path' to explicitly use the env var."
        ),
    )
    parser.add_argument(
        "-p", "--prefix", default=None,
        help="Prefix for the timestamped output folder (default: Analysis_<ts>).",
    )
    parser.add_argument(
        "-j", "--alignment", default="union",
        choices=list(ALIGNMENT_MAP.keys()),
        help="Timestamp alignment method (default: union).",
    )
    parser.add_argument(
        "-m", "--handle-missing", default="none", dest="handle_missing",
        choices=["none", "drop", "forward_fill", "backward_fill", "interpolate"],
        help="Missing value strategy after alignment (default: none).",
    )
    parser.add_argument(
        "-ta", "--timestamp-alias", default=None, dest="timestamp_alias",
        help="Rename _parsed_datetime to this name in the output Parquet.",
    )
    parser.add_argument(
        "-k", "--keep-zero-diff", action="store_true", default=False,
        help="Keep rows where all differences are zero (default: drop them).",
    )
    args = parser.parse_args()

    if len(args.files) < 2:
        parser.error("At least 2 -f/--file arguments are required.")

    # Resolve output path — treat magic tokens the same as the env var
    _token_map = {
        None:            OUTPUT_PATH,
        "output_path":   OUTPUT_PATH,
        "simulation_path": SIM_PATH,
    }
    if args.output_path in _token_map:
        out = _token_map[args.output_path]
    else:
        out = Path(args.output_path)

    comparator = TimeSeriesComparator(
        file_args        = args.files,
        output_dir       = out,
        prefix           = args.prefix,
        join_type        = ALIGNMENT_MAP[args.alignment],
        missing_strategy = args.handle_missing,
        drop_zero_diff   = not args.keep_zero_diff,
        datetime_alias   = args.timestamp_alias,
    )
    return 0 if comparator.run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
