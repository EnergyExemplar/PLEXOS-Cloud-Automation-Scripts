"""
Bid adder generation — piecewise-linear markup from net-load curves.

Focused script: Downloads net-load data, calculates normalized net-load
curves, applies piecewise-linear interpolation with configurable bands
and monthly seasonal weights, then writes the modified bid adder back
into the model's timeseries.zip.

Environment variables used:
    cloud_cli_path   – Path to the Cloud CLI executable
    simulation_path  – Root path for study files (default: /simulation)
    output_path      – Modified bid adder is copied here for downstream tasks
"""

import os
import sys
import shutil
import traceback
import pandas as pd
from pathlib import Path
import argparse
import numpy as np
import zipfile
from eecloud.cloudsdk import CloudSDK, SDKBase

# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — These defaults apply when the corresponding CLI flag is omitted.
# ═══════════════════════════════════════════════════════════════════════════════

# Piecewise-linear band breakpoints as "x:y" pairs (net-load-norm : markup)
# Example: "0.0:0,0.6:0,0.8:125,0.9:625,1.0:1125"
BANDS = "0.0:0,0.6:0,0.8:25,0.9:125,1.0:225"

# Monthly seasonal weight multipliers as "month:weight" pairs
# Example: "1:0.50,2:0.55,3:1.30,..."
SEASONAL_WEIGHTS = "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05"

# Calibration iteration counter
COUNTER = 0

# Use local input files instead of downloading from DataHub
IS_LOCAL_MODE = False

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════

OUTPUT_PATH = Path(os.environ.get("output_path", "/output"))


# ---------------- DOWNLOAD INPUTS ----------------
def download_inputs(netload_file_path, local_mode=False):
    """Download input files from DataHub.

    Args:
        netload_file_path: DataHub remote path to the net-load Excel file.
        local_mode: If True, skip download and use local files.

    Returns:
        Path to the downloaded Netload file, or None in local mode / if SDK
        did not report a LocalFilePath.
    """
    if local_mode:
        print("[INFO] Local mode enabled — using files from inputs/ folder")
        return None

    try:
        cloud_cli_path = os.environ["cloud_cli_path"]
    except KeyError:
        print("[FAIL] Missing required environment variable: cloud_cli_path")
        sys.exit(1)

    pxc = CloudSDK(cli_path=cloud_cli_path)

    print("[INFO] Downloading input files from DataHub...")

    response = pxc.datahub.download(
        remote_glob_patterns=[
            netload_file_path
        ],
        output_directory=str(OUTPUT_PATH),
        print_message=True
    )

    data = SDKBase.get_response_data(response)
    netload_path = None
    if data is not None and hasattr(data, "DatahubResourceResults"):
        for result in data.DatahubResourceResults:
            if not getattr(result, "Success", False):
                reason = getattr(result, "FailureReason", "unknown")
                if reason == "File is identical to the remote file":
                    local_file = getattr(result, "LocalFilePath", None)
                    if local_file:
                        netload_path = Path(local_file)
                else:
                    print(f"[FAIL] DataHub download failed: {reason}")
                    sys.exit(1)
            else:
                local_file = getattr(result, "LocalFilePath", None)
                if local_file:
                    netload_path = Path(local_file)
    return netload_path

# ---------------- ARGUMENTS ----------------
def parse_bands(value: str):
    value = value.strip("\"'")
    try:
        bands = [(float(x.split(":")[0]), float(x.split(":")[1])) for x in value.split(",")]
    except (ValueError, IndexError) as e:
        raise argparse.ArgumentTypeError(
            f"Invalid bands format: {value!r}. Expected comma-separated x:y pairs (e.g. '0.0:0,0.8:25,1.0:225'): {e}"
        )
    bands.sort(key=lambda band: band[0])

    xs = [x for x, _ in bands]
    if len(xs) != len(set(xs)):
        raise argparse.ArgumentTypeError(
            "Band breakpoints must have unique x-values."
        )

    return bands

def parse_seasonal_weights(value: str):
    value = value.strip("\"'")
    try:
        weights = {int(x.split(":")[0]): float(x.split(":")[1]) for x in value.split(",")}
    except (ValueError, IndexError) as e:
        raise argparse.ArgumentTypeError(
            f"Invalid seasonal weights format: {value!r}. Expected comma-separated month:weight pairs (e.g. '1:0.50,2:0.55,...,12:1.05'): {e}"
        )
    for month in weights:
        if month < 1 or month > 12:
            raise argparse.ArgumentTypeError(
                f"Month {month} is out of range (must be 1–12)."
            )
    return weights

# ---------------- CALC ----------------
def piecewise_linear(x, bands):
    xs, ys = zip(*bands)
    return np.interp(x, xs, ys)


# Canonical band values per counter — ensures monotonically increasing bid adders.
# Intentionally duplicated from get_next_bands() in calibration_evaluation.py:
# scripts must be self-contained (no cross-script imports), so this lookup is
# replicated here. Keep both tables in sync when changing band values.
BANDS_BY_COUNTER = {
    0: [(0.0, 0.0), (0.6, 0.0), (0.8, 25.0), (0.9, 125.0), (1.0, 225.0)],    # 1× baseline
    1: [(0.0, 0.0), (0.6, 0.0), (0.8, 75.0), (0.9, 375.0), (1.0, 675.0)],    # 3×
    2: [(0.0, 0.0), (0.6, 0.0), (0.8, 125.0), (0.9, 625.0), (1.0, 1125.0)],  # 5×
}


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("--bands", type=parse_bands, default=parse_bands(BANDS))
    parser.add_argument("--seasonal-weights", type=parse_seasonal_weights, default=parse_seasonal_weights(SEASONAL_WEIGHTS))
    parser.add_argument("--counter", type=int, default=COUNTER)
    parser.add_argument("--bidadder-filename", type=str, required=True)
    parser.add_argument("--netload-file", nargs='+', required=True,
                        help="DataHub path to the net-load Excel file, "
                             "e.g. calibration/inputs/Netload_2027.xlsx")
    parser.add_argument("--timeseries-subdir", nargs='+', default=["TimeSeries/Bid Adders"],
                        help="Subdirectory under simulation_path where the bid adder file lives "
                             "and the zip entry prefix (default: TimeSeries/Bid Adders)")
    parser.add_argument("--local-mode", action="store_true", default=IS_LOCAL_MODE, help="Use local input files from inputs/ folder instead of DataHub")

    args = parser.parse_args()

    # Join space-separated tokens (handles paths with spaces without quotes)
    args.netload_file = ' '.join(args.netload_file)
    args.timeseries_subdir = ' '.join(args.timeseries_subdir)

    # Override bands from counter lookup to guarantee monotonic progression
    if args.counter in BANDS_BY_COUNTER:
        canonical_bands = BANDS_BY_COUNTER[args.counter]
        if args.bands != canonical_bands:
            print(f"[WARN] --bands argument does not match canonical bands for counter {args.counter}")
            print(f"[WARN]   Payload bands: {args.bands}")
            print(f"[WARN]   Canonical bands: {canonical_bands}")
            print(f"[WARN]   Using canonical bands to ensure monotonic progression")
        args.bands = canonical_bands

    # ---------- PRE-SCRIPT DIAGNOSTIC LOGGING ----------
    print(f"\n[DEBUG] ========== PRE-SCRIPT EXECUTION START ==========")
    print(f"[DEBUG] Counter: {args.counter}")
    print(f"[DEBUG] Bidadder filename: {args.bidadder_filename}")
    print(f"[DEBUG] Bands: {args.bands}")
    print(f"[DEBUG] Seasonal weights: {args.seasonal_weights}")
    print(f"[DEBUG] Netload file: {args.netload_file}")
    print(f"[DEBUG] Timeseries subdir: {args.timeseries_subdir}")
    print(f"[DEBUG] Local mode: {args.local_mode}")
    print(f"[DEBUG] ==============================================\n")

    # ---------------- INIT ----------------
    netload_path = download_inputs(args.netload_file, local_mode=args.local_mode)

    bands = args.bands
    seasonal_weights = args.seasonal_weights
    counter = args.counter

    print(f"[INFO] Counter: {counter}")
    print(f"[INFO] Bands: {bands}")
    if args.local_mode:
        print("[INFO] Local mode: TRUE")

    # ---------------- PATH ----------------
    simulation_path = os.environ.get("simulation_path", "/simulation")
    # Always resolve the existing bid adder relative to the study's
    # timeseries subdirectory so --bidadder-filename behaves
    # consistently in both local and cloud modes.
    output_path = Path(simulation_path) / args.timeseries_subdir

    if args.local_mode:
        # Local mode: read net-load inputs from the local study inputs folder.
        input_folder = Path(simulation_path) / "inputs"
    elif netload_path is not None:
        # Use the directory reported by the SDK so the path is always correct
        # regardless of whether the SDK preserves the remote subdirectory structure.
        input_folder = netload_path.parent
    else:
        # Fallback: SDK preserves remote path structure under the download directory.
        netload_remote = Path(args.netload_file)
        input_folder = OUTPUT_PATH / netload_remote.parent

    output_path.mkdir(parents=True, exist_ok=True)

    # --- VALIDATE INPUTS EXIST ---
    print(f"\n[DEBUG] ========== INPUT FILE VALIDATION ==========")
    print(f"[DEBUG] Input folder: {input_folder}")
    print(f"[DEBUG] Input folder exists: {input_folder.exists()}")

    netload_filename = Path(args.netload_file).name
    netload_file = input_folder / netload_filename

    print(f"[DEBUG] Netload file: {netload_file}")
    print(f"[DEBUG] Netload exists: {netload_file.exists()}")

    if not netload_file.exists():
        print(f"[FAIL] Netload file NOT found: {netload_file}")
        print(f"[FAIL] Files in {input_folder}:")
        try:
            for f in input_folder.iterdir():
                print(f"[FAIL]   {f.name}")
        except Exception as e:
            print(f"[FAIL]   (unable to list folder contents: {e})")
        raise FileNotFoundError(f"{netload_filename} not found at {netload_file}")

    # ---------------- LOAD ----------------
    print(f"\n[DEBUG] Loading Excel files...")
    try:
        load_df = pd.read_excel(netload_file, sheet_name="Load")
        solar_df = pd.read_excel(netload_file, sheet_name="Solar")
        wind_df = pd.read_excel(netload_file, sheet_name="Wind")
        print(f"[DEBUG] Load shape: {load_df.shape}")
        print(f"[DEBUG] Solar shape: {solar_df.shape}")
        print(f"[DEBUG] Wind shape: {wind_df.shape}")
    except Exception as e:
        print(f"[FAIL] Failed to read Excel sheets: {e}")
        raise

    for df in [load_df, solar_df, wind_df]:
        df["Datetime"] = pd.to_datetime(df["Datetime"])

    # ---------------- NET LOAD ----------------
    load_cols = ["WZ_COAST","WZ_EAST","WZ_FAR_WEST","WZ_NORTH",
                 "WZ_NORTH_CENTRAL","WZ_SOUTH","WZ_SOUTH_CENTRAL","WZ_WEST"]

    load_df["Load"] = load_df[load_cols].sum(axis=1)
    solar_df["Solar"] = solar_df.drop(columns=["Parent Name","Collection","Property","Band","Datetime","Units"]).sum(axis=1)
    wind_df["Wind"] = wind_df.drop(columns=["Parent Name","Collection","Property","Band","Datetime","Units"]).sum(axis=1)

    merged = load_df[["Datetime","Load"]].merge(
        solar_df[["Datetime","Solar"]], on="Datetime"
    ).merge(
        wind_df[["Datetime","Wind"]], on="Datetime"
    )

    merged["NetLoad"] = merged["Load"] - merged["Wind"] - merged["Solar"]
    merged["Date"] = merged["Datetime"].dt.date
    merged["DailyMax"] = merged.groupby("Date")["NetLoad"].transform("max")
    merged["NetLoadNorm"] = merged["NetLoad"] / merged["DailyMax"]

    # --- CALCULATE MARKUP ADDER WITH VALIDATION ---
    print(f"\n[DEBUG] ========== MARKUP ADDER CALCULATION ==========")
    print(f"[DEBUG] Calculating piecewise linear interpolation...")

    try:
        merged["MarkupAdder"] = merged["NetLoadNorm"].apply(lambda x: piecewise_linear(x, bands))
        print(f"[DEBUG] Piecewise linear applied")
        print(f"[DEBUG]   Min: {merged['MarkupAdder'].min():.4f}, Max: {merged['MarkupAdder'].max():.4f}")
    except Exception as e:
        print(f"[FAIL] Piecewise linear failed: {e}")
        raise

    merged["Month"] = merged["Datetime"].dt.month
    print(f"[DEBUG] Unique months in data: {sorted(merged['Month'].unique())}")
    print(f"[DEBUG] Seasonal weights months: {sorted(seasonal_weights.keys())}")

    # --- CHECK FOR MISSING MONTHS ---
    missing_months = set(merged["Month"].unique()) - set(seasonal_weights.keys())
    if missing_months:
        print(f"[FAIL] Missing months in seasonal_weights: {sorted(missing_months)}")
        print(f"[FAIL] Every month present in the data must have a weight.")
        sys.exit(1)

    # Apply seasonal weights with NaN check
    print(f"[DEBUG] Applying seasonal weights...")
    print(f"[DEBUG] Before weight multiplication - Min: {merged['MarkupAdder'].min():.4f}, Max: {merged['MarkupAdder'].max():.4f}, Mean: {merged['MarkupAdder'].mean():.4f}")

    merged["MarkupAdder"] *= merged["Month"].map(seasonal_weights)

    print(f"[DEBUG] Seasonal weights applied")
    print(f"[DEBUG] After weight multiplication - Min: {merged['MarkupAdder'].min():.4f}, Max: {merged['MarkupAdder'].max():.4f}, Mean: {merged['MarkupAdder'].mean():.4f}")

    # Check for NaNs after multiplication
    nan_count = merged["MarkupAdder"].isna().sum()
    if nan_count > 0:
        print(f"[WARN] After applying weights: {nan_count} NaN values out of {len(merged)}")
        print(f"[WARN] This indicates missing months in seasonal_weights!")
    else:
        print(f"[DEBUG] No NaN values after weight multiplication")

    merged["MarkupAdder"] = merged["MarkupAdder"].rolling(3, center=True, min_periods=1).mean()

    # ---------------- READ & MODIFY EXISTING BID ADDER ----------------
    print(f"\n[DEBUG] ========== READING EXISTING BID ADDER ==========")

    # Find existing bid adder file in /simulation/TimeSeries/Bid Adders/
    bid_adder_stem = Path(args.bidadder_filename).stem  # e.g. Plexos_Markup_Adders_AllGenerators-2027
    existing_file = None

    for ext in [".xlsx", ".csv"]:
        candidate = output_path / (bid_adder_stem + ext)
        if candidate.exists():
            existing_file = candidate
            break

    if existing_file is None:
        print(f"[FAIL] Existing bid adder not found in {output_path}")
        print(f"[FAIL] Looking for: {bid_adder_stem}.xlsx or {bid_adder_stem}.csv")
        try:
            for f in output_path.iterdir():
                print(f"[FAIL]   Found: {f.name}")
        except Exception as e:
            print(f"[FAIL]   Unable to list directory contents: {e}")
        raise FileNotFoundError(f"Bid adder file not found: {bid_adder_stem}")

    print(f"[DEBUG] Found existing bid adder: {existing_file}")

    # Read existing file
    if existing_file.suffix == '.xlsx':
        existing_df = pd.read_excel(existing_file)
    else:
        existing_df = pd.read_csv(existing_file)

    print(f"[DEBUG] Existing bid adder shape: {existing_df.shape}")
    print(f"[DEBUG] Columns (first 10): {list(existing_df.columns)[:10]}")

    # Identify generator columns (everything except Year/Month/Day/Period)
    required_cols = ["Year", "Month", "Day", "Period"]
    gen_cols = [c for c in existing_df.columns if c not in required_cols]
    print(f"[DEBUG] Generator columns: {len(gen_cols)}")
    print(f"[DEBUG] Sample generators: {gen_cols[:5]}")

    if not gen_cols:
        print(f"[FAIL] No generator columns found in bid adder file: {existing_file}")
        print(f"[FAIL] Expected columns beyond {required_cols}. Got: {list(existing_df.columns)}")
        sys.exit(1)

    # Show ORIGINAL values before modification
    sample_gen = gen_cols[0]
    print(f"[DEBUG] BEFORE MarkupAdder - {sample_gen} first 5 values:")
    for i in range(min(5, len(existing_df))):
        print(f"[DEBUG]   Row {i}: {existing_df[sample_gen].iloc[i]:.4f}")

    orig_mean = existing_df[gen_cols].values.mean()
    print(f"[DEBUG] BEFORE MarkupAdder - Overall mean: {orig_mean:.4f}")

    # Verify row count matches
    if len(existing_df) != len(merged):
        print(f"[WARN] Row count mismatch: existing={len(existing_df)}, MarkupAdder={len(merged)}")
        min_rows = min(len(existing_df), len(merged))
        print(f"[WARN] Using first {min_rows} rows")
        markup_values = merged["MarkupAdder"].values[:min_rows]
        existing_df = existing_df.iloc[:min_rows].copy()
    else:
        markup_values = merged["MarkupAdder"].values

    # Apply MarkupAdder as MULTIPLIER to all generator columns in one vectorized operation
    print(f"[DEBUG] Applying MarkupAdder multiplier to {len(gen_cols)} generator columns...")
    print(f"[DEBUG] MarkupAdder stats — Min: {markup_values.min():.4f}, Max: {markup_values.max():.4f}, Mean: {markup_values.mean():.4f}")
    existing_df[gen_cols] = existing_df[gen_cols].multiply(markup_values, axis=0)

    # Show MODIFIED values after modification
    print(f"[DEBUG] AFTER MarkupAdder - {sample_gen} first 5 values:")
    for i in range(min(5, len(existing_df))):
        print(f"[DEBUG]   Row {i}: {existing_df[sample_gen].iloc[i]:.4f}")

    modified_mean = existing_df[gen_cols].values.mean()
    print(f"[DEBUG] AFTER MarkupAdder - Overall mean: {modified_mean:.4f}")
    if orig_mean != 0:
        print(f"[DEBUG] Change ratio: {modified_mean / orig_mean:.4f}x")
    else:
        print(f"[DEBUG] Change ratio: n/a (original mean was 0)")

    wide_df = existing_df

    # Save modified bid adder back — OVERWRITE the exact file PLEXOS reads
    # Save in the SAME format as the source file
    if existing_file.suffix == '.xlsx':
        wide_df.to_excel(existing_file, index=False, engine='openpyxl')
    else:
        wide_df.to_csv(existing_file, index=False)
    print(f"\n[OK] Modified Bid Adder saved: {existing_file} (format: {existing_file.suffix})")

    # --- UPDATE timeseries.zip so PLEXOS engine picks up the change ---
    timeseries_zip = Path(simulation_path) / "timeseries.zip"
    if timeseries_zip.exists() and not args.local_mode:
        print(f"\n[ZIP] ========== UPDATING timeseries.zip ==========")
        # The entry inside the zip matches: <timeseries_subdir>/<filename>
        zip_entry_name = f"{args.timeseries_subdir}/{existing_file.name}"
        print(f"[ZIP] Zip file: {timeseries_zip}")
        print(f"[ZIP] Replacing entry: {zip_entry_name}")

        temp_zip_path = timeseries_zip.with_suffix(".tmp.zip")
        try:
            replaced = False
            with zipfile.ZipFile(timeseries_zip, 'r') as zin:
                with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        if item.filename == zip_entry_name:
                            # Replace with modified file
                            zout.write(str(existing_file), zip_entry_name)
                            replaced = True
                            print(f"[ZIP] Replaced: {zip_entry_name}")
                        else:
                            # Copy unchanged entry
                            zout.writestr(item, zin.read(item.filename))

            if not replaced:
                print(f"[FAIL] Entry '{zip_entry_name}' not found in timeseries.zip")
                if temp_zip_path.exists():
                    temp_zip_path.unlink()
                sys.exit(1)

            # Swap temp zip for original
            timeseries_zip.unlink()
            temp_zip_path.rename(timeseries_zip)
            print(f"[ZIP] timeseries.zip updated successfully")

            # Verify
            with zipfile.ZipFile(timeseries_zip, 'r') as zcheck:
                info = zcheck.getinfo(zip_entry_name)
                print(f"[ZIP] Verified: {zip_entry_name} ({info.file_size:,} bytes in zip)")
            print(f"[ZIP] ==============================================\n")
        except Exception as e:
            print(f"[ZIP] ERROR updating timeseries.zip: {e}")
            print(f"[ZIP] {traceback.format_exc()}")
            # Clean up temp file if it exists
            if temp_zip_path.exists():
                temp_zip_path.unlink()
    else:
        if not timeseries_zip.exists():
            print(f"[INFO] No timeseries.zip found at {timeseries_zip} — skipping zip update")

    # --- DIAGNOSTIC ---
    print(f"\n[DEBUG] ========== BID ADDER MODIFICATION VERIFICATION ==========")
    print(f"[DEBUG] Counter: {counter}")
    print(f"[DEBUG] Source file: {existing_file}")
    print(f"[DEBUG] Output file: {existing_file} (overwritten in-place)")
    print(f"[DEBUG] Seasonal weights used: {seasonal_weights}")
    print(f"[DEBUG] Bands used: {bands}")
    print(f"[DEBUG] wide_df shape: {wide_df.shape}")
    print(f"[DEBUG] Generator columns: {len(gen_cols)}")

    all_gen_values = wide_df[gen_cols].values.flatten()
    print(f"[DEBUG] Modified generator statistics (Counter {counter}):")
    print(f"[DEBUG]   Count: {len(all_gen_values):.0f}")
    print(f"[DEBUG]   Min: {all_gen_values.min():.4f}")
    print(f"[DEBUG]   Max: {all_gen_values.max():.4f}")
    print(f"[DEBUG]   Mean: {all_gen_values.mean():.4f}")
    print(f"[DEBUG]   Std: {all_gen_values.std():.4f}")
    print(f"[DEBUG] Bid Adder modified successfully\n")

    # Also save to output_path for the upload post-script (if available)
    if "output_path" in os.environ:
        env_output_path = Path(os.environ.get("output_path", "/output"))
        env_output_path.mkdir(parents=True, exist_ok=True)
        output_copy_name = existing_file.name
        shutil.copy2(str(existing_file), str(env_output_path / output_copy_name))
        print(f"[OK] Copied modified Bid Adder to output: {env_output_path / output_copy_name}")
    else:
        print(f"[INFO] output_path not set; bid adder available locally at: {existing_file}")

    # Log completion
    if not args.local_mode:
        print(f"\n[OK] ========== BID ADDER READY FOR SIMULATION ==========")
        print(f"[OK] Modified file: {existing_file}")
        print(f"[OK] Location: {output_path}/")
        print(f"[OK] Counter: {counter}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())