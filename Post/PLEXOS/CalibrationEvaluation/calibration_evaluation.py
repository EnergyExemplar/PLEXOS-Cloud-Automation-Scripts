"""
Calibration loop evaluation script — iterative bid adder adjustment.

Post-simulation evaluation that:
1. Extracts solution parquets (data, fullkeyinfo, period) from /simulation
2. Joins and filters for Region price data from the solution
3. Calculates average price and compares to threshold
4. Applies the configured fixed seasonal weights for bands-only calibration
5. Enqueues next simulation if needed (up to max retries)

Uses proven join/extraction logic from solution_data_query.py.
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import duckdb
from eecloud.cloudsdk import CloudSDK, SDKBase

# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — These defaults apply when the corresponding CLI flag is omitted.
# ═══════════════════════════════════════════════════════════════════════════════

# Target average price — calibration succeeds when the simulated average
# falls within threshold ± margin
THRESHOLD_VALUE = 80.0

# Calibration iteration counter (0-based)
COUNTER = 0

# Acceptable deviation from the threshold (fraction, e.g. 0.05 = ±5%)
MARGIN = 0.05

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Environment variables ─────────────────────────────────────────────────────
try:
    OUTPUT_PATH = Path(os.environ["output_path"])
except KeyError:
    print("[FAIL] Missing required environment variable: output_path")
    sys.exit(1)

try:
    DUCK_DB_PATH = os.environ["duck_db_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: duck_db_path")
    sys.exit(1)

# ── Arguments ─────────────────────────────────────────────────────────────────
def _make_parser():
    """Create and return the argument parser. Exposed at module level for test access."""
    p = argparse.ArgumentParser()
    p.add_argument("--threshold-value", type=float, default=THRESHOLD_VALUE)
    p.add_argument("--simulation-file-path", required=True,
                   help="DataHub path to the simulation payload JSON")
    p.add_argument("--counter", type=int, default=COUNTER)
    p.add_argument("--margin", type=float, default=MARGIN)
    p.add_argument("--pre-task-name", default="generate_bid_adder",
                   help="Name of the pre-simulation task in the payload JSON "
                        "(default: generate_bid_adder)")
    p.add_argument("--post-task-name", default="evaluate_results",
                   help="Name of the post-simulation task in the payload JSON "
                        "(default: evaluate_results)")
    p.add_argument("--pre-script-name", default="bid_adder_generation.py",
                   help="Script filename for the pre-simulation task "
                        "(default: bid_adder_generation.py)")
    p.add_argument("--post-script-name", default="calibration_evaluation.py",
                   help="Script filename for the post-simulation task "
                        "(default: calibration_evaluation.py)")
    return p

# Module-level parser instance retained for direct test access (TestParserDefaults).
parser = _make_parser()

# ── Solution extraction (from solution_data_query.py) ─────────────────────────
def find_solution_parquets():
    """
    Locate fullkeyinfo, period, and data parquets in /simulation.
    
    Searches under ParquetUploads/ first (expected location), then falls
    back to a recursive glob if the standard directory structure is absent.
    
    Returns:
        (fullkeyinfo_path, period_path, data_paths) or exits if not found
    """
    search_root = os.environ.get("simulation_path", "/simulation")
    parquet_uploads = glob.glob(f"{search_root}/**/ParquetUploads/**/*.parquet", recursive=True)

    if parquet_uploads:
        all_parquets = parquet_uploads
        print(f"[DEBUG] Using ParquetUploads directory ({len(all_parquets)} files)", flush=True)
    else:
        all_parquets = glob.glob(f"{search_root}/**/*.parquet", recursive=True)
        print(f"[DEBUG] ParquetUploads not found, scanning all parquets ({len(all_parquets)} files)", flush=True)

    # Find fullkeyinfo (single file)
    fullkey_parquets = [p for p in all_parquets if "fullkeyinfo" in p.lower()]
    # Find period (single file)
    period_parquets = [p for p in all_parquets if "period" in p.lower() and p.endswith(".parquet")]
    # Find data (partitioned by dataFileId — case-insensitive to handle variant casing)
    data_parquets = [p for p in all_parquets if "data" in p.lower() and "datafileid" in p.lower()]

    print(f"[DEBUG] ========== PARQUET DISCOVERY ==========", flush=True)
    print(f"[DEBUG] Search root: {search_root}", flush=True)
    print(f"[DEBUG] Total parquet files: {len(all_parquets)}", flush=True)
    print(f"[INFO] Found {len(data_parquets)} data parquets", flush=True)
    for i, p in enumerate(data_parquets[:5], 1):
        print(f"  [{i}] {p}", flush=True)
    if len(data_parquets) > 5:
        print(f"  ... and {len(data_parquets) - 5} more", flush=True)
    print(f"[INFO] Found {len(fullkey_parquets)} fullkey parquets", flush=True)
    for i, p in enumerate(fullkey_parquets, 1):
        print(f"  [{i}] {p}", flush=True)
    print(f"[INFO] Found {len(period_parquets)} period parquets", flush=True)
    for i, p in enumerate(period_parquets, 1):
        print(f"  [{i}] {p}", flush=True)

    if not data_parquets or not fullkey_parquets or not period_parquets:
        print("[FAIL] Missing required parquet files!", flush=True)
        sys.exit(1)

    # Use first match if multiples exist (e.g. multiple model solutions)
    fullkeyinfo_path = fullkey_parquets[0]
    period_path = period_parquets[0]
    
    if len(fullkey_parquets) > 1:
        print(f"[WARN] Found {len(fullkey_parquets)} fullkeyinfo files, using first: {fullkeyinfo_path}", flush=True)
    if len(period_parquets) > 1:
        print(f"[WARN] Found {len(period_parquets)} period files, using first: {period_path}", flush=True)

    return fullkeyinfo_path, period_path, data_parquets

# ── Build filter query (adapted from solution_data_query.py) ──────────────────
def build_filtered_query(fullkeyinfo_path, period_path, data_paths):
    """
    Build DuckDB SELECT for filtered join: Region prices.
    
    Joins:
        data (SeriesId, PeriodId, Value) 
        + fullkeyinfo (SeriesId, ChildClassName, PropertyName, ...) 
        + period (PeriodId, StartDate, PeriodTypeId, ...)
    
    Filters:
        - ChildClassName = 'Region'
        - PropertyName = 'Price'
        - Value IS NOT NULL
    
    Returns ALL columns (NOT aggregated) for staging to parquet.
    """
    data_paths_sql = "[" + ", ".join("'" + p.replace("'", "''") + "'" for p in data_paths) + "]"
    fullkeyinfo_escaped = str(fullkeyinfo_path).replace("'", "''")
    period_escaped = str(period_path).replace("'", "''")

    select_sql = f"""
        SELECT 
            fk.ChildClassName,
            fk.PropertyName,
            fk.SeriesId,
            d.PeriodId,
            d.Value,
            p.StartDate,
            p.PeriodTypeId
        FROM '{fullkeyinfo_escaped}' fk
        INNER JOIN read_parquet({data_paths_sql}, hive_partitioning = true) d
            ON fk.SeriesId = d.SeriesId
        INNER JOIN '{period_escaped}' p
            ON p.PeriodId = d.PeriodId
        WHERE d.Value IS NOT NULL
          AND LOWER(COALESCE(fk.ChildClassName, '')) = 'region'
          AND LOWER(COALESCE(fk.PropertyName, '')) = 'price'
    """
    
    return select_sql

# ── Stage filtered data to parquet (from solution_data_query_updated.py) ─────
def stage_filtered_parquet(fullkeyinfo_path, period_path, data_paths):
    """
    Export filtered join to intermediate parquet for reliable avg calculation.
    Two-step approach: export → then read from staged file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staged_file = OUTPUT_PATH / f"filtered_region_price_{timestamp}.parquet"
    
    select_sql = build_filtered_query(fullkeyinfo_path, period_path, data_paths)
    staged_sql_path = str(staged_file).replace("'", "''")
    
    try:
        with duckdb.connect(str(DUCK_DB_PATH)) as con:
            con.execute("SET enable_progress_bar=true")
            con.execute("SET enable_progress_bar_print=false")
            
            print(f"[DEBUG] Staging filtered data to: {staged_file}", flush=True)
            con.execute(
                f"COPY ({select_sql}) TO '{staged_sql_path}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            
            # Verify file was created
            if staged_file.exists():
                size_mb = staged_file.stat().st_size / (1024 * 1024)
                print(f"[OK] Staged parquet created: {size_mb:.2f} MB", flush=True)
                return str(staged_file)
            else:
                print(f"[FAIL] Staged file not created: {staged_file}", flush=True)
                return None
            
    except Exception as e:
        print(f"[FAIL] Failed to stage parquet: {e}", flush=True)
        return None

# ── Average calculation (two-step: stage then read) ──────────────────────────
def get_filtered_average_price():
    """
    Two-step average calculation:
    1. Stage filtered join to intermediate parquet
    2. Calculate AVG from staged file (more reliable than direct join)
    """
    print(f"[DEBUG] ========== EXTRACTING SOLUTION DATA ==========", flush=True)
    
    fullkeyinfo_path, period_path, data_paths = find_solution_parquets()
    
    print(f"[DEBUG] FullKeyInfo: {fullkeyinfo_path}", flush=True)
    print(f"[DEBUG] Period:      {period_path}", flush=True)
    print(f"[DEBUG] Data files:  {len(data_paths)} partitions", flush=True)

    # STEP 1: Stage filtered data to parquet
    print(f"[DEBUG] ========== STAGING FILTERED DATA ==========", flush=True)
    staged_file = stage_filtered_parquet(fullkeyinfo_path, period_path, data_paths)
    
    if not staged_file:
        print("[FAIL] Failed to stage filtered data", flush=True)
        return None
    
    # STEP 2: Calculate AVG from staged file
    print(f"[DEBUG] ========== CALCULATING AVERAGE PRICE ==========", flush=True)
    
    try:
        with duckdb.connect(str(DUCK_DB_PATH)) as con:
            con.execute("SET enable_progress_bar=true")
            con.execute("SET enable_progress_bar_print=false")
            
            staged_sql_path = str(staged_file).replace("'", "''")
            result = con.execute(
                f"""
                SELECT AVG(CAST(Value AS DOUBLE)), COUNT(*) as total_rows
                FROM read_parquet('{staged_sql_path}')
                WHERE Value IS NOT NULL
                """
            ).fetchone()
        
        if not result:
            print("[FAIL] Query returned no data", flush=True)
            return None
        
        avg_value = float(result[0]) if result[0] is not None else None
        total_rows = int(result[1]) if result[1] is not None else 0
        
        if avg_value is None:
            print(f"[FAIL] Average is NULL (check filters). Total rows in staged file: {total_rows}", flush=True)
            return None
        
        print(f"[DEBUG] Query executed successfully", flush=True)
        print(f"[DEBUG] Total rows matching filters: {total_rows}", flush=True)
        print(f"[DEBUG] Average value: {avg_value:.2f}", flush=True)
        return avg_value
        
    except Exception as e:
        print(f"[FAIL] Failed to calculate average: {e}", flush=True)
        return None

# ── Parameter evolution ───────────────────────────────────────────────────────
MAX_ITERATIONS = 3

def get_next_bands(counter):
    """Increasing bands to test price sensitivity."""
    bands_by_counter = {
        0: "0.0:0,0.6:0,0.8:25,0.9:125,1.0:225",       # 1× (baseline)
        1: "0.0:0,0.6:0,0.8:75,0.9:375,1.0:675",       # 3×
        2: "0.0:0,0.6:0,0.8:125,0.9:625,1.0:1125",     # 5×
    }
    bands = bands_by_counter.get(counter, bands_by_counter[2])
    print(f"[DEBUG] Bands for counter {counter}: {bands}", flush=True)
    return bands

# Fixed seasonal weights — only bands change across iterations.
BASE_WEIGHTS_STR = "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05"

def get_adjusted_seasonal_weights(current_avg, target):
    """Return fixed base seasonal weights (unchanged across iterations).

    Only bands are adjusted per iteration; seasonal weights remain constant.
    """
    print(f"[DEBUG] Using fixed base seasonal weights (bands-only calibration)", flush=True)
    print(f"[DEBUG] Weights: {BASE_WEIGHTS_STR}", flush=True)
    return BASE_WEIGHTS_STR

# ── Enqueue next iteration ────────────────────────────────────────────────────
def enqueue_next_simulation(next_counter, current_avg, threshold_value, simulation_file_path, margin,
                            pre_task_name="generate_bid_adder", post_task_name="evaluate_results",
                            pre_script_name="bid_adder_generation.py", post_script_name="calibration_evaluation.py"):
    """Download payload, adjust parameters, and enqueue next simulation."""

    print(f"\n[ENQUEUE] ========== STARTING ENQUEUE PROCESS ==========", flush=True)
    print(f"[ENQUEUE] Counter: {next_counter}, Current Avg: {current_avg:.2f}, Target: {threshold_value}", flush=True)

    try:
        cloud_cli_path = os.environ["cloud_cli_path"]
    except KeyError:
        print("[FAIL] Missing required environment variable: cloud_cli_path")
        sys.exit(1)

    pxc = CloudSDK(cli_path=cloud_cli_path)

    # STEP 1: Download payload
    local_payload_dir = str(OUTPUT_PATH)
    remote_pattern = simulation_file_path
    
    print(f"\n[ENQUEUE] STEP 1: Download payload...", flush=True)
    print(f"[ENQUEUE] Downloading payload from: {remote_pattern}", flush=True)
    print(f"[ENQUEUE] Output directory: {local_payload_dir}", flush=True)
    
    response = pxc.datahub.download(
        remote_glob_patterns=[remote_pattern],
        output_directory=local_payload_dir,
        print_message=True
    )

    # Validate SDK response and locate downloaded payload via LocalFilePath
    data = SDKBase.get_response_data(response)
    local_payload_path = None
    if data is not None and hasattr(data, "DatahubResourceResults"):
        for result in data.DatahubResourceResults:
            if not getattr(result, "Success", False):
                reason = getattr(result, "FailureReason", "unknown")
                if reason == "File is identical to the remote file":
                    local_file = getattr(result, "LocalFilePath", None)
                    if local_file:
                        local_payload_path = Path(local_file)
                else:
                    print(f"[FAIL] DataHub download failed: {reason}", flush=True)
                    sys.exit(1)
            else:
                local_file = getattr(result, "LocalFilePath", None)
                if local_file:
                    local_payload_path = Path(local_file)

    # Fall back to constructing path from known filename if SDK did not report LocalFilePath
    if local_payload_path is None:
        expected_name = Path(simulation_file_path).name
        # Try flat path first, then check if SDK preserved remote subdirectory structure
        flat_path = Path(local_payload_dir) / expected_name
        subdir_path = Path(local_payload_dir) / simulation_file_path
        if flat_path.exists():
            local_payload_path = flat_path
        elif subdir_path.exists():
            local_payload_path = subdir_path
        else:
            local_payload_path = flat_path  # will fail in the exists() check below

    if not local_payload_path.exists():
        print(f"[FAIL] Payload file not found at expected path: {local_payload_path}", flush=True)
        sys.exit(1)

    print(f"[OK] Payload downloaded and verified: {local_payload_path}", flush=True)
    
    with open(local_payload_path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)

    print(f"[DEBUG] Total tasks in payload: {len(payload['simulationOptions']['simulationTasks'])}", flush=True)

    # STEP 2: Update tasks with new counter and adjusted weights
    print(f"\n[ENQUEUE] STEP 2: Update payload tasks with counter={next_counter}...", flush=True)
    tasks_updated = {pre_task_name: False, post_task_name: False}
    
    for task in payload["simulationOptions"]["simulationTasks"]:
        task_name = task["name"]
        
        if task_name == pre_task_name:
            adjusted_weights = get_adjusted_seasonal_weights(current_avg, threshold_value)
            print(
                f"[DEBUG] Retrieved fixed seasonal weights for iteration "
                f"(avg={current_avg:.2f}, target={threshold_value})",
                flush=True,
            )

            # Preserve the existing --bidadder-filename from the payload so the loop
            # does not silently change user configuration.
            existing_args = task.get("arguments", "")
            bidadder_filename = None
            if "--bidadder-filename" in existing_args:
                try:
                    bidadder_filename = existing_args.split("--bidadder-filename")[1].strip().split()[0]
                except (IndexError, ValueError):
                    pass

            if bidadder_filename is None:
                print(f"[FAIL] Could not parse --bidadder-filename from existing task arguments", flush=True)
                print(f"[FAIL] Existing arguments: {existing_args}", flush=True)
                sys.exit(1)

            # Preserve --netload-file from the existing payload if present
            netload_file = None
            if "--netload-file" in existing_args:
                try:
                    netload_file = existing_args.split("--netload-file")[1].strip().split("--")[0].strip()
                except (IndexError, ValueError):
                    pass

            if netload_file is None:
                print(f"[FAIL] Could not parse --netload-file from existing task arguments", flush=True)
                print(f"[FAIL] Existing arguments: {existing_args}", flush=True)
                sys.exit(1)

            # Preserve --timeseries-subdir from the existing payload if present
            timeseries_subdir = None
            if "--timeseries-subdir" in existing_args:
                try:
                    timeseries_subdir = existing_args.split("--timeseries-subdir")[1].strip().split("--")[0].strip()
                except (IndexError, ValueError):
                    pass

            new_args = (
                f"python3 {pre_script_name} "
                f"--bands {get_next_bands(next_counter)} "
                f"--seasonal-weights {adjusted_weights} "
                f"--counter {next_counter} "
                f"--bidadder-filename {bidadder_filename} "
                f"--netload-file {netload_file}"
            )
            if timeseries_subdir:
                new_args += f" --timeseries-subdir {timeseries_subdir}"
            task["arguments"] = new_args
            tasks_updated[pre_task_name] = True
            print(f"[OK] Updated {pre_task_name}:", flush=True)
            print(f"     Counter: {next_counter}", flush=True)
            print(f"     Output file: {bidadder_filename}", flush=True)
            print(f"     Bands: {get_next_bands(next_counter)}", flush=True)
            print(f"     Adjusted weights: {adjusted_weights}", flush=True)

        elif task_name == post_task_name:
            new_args = (
                f"python3 {post_script_name} "
                f"--threshold-value {threshold_value} "
                f"--counter {next_counter} "
                f"--margin {margin} "
                f"--simulation-file-path {simulation_file_path} "
                f"--pre-task-name {pre_task_name} "
                f"--post-task-name {post_task_name} "
                f"--pre-script-name {pre_script_name} "
                f"--post-script-name {post_script_name}"
            )
            task["arguments"] = new_args
            tasks_updated[post_task_name] = True
            print(f"[OK] Updated {post_task_name}:", flush=True)
            print(f"     Counter: {next_counter}", flush=True)
            print(f"     Threshold: {threshold_value}", flush=True)

    # Verify all tasks were updated
    print(f"\n[DEBUG] Task update status:", flush=True)
    for task_name, updated in tasks_updated.items():
        status = "UPDATED" if updated else "NOT FOUND"
        print(f"     {task_name}: {status}", flush=True)
    
    if not all(tasks_updated.values()):
        print(f"[WARN] Some tasks were not found in payload", flush=True)

    # STEP 3: Save updated payload
    print(f"\n[ENQUEUE] STEP 3: Save updated payload...", flush=True)
    with open(local_payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] Payload updated and saved: {local_payload_path}", flush=True)
    
    # --- DIAGNOSTIC: Verify payload was actually updated ---
    print(f"\n[DEBUG] Verifying payload update...", flush=True)
    try:
        with open(local_payload_path, "r", encoding="utf-8-sig") as f:
            payload_verify = json.load(f)
        for task in payload_verify["simulationOptions"]["simulationTasks"]:
            if task["name"] == pre_task_name:
                if f"--counter {next_counter}" in task["arguments"]:
                    print(f"[DEBUG] Payload correctly has counter={next_counter}", flush=True)
                else:
                    print(f"[DEBUG] Payload counter NOT updated!", flush=True)
                    print(f"[DEBUG]   Arguments: {task['arguments'][:150]}", flush=True)
                # Show the adjusted weights in payload
                if "--seasonal-weights" in task["arguments"]:
                    weights_part = task["arguments"].split("--seasonal-weights")[1].split("--counter")[0].strip()
                    print(f"[DEBUG] Payload seasonal weights for iteration {next_counter}:", flush=True)
                    print(f"[DEBUG]   {weights_part[:80]}...", flush=True)
    except Exception as e:
        print(f"[DEBUG] Could not verify payload: {e}", flush=True)
    print(f"[DEBUG] End payload verification\n", flush=True)
    
    # STEP 4: Enqueue simulation
    print(f"\n[ENQUEUE] STEP 4: Enqueue simulation with counter={next_counter}...", flush=True)
    try:
        response = pxc.simulation.enqueue_simulation(
            file_path=str(local_payload_path),
            print_message=True
        )
        enqueue_data = SDKBase.get_response_data(response)
        if enqueue_data is not None and hasattr(enqueue_data, "SimulationStarted"):
            started = enqueue_data.SimulationStarted
            if started:
                sim_id = getattr(started[0].Id, "Value", started[0].Id)
                print(f"[OK] Simulation enqueued — ID: {sim_id}", flush=True)
            else:
                print(f"[WARN] Enqueue response has no SimulationStarted entries", flush=True)
        else:
            print(f"[OK] Simulation enqueued successfully", flush=True)
        print(f"[ENQUEUE] ========== ENQUEUE COMPLETE ==========", flush=True)
    except Exception as e:
        print(f"[FAIL] Failed to enqueue simulation: {e}", flush=True)
        sys.exit(1)

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = _make_parser()
    args = parser.parse_args()

    threshold_value = args.threshold_value
    simulation_file_path = args.simulation_file_path
    counter = args.counter
    margin = args.margin
    pre_task_name = args.pre_task_name
    post_task_name = args.post_task_name
    pre_script_name = args.pre_script_name
    post_script_name = args.post_script_name

    print(f"[INFO] Counter: {counter}", flush=True)
    print(f"[INFO] Threshold: {threshold_value}", flush=True)
    print(f"[INFO] Margin: {margin}", flush=True)

    print("[DEBUG] Starting evaluation logic...", flush=True)

    try:
        avg_value = get_filtered_average_price()
    except Exception as e:
        print(f"[FAIL] Failed to extract solution data: {e}", flush=True)
        return 1

    if avg_value is None:
        print("[FAIL] Could not calculate average price", flush=True)
        return 1

    lower_bound = threshold_value * (1 - margin)
    upper_bound = threshold_value * (1 + margin)

    print(f"[AVG] {avg_value}", flush=True)
    print(f"[RANGE] {lower_bound} - {upper_bound}", flush=True)

    # ✅ SUCCESS
    if lower_bound <= avg_value <= upper_bound:
        print(f"\n[SUCCESS] ========== CALIBRATION COMPLETE ==========", flush=True)
        print(f"[SUCCESS] Average value {avg_value:.2f} is within range [{lower_bound:.2f}, {upper_bound:.2f}]", flush=True)
        print(f"[SUCCESS] Threshold target: {threshold_value}", flush=True)
        return 0

    # ❌ STOP CONDITION
    if counter + 1 >= MAX_ITERATIONS:
        print(f"\n[STOP] ========== MAX RETRIES REACHED ==========", flush=True)
        print(f"[STOP] Counter: {counter}", flush=True)
        print(f"[STOP] Final average: {avg_value:.2f}", flush=True)
        print(f"[STOP] Target range: [{lower_bound:.2f}, {upper_bound:.2f}]", flush=True)
        print(f"[STOP] Ending calibration after {MAX_ITERATIONS} iterations.", flush=True)
        return 0

    # 🔁 RETRY
    print(f"\n[RETRY] ========== OUTSIDE RANGE - PREPARING RETRY ==========", flush=True)
    print(f"[RETRY] Current average: {avg_value:.2f}", flush=True)
    print(f"[RETRY] Target range: [{lower_bound:.2f}, {upper_bound:.2f}]", flush=True)
    print(f"[RETRY] Deviation: {((avg_value - threshold_value) / threshold_value * 100):.2f}%", flush=True)
    print(f"[RETRY] Next counter: {counter + 1}", flush=True)

    try:
        enqueue_next_simulation(counter + 1, avg_value, threshold_value, simulation_file_path, margin,
                                pre_task_name=pre_task_name, post_task_name=post_task_name,
                                pre_script_name=pre_script_name, post_script_name=post_script_name)
        print(f"\n[OK] Next simulation enqueued. Calibration iteration complete.", flush=True)
    except Exception as e:
        print(f"[FAIL] Failed to enqueue next simulation: {e}", flush=True)
        import traceback
        print(f"[FAIL] Traceback: {traceback.format_exc()}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())