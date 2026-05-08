"""
PLEXOS Pre-Script: Transmission Outages Island Detection Pipeline

Downloads input files from DataHub, runs island detection analysis,
writes output files to output_path, and uploads results back to DataHub.

Writes SRD properties into the PLEXOS model database and regenerates
the XML model file so the simulation engine picks up the changes.

Environment variables (platform-injected):
    cloud_cli_path   - (required) Path to the Cloud CLI executable
    output_path      - (required) Directory for output artifacts (auto-uploaded)
    study_id         - (required) Study ID for DB-to-XML conversion
    simulation_path  - (optional) Root path for study files (reference.db, project.xml)
    sqlite_input_path- (fallback) Model DB path when simulation_path is unavailable

CLI arguments (required unless noted otherwise):
    python3 island_node.py
        --start-date        2025-03-01T00:00
        --end-date          2025-03-31T23:00
        --output-folder     IslandScript/outputs
        --model-name        WY2025 woPTC_hourly
        --branch-data-file  IslandScript/inputs/Plexos Branch Data.csv
        --network-data-file IslandScript/inputs/Network Branch Data.xlsx
        --plexos-input-file IslandScript/inputs/Island Script data 0527.xlsx
        --scenario          Node off island script
        --default-from-date '12/1/2024 0:00'   (optional, default: 12/1/2024 0:00)

    Dates accept T-separator (recommended, no quotes needed) or space-separated
    with quotes: --start-date 2025-03-01T00:00 or --start-date '2025-03-01 00:00'.
    If only a date is given (no time), start-date defaults to 00:00 and
    end-date defaults to 23:00.

    File paths (--branch-data-file, --network-data-file, --plexos-input-file) are
    full DataHub paths including the folder, e.g. IslandScript/inputs/file.csv.
    Spaces in names are supported without quoting.

Example:
    python3 island_node.py \
        --start-date 2025-03-01T00:00 --end-date 2025-03-31T23:00 \
        --output-folder IslandScript/outputs \
        --model-name WY2025 woPTC_hourly \
        --branch-data-file IslandScript/inputs/Plexos Branch Data.csv \
        --network-data-file IslandScript/inputs/Network Branch Data.xlsx \
        --plexos-input-file IslandScript/inputs/Island Script data 0527.xlsx \
        --scenario Node off island script

Output files written to DataHub (under --output-folder):
    grid_data.csv
    hourly_data.parquet
    island_node_srd.csv
    island_gen_unit_out_srd.csv
    island_gen_unit_out_srd_helper.csv
    island_gen_must_run_srd.csv
    island_gen_must_run_srd_helper.csv
    dc_tie_units_srd.csv
    final_island_periods.xlsx
"""

import os
import sys
import logging
import argparse
import sqlite3
from pathlib import Path

import shutil

import pandas as pd
import networkx as nx
from eecloud.cloudsdk import CloudSDK, SDKBase
from plexos_sdk import PLEXOSSDK
from plexos_sdk.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError

logger = logging.getLogger(__name__)


# ============================================================
# STRUCTURAL CONSTANTS (never change between runs)
# ============================================================

SRD_COLUMNS = [
    "Collection", "Parent Object", "Child Object", "Property", "Value",
    "Data File", "Units", "Band", "Date From", "Date To", "Timeslice",
    "Action", "Expression", "Scenario", "Memo"
]

GRID_OUTPUT_COLUMNS = [
    'From Number', 'To Number', 'Circuit', 'Date From', 'Date To',
    'Value', 'From Name', 'To Name', 'Category', 'Child Object'
]

GRID_COLUMN_RENAME_MAPPING = {
    'Date From': 'From Date',
    'Date To': 'To Date',
    'Value': 'Status'
}

ISLAND_DETECTOR_COLS_RENAME = {
    'From Number': 'source',
    'To Number': 'target',
    'Circuit': 'circuit_id',
    'Status': 'status'
}

ISLAND_COLS = ['node', 'island_id', 'island_size']

LINES_KEY_COLUMNS = ['From Number', 'To Number', 'Circuit']
ALL_LINES_COLUMNS = [
    'Date', 'Hour', 'From Number', 'To Number', 'Circuit', 'Status',
    'timestamp', 'From Name', 'To Name', 'Category', 'Child Object'
]
HOURLY_DATA_STRING_COLS = ['Circuit', 'From Name', 'To Name', 'Category', 'Child Object']

SRD_NAMES_MAPPING = {
    "node": "Child Object",
    "from_date": "Date From",
    "to_date": "Date To"
}

RESO_NODE_NAMES_MAPPING = {
    'Parent Name': "Child Object",
    'from_date': "Date From",
    'to_date': "Date To"
}

DEFAULT_VALUES_FOR_NODE_SRD = {
    "Collection": "Nodes",
    "Parent Object": "System",
    "Property": "Units",
    "Value": 0,
    "Data File": None,
    "Units": '-',
    "Band": 1,
    "Timeslice": None,
    "Action": '=',
    "Expression": None,
    "Scenario": None,
    "Memo": None,
}

GEN_UNIT_OUT_DEFAULT_DATA = {
    "Parent Object": "System",
    "Property": "Units Out",
    "Value": 1,
    "Data File": None,
    "Units": "-",
    "Band": 1,
    "Timeslice": None,
    "Action": "=",
    "Expression": None,
    "Scenario": None
}

DEFAULT_DATA_DC_REGION_UNITS = {
    "Collection": "Regions",
    "Parent Object": "System",
    "Property": "Units",
    "Value": 0,
    "Data File": None,
    "Units": "-",
    "Band": 1,
    "Timeslice": None,
    "Action": "=",
    "Expression": None,
    "Scenario": None,
    "Memo": None,
}

COLLECTION_MAPPING = {
    "Generator": "Generators",
    "Battery": "Batteries"
}


# ============================================================
# DATAHUB HELPERS
# ============================================================

def init_cloud_sdk(cli_path: str):
    """Initialize and authenticate CloudSDK using platform env vars."""
    pxc = CloudSDK(cli_path=cli_path)
    return pxc


def download_inputs_from_datahub(pxc, remote_files: list[str], local_dir: str):
    """
    Download specific input files from DataHub to a local directory.
    After download, files are flattened into local_dir (subfolder structure removed).
    """
    os.makedirs(local_dir, exist_ok=True)

    logger.info(f"Downloading inputs from DataHub: {remote_files} -> {local_dir}")

    resp = pxc.datahub.download(
        remote_glob_patterns=remote_files,
        output_directory=local_dir,
        parallel_download=True,
        print_message=True,
    )
    result = SDKBase.get_response_data(resp)

    if result is None:
        raise RuntimeError(f"DataHub download failed: {resp}")

    if result.DatahubResourceResults:
        for item in result.DatahubResourceResults:
            if item.Success:
                logger.info(f"  Downloaded: {item.RelativeFilePath} -> {item.LocalFilePath}")
            elif getattr(item, "FailureReason", "") == "File is identical to the remote file":
                logger.info(f"  Already up to date: {item.RelativeFilePath}")
            else:
                raise RuntimeError(
                    f"  Failed to download {item.RelativeFilePath}: {item.FailureReason}"
                )
    else:
        raise RuntimeError("No files found in DataHub at the specified path.")

    # Flatten: DataHub may preserve folder structure (e.g. _inputs/IslandScript/inputs/file.csv).
    # Walk the download dir and move all files up to local_dir so paths are predictable.
    seen_names: set[str] = set()
    for root, dirs, files in os.walk(local_dir):
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(local_dir, fname)
            if src != dst:
                if fname in seen_names:
                    raise RuntimeError(
                        f"Filename collision during flattening: '{fname}' "
                        f"already exists in {local_dir}"
                    )
                os.replace(src, dst)
                logger.info(f"  Flattened: {src} -> {dst}")
            seen_names.add(fname)

    logger.info("All input files downloaded from DataHub.")


def upload_outputs_to_datahub(pxc, local_dir: str, remote_folder: str,
                              glob_patterns=None):
    """
    Upload all output files from a local directory to a DataHub folder.
    """
    if glob_patterns is None:
        glob_patterns = ["**/*.csv", "**/*.parquet"]
    logger.info(f"Uploading outputs to DataHub: {local_dir} -> {remote_folder}")

    resp = pxc.datahub.upload(
        local_folder=local_dir,
        remote_folder=remote_folder,
        glob_patterns=glob_patterns,
        is_versioned=True,
        parallel_upload=True,
        print_message=True,
    )
    result = SDKBase.get_response_data(resp)

    if result is None:
        raise RuntimeError(f"DataHub upload failed: {resp}")

    if result.DatahubResourceResults:
        for item in result.DatahubResourceResults:
            if item.Success:
                logger.info(f"  Uploaded: {item.LocalFilePath} -> {item.RelativeFilePath}")
            elif getattr(item, "FailureReason", "") == "File is identical to the remote file":
                logger.info(f"  Already up to date: {item.LocalFilePath}")
            else:
                logger.error(
                    f"  Failed to upload {item.LocalFilePath}: {item.FailureReason}"
                )
                raise RuntimeError(
                    f"DataHub upload failed for {item.LocalFilePath}: {item.FailureReason}"
                )
    else:
        logger.warning("No files were uploaded to DataHub.")

    logger.info("All output files uploaded to DataHub.")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def add_one_hour_to_last_month_hour(df):
    to_date = pd.to_datetime(df['to_date'], errors='coerce')
    # Add 1 hour to ALL to_date so Date To represents the END of the
    # last islanded hour, not its start.
    df['to_date'] = to_date + pd.Timedelta(hours=1)
    # For month-boundary transitions (original hour was 23:00 on month-end,
    # now 00:00 on month-start) add an extra 1-hour buffer.
    to_date_adj = pd.to_datetime(df['to_date'], errors='coerce')
    month_boundary_mask = to_date_adj.dt.is_month_start & (to_date_adj.dt.hour == 0)
    if month_boundary_mask.any():
        df.loc[month_boundary_mask, 'to_date'] = to_date_adj[month_boundary_mask] + pd.Timedelta(hours=1)
    return df


def convert_date_format(df, date_columns=None):
    if date_columns is None:
        date_columns = ["Date From", "Date To"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.floor("s")
    return df


# ============================================================
# PIPELINE CLASSES
# ============================================================

class GridDataProcessor:
    def __init__(self, input_file, network_file, output_file, output_dir, default_from_date):
        self.df_plexos_branch = pd.read_csv(input_file)
        self.network_df = pd.read_excel(network_file)
        self.output_file = output_file
        os.makedirs(output_dir, exist_ok=True)
        self.default_from_date = default_from_date

    def process_grid_data(self) -> pd.DataFrame:
        try:
            logger.info("Starting grid data processing...")
            df = self.df_plexos_branch
            network_df = self.network_df

            mask_to_remove = (df['Value'] == 1) & df['Date To'].notna() & (df['Date To'].astype(str).str.strip() != '')
            df_cleaned = df[~mask_to_remove]

            is_blank_date_to = df_cleaned['Date To'].isna() | (df_cleaned['Date To'].astype(str).str.strip() == '')
            set1 = df_cleaned[is_blank_date_to].copy()
            set2 = df_cleaned[~is_blank_date_to].copy()

            set1 = set1[~set1['Child Object'].isin(set2['Child Object'])]

            child_objects_value0_in_set1 = set1.loc[set1['Value'] == 0, 'Child Object'].unique()
            set2 = set2[~set2['Child Object'].isin(child_objects_value0_in_set1)]

            set1['Set'] = 'Set 1'
            set2['Set'] = 'Set 2'

            final_df = pd.concat([set1, set2], ignore_index=True)
            final_df = final_df[~final_df.apply(lambda row: row.astype(str).str.strip().eq('').all(), axis=1)]

            for col in ['Date From', 'Date To']:
                final_df[col] = pd.to_datetime(final_df[col], errors='coerce').dt.strftime('%m/%d/%Y %I:%M:%S %p')

            merged_df = final_df.merge(network_df, how='left', left_on='Child Object', right_on='Name')

            final_df_output = merged_df[GRID_OUTPUT_COLUMNS].rename(
                GRID_COLUMN_RENAME_MAPPING, axis=1
            )

            for col in ['From Date', 'To Date']:
                final_df_output[col] = final_df_output[col].fillna('').astype(str).str.strip()

            mask = (final_df_output['From Date'] == '') & (final_df_output['To Date'] != '')
            final_df_output.loc[mask, 'From Date'] = self.default_from_date

            final_df_output.to_csv(self.output_file, index=False)
            logger.info(f"Final grid data saved to '{self.output_file}'")
            return final_df_output

        except Exception as e:
            logger.error(f"Error in grid data processing: {str(e)}")
            raise
        finally:
            if 'df_cleaned' in locals():
                del df_cleaned


class OutageReportGenerator:
    def __init__(self, start_date, end_date, output_dir="outputs"):
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.lines_key_columns = LINES_KEY_COLUMNS

    def merge_outages(self, outage_periods):
        if not outage_periods:
            return []
        outage_periods.sort()
        merged = [outage_periods[0]]
        for current in outage_periods[1:]:
            last = merged[-1]
            if current[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)
        return merged

    def generate_hourly_outage_status(self, df, chunk_hours=24):
        df = convert_date_format(df, date_columns=["From Date", "To Date"])
        df["From Date"] = df["From Date"].dt.floor("h")
        df["To Date"] = df["To Date"].dt.ceil("h")

        start_date = pd.to_datetime(self.start_date)
        end_date = pd.to_datetime(self.end_date)

        if chunk_hours is None:
            return self._outage_status_matrix_helper(df, start_date, end_date)
        else:
            result_chunks = []
            current = start_date
            while current <= end_date:
                chunk_end = min(current + pd.Timedelta(hours=chunk_hours - 1), end_date)
                chunk_df = self._outage_status_matrix_helper(df.copy(), current, chunk_end)
                result_chunks.append(chunk_df)
                current = chunk_end + pd.Timedelta(hours=1)
            return pd.concat(result_chunks, ignore_index=True)

    def _outage_status_matrix_helper(self, df, start_date, end_date):
        time_range = pd.date_range(start=start_date, end=end_date, freq='h')
        lines_df = df[self.lines_key_columns].drop_duplicates().reset_index(drop=True)
        lines_df['key'] = 1
        time_df = pd.DataFrame({'timestamp': time_range, 'key': 1})
        all_combinations = lines_df.merge(time_df, on='key').drop('key', axis=1)
        all_combinations['Date'] = all_combinations['timestamp'].dt.date
        all_combinations['Hour'] = all_combinations['timestamp'].dt.hour

        all_combinations = self._assign_static_line_status(df, all_combinations)
        all_combinations = self._assign_dynamic_outage_status(df, all_combinations)

        result_df = all_combinations[ALL_LINES_COLUMNS].copy()
        return result_df.drop_duplicates()

    def _assign_static_line_status(self, df, all_combinations):
        static_mask = pd.isna(df["From Date"]) & pd.isna(df["To Date"])
        static_df = df[static_mask][self.lines_key_columns + ['Status', 'From Name', 'To Name', 'Category', 'Child Object']].drop_duplicates()
        return all_combinations.merge(static_df, on=self.lines_key_columns, how='left')

    def _assign_dynamic_outage_status(self, df, all_combinations):
        dynamic_mask = pd.notna(df["From Date"]) & pd.notna(df["To Date"])
        dynamic_df = df[dynamic_mask][['From Number', 'To Number', 'Circuit', 'From Date', 'To Date', 'Status', 'From Name', 'To Name', 'Category', 'Child Object']].copy()

        if not dynamic_df.empty:
            merged_outages_df = self._merge_dynamic_outages(dynamic_df)
            all_combinations = self._tag_outage_hours(all_combinations, merged_outages_df)
        else:
            all_combinations['Status'] = all_combinations['Status'].fillna(1).astype(int)
        return all_combinations

    def _merge_dynamic_outages(self, dynamic_df):
        merged_outages = []
        for (from_num, to_num, circuit), group in dynamic_df.groupby(self.lines_key_columns):
            outage_periods = list(zip(group['From Date'], group['To Date']))
            merged_periods = self.merge_outages(outage_periods)
            for from_date, to_date in merged_periods:
                merged_outages.append({
                    'From Number': from_num, 'To Number': to_num, 'Circuit': circuit,
                    'From Date': from_date, 'To Date': to_date, 'Status': 0,
                    'From Name': group['From Name'].iloc[0], 'To Name': group['To Name'].iloc[0],
                    'Category': group['Category'].iloc[0], 'Child Object': group['Child Object'].iloc[0]
                })
        return pd.DataFrame(merged_outages)

    def _tag_outage_hours(self, all_combinations, merged_outages_df):
        outage_hours_list = []
        for _, outage in merged_outages_df.iterrows():
            outage_hours = pd.date_range(start=outage['From Date'], end=outage['To Date'], freq='h')
            outage_hour_df = pd.DataFrame({
                'From Number': outage['From Number'], 'To Number': outage['To Number'],
                'Circuit': outage['Circuit'], 'timestamp': outage_hours, 'outage_status': 0,
            })
            outage_hours_list.append(outage_hour_df)

        if outage_hours_list:
            all_outage_hours = pd.concat(outage_hours_list, ignore_index=True)
            all_combinations = all_combinations.merge(
                all_outage_hours, on=self.lines_key_columns + ['timestamp'], how='left'
            )
            all_combinations['Status'] = all_combinations['outage_status'].combine_first(
                all_combinations['Status']
            ).fillna(1).astype(int)
            all_combinations = all_combinations.drop('outage_status', axis=1)
        else:
            all_combinations['Status'] = all_combinations['Status'].fillna(1).astype(int)

        meta_cols = ['From Name', 'To Name', 'Category', 'Child Object']
        meta_df = merged_outages_df[self.lines_key_columns + meta_cols].drop_duplicates()

        all_combinations = all_combinations.merge(
            meta_df, on=self.lines_key_columns, how='left', suffixes=('', '_dyn')
        )
        for col in meta_cols:
            dyn_col = f"{col}_dyn"
            if dyn_col in all_combinations.columns:
                all_combinations[col] = all_combinations[col].fillna(all_combinations[dyn_col])
                all_combinations.drop(columns=[dyn_col], inplace=True)

        return all_combinations


class IslandDetector:
    def __init__(self):
        pass

    def _build_island_df(self, components, timestamp):
        # Threshold: components larger than this are assumed to be the main
        # grid and are excluded from the island report.
        MAX_ISLAND_SIZE = 9000
        island_rows = []
        for island_id, comp in enumerate(components):
            if len(comp) <= MAX_ISLAND_SIZE:
                for node in comp:
                    island_rows.append({
                        'node': node, 'island_id': island_id,
                        'island_size': len(comp), 'timestamp': timestamp,
                        'date': timestamp.date(), 'hour': timestamp.hour
                    })
            else:
                logger.debug(
                    f"  Skipping main-grid component (island_id={island_id}, "
                    f"size={len(comp)}) at {timestamp}"
                )
        island_cols = ISLAND_COLS + ['timestamp', 'date', 'hour']
        return pd.DataFrame(island_rows) if island_rows else pd.DataFrame(columns=island_cols)

    def _build_island_and_bridging_for_timestamp(self, df, timestamp):
        df = df.copy()
        df['timestamp'] = timestamp
        df['date'] = timestamp.date()
        df['hour'] = timestamp.hour
        df = df.rename(columns=ISLAND_DETECTOR_COLS_RENAME)

        all_nodes = set(df['source']) | set(df['target'])
        active_df = df[df['status'] == 1]
        active_edges = (
            active_df.groupby(['source', 'target']).size().reset_index()[['source', 'target']]
        )

        G = nx.Graph()
        G.add_nodes_from(all_nodes)
        G.add_edges_from(active_edges.itertuples(index=False, name=None))

        components = list(nx.connected_components(G))
        island_df = self._build_island_df(components, timestamp)
        return island_df

    def detect_islands_hourly(self, hourly_data_df):
        if hourly_data_df.empty:
            return pd.DataFrame()

        all_islands = []

        for timestamp, group in hourly_data_df.groupby('timestamp'):
            island_df = self._build_island_and_bridging_for_timestamp(group.copy(), timestamp)
            if island_df is not None and not island_df.empty:
                island_df["timestamp"] = timestamp
                all_islands.append(island_df)

        return pd.concat(all_islands, ignore_index=True) if all_islands else pd.DataFrame()


class IslandReportConsolidator:
    def __init__(self, output_dir="processed_output"):
        self.processed_base_dir = output_dir
        os.makedirs(self.processed_base_dir, exist_ok=True)

    def summarize_island_periods(self, island_df):
        output_dir = self.processed_base_dir
        if "timestamp" in island_df.columns and "Datetime" not in island_df.columns:
            island_df["Datetime"] = island_df["timestamp"]

        island_df = island_df.copy()
        island_df["Datetime"] = pd.to_datetime(island_df["Datetime"])
        island_df = island_df.sort_values(["node", "Datetime"])

        result_data = []
        for node, group in island_df.groupby("node"):
            previous_date = None
            from_date = None
            period_island_id = None
            period_island_size = None

            for index, row in group.iterrows():
                current_date = row["Datetime"]
                if previous_date is None or (current_date - previous_date) > pd.Timedelta(hours=1):
                    if from_date is not None:
                        result_data.append({
                            "node": node, "island_id": period_island_id,
                            "island_size": period_island_size,
                            "from_date": from_date, "to_date": previous_date
                        })
                    from_date = current_date
                    period_island_id = row["island_id"]
                    period_island_size = row["island_size"]
                previous_date = current_date

            if from_date is not None:
                result_data.append({
                    "node": node, "island_id": period_island_id,
                    "island_size": period_island_size,
                    "from_date": from_date, "to_date": previous_date
                })

        processed_island_df = pd.DataFrame(result_data)
        processed_island_df = add_one_hour_to_last_month_hour(processed_island_df)
        processed_island_df = convert_date_format(processed_island_df, date_columns=["from_date", "to_date"])
        processed_output_file = f"{output_dir}/final_island_periods.xlsx"
        processed_island_df.to_excel(processed_output_file, index=False)
        logger.info(f"Final Island Period Report Saved: {processed_output_file}")

        return processed_island_df


class SRDBuilder:
    def __init__(self, plexos_input_path, start_date, end_date, output_paths,
                 node_scenario, must_run_scenario):
        all_sheets = pd.read_excel(plexos_input_path, sheet_name=None)
        self.start_date = start_date
        self.end_date = end_date
        self.output_paths = output_paths
        self.node_scenario = node_scenario
        self.must_run_scenario = must_run_scenario

        self.df_reso_nodes_members = all_sheets['Resouce Node Memberships']
        self.df_node_objects = all_sheets['Node Objects']
        self.df_gen_nodes_members = all_sheets['Generator.Nodes']
        self.df_gen_units_out = all_sheets['Generator Units Out']
        self.df_gen_units_out = self._fill_outages_missing_dates(self.df_gen_units_out)
        self.df_gen_must_run = all_sheets['Must_Run_Units']
        self.df_dc_region_node_memb = all_sheets['dc_ties_memb']

        # Override scenario fields in the SRD default dicts
        self.node_srd_defaults = {**DEFAULT_VALUES_FOR_NODE_SRD, "Scenario": node_scenario}
        self.dc_region_units_data = {**DEFAULT_DATA_DC_REGION_UNITS, "Scenario": node_scenario}

    def _fill_outages_missing_dates(self, df_gen_mapped, hours_to_add=2):
        from_date_dt = pd.to_datetime(self.start_date)
        to_date_dt = pd.to_datetime(self.end_date).floor('h')
        to_date_dt = (to_date_dt + pd.Timedelta(hours=hours_to_add))

        df_gen_mapped['Date From'] = df_gen_mapped['Date From'].fillna(from_date_dt)
        df_gen_mapped['Date To'] = df_gen_mapped['Date To'].fillna(to_date_dt)

        return df_gen_mapped

    def build_island_node_srd(self, final_island_periods):
        logger.info("Starting SRD conversion for islanded nodes.")

        df = final_island_periods.rename(columns=SRD_NAMES_MAPPING)
        df = df[list(SRD_NAMES_MAPPING.values())].copy()

        df_node_objects = self.df_node_objects.copy()
        df_node_objects['Node Number'] = (
            df_node_objects['Name'].str.extract(r'^(\d+)').astype(float)
        )
        df_node_objects = df_node_objects.dropna(subset=['Node Number'])
        df_node_objects['Node Number'] = df_node_objects['Node Number'].astype(int)
        df['Child Object'] = df['Child Object'].astype(int)

        df = df.merge(
            df_node_objects[['Node Number', 'Name']],
            how='left', left_on='Child Object', right_on='Node Number'
        )
        df = df.drop(columns=['Child Object', 'Node Number'])
        df = df.rename(columns={'Name': 'Child Object'})

        df = df.assign(**self.node_srd_defaults)
        df = df[SRD_COLUMNS]

        logger.info(f"Island Node DataFrame created (P1) with shape: {df.shape}")
        return df

    def build_resource_node_srd(self, final_island_periods, df_node_srd_p1):
        logger.info("Starting SRD creation for resource nodes.")

        df_reso_nodes_members = self.df_reso_nodes_members.copy()
        df_reso_nodes_members['Extracted_Node'] = (
            pd.to_numeric(
                df_reso_nodes_members['Child Name'].str.extract(r'^(\d+)')[0],
                errors='coerce'
            ).astype('Int64')
        )

        df_reso_nodes_mapped = df_reso_nodes_members.merge(
            final_island_periods, left_on='Extracted_Node', right_on='node', how='left'
        )

        df_reso_nodes_mapped = df_reso_nodes_mapped[df_reso_nodes_mapped['node'].notna()]
        df_reso_node_srd = df_reso_nodes_mapped[['Parent Name', 'from_date', 'to_date']].rename(
            columns=RESO_NODE_NAMES_MAPPING
        )

        df_reso_node_srd = df_reso_node_srd.assign(**self.node_srd_defaults)
        df_reso_node_srd = df_reso_node_srd[SRD_COLUMNS]

        df_node_srd = pd.concat([df_node_srd_p1, df_reso_node_srd], ignore_index=True)
        df_node_srd = convert_date_format(df_node_srd)
        df_node_srd.to_csv(self.output_paths['node_srd'], index=False)
        logger.info(f"Islanded Node Outages SRD created with shape: {df_node_srd.shape}")

        return df_node_srd

    def build_gen_unit_outage_srd(self, df_node_srd):
        self.df_gen_nodes_members['Collection'] = (
            self.df_gen_nodes_members['Collection']
            .str.split('.').str[0]
            .map(COLLECTION_MAPPING)
        )

        df_island_outages_gen = self.df_gen_nodes_members.merge(
            df_node_srd[['Child Object', 'Date From', 'Date To']],
            left_on='Child Name', right_on='Child Object', how='left'
        )

        df_island_outages_gen = df_island_outages_gen[df_island_outages_gen['Child Object'].notna()]
        df_gen_mapped = df_island_outages_gen[['Collection', 'Parent Name', 'Date From', 'Date To']]

        return df_gen_mapped

    def label_generator_outage_scenarios(self, df_gen_mapped):
        df_gen_mapped = df_gen_mapped.copy()
        df_gen_units_out = self.df_gen_units_out.copy()
        df_gen_mapped = convert_date_format(df_gen_mapped)
        df_gen_units_out = convert_date_format(df_gen_units_out)

        scenarios = []
        for idx, row in df_gen_mapped.iterrows():
            gen_name = row['Parent Name']
            new_from = row['Date From']
            new_to = row['Date To']

            existing = df_gen_units_out[df_gen_units_out['Child Object'] == gen_name]
            found = False
            for _, ex in existing.iterrows():
                ex_from = ex['Date From']
                ex_to = ex['Date To']

                if new_from >= ex_from and new_to <= ex_to:
                    scenarios.append("No need to include (Full Overlaped)")
                    found = True
                    break
                elif ex_from >= new_from and ex_to <= new_to:
                    scenarios.append("No need existing outages")
                    found = True
                    break
                elif (new_from <= ex_to and new_to >= ex_from):
                    scenarios.append("Partial Overlaped")
                    found = True
                    break
            if not found:
                scenarios.append("Different Outage Period")

        df_gen_mapped['Memo'] = scenarios
        df_gen_mapped.rename(columns={"Parent Name": "Child Object"}, inplace=True)
        df_gen_mapped = df_gen_mapped.assign(**GEN_UNIT_OUT_DEFAULT_DATA)
        df_gen_mapped = df_gen_mapped[SRD_COLUMNS]
        df_gen_mapped = convert_date_format(df_gen_mapped)
        df_gen_mapped.to_csv(self.output_paths['gen_unit_out_helper'], index=False)
        logger.info(f"Generator Unit Outages helper SRD created with shape: {df_gen_mapped.shape}")
        return df_gen_mapped

    def merge_partial_overlap_periods(self, df_gen_unit_out_srd):
        df_updated = df_gen_unit_out_srd.copy()
        df_gen_units_out = self.df_gen_units_out.copy()

        df_updated = convert_date_format(df_updated)
        df_gen_units_out = convert_date_format(df_gen_units_out)
        df_gen_units_out.drop(columns=['Category'], inplace=True, errors='ignore')

        mask_partial = df_updated['Memo'] == 'Partial Overlaped'
        for idx, row in df_updated[mask_partial].iterrows():
            gen = row['Child Object']
            new_from = row['Date From']
            new_to = row['Date To']

            overlaps = df_gen_units_out[
                (df_gen_units_out['Child Object'] == gen) &
                (df_gen_units_out['Date From'] <= new_to) &
                (df_gen_units_out['Date To'] >= new_from) &
                ~((new_from >= df_gen_units_out['Date From']) & (new_to <= df_gen_units_out['Date To'])) &
                ~((df_gen_units_out['Date From'] >= new_from) & (df_gen_units_out['Date To'] <= new_to))
            ]

            if not overlaps.empty:
                extended_from = min(new_from, overlaps['Date From'].min())
                extended_to = max(new_to, overlaps['Date To'].max())
                df_updated.at[idx, 'Date From'] = extended_from
                df_updated.at[idx, 'Date To'] = extended_to

        return df_updated

    def update_generator_outage_records(self, df_gen_unit_out_srd_updated):
        df_existing_outages = self.df_gen_units_out.copy()
        df_existing_outages.drop(columns=['Category'], inplace=True, errors='ignore')
        df_new_outage_data = df_gen_unit_out_srd_updated.copy()

        df_existing_outages = convert_date_format(df_existing_outages)
        df_new_outage_data = convert_date_format(df_new_outage_data)

        update_scenarios = ['No need existing outages', 'Partial Overlaped']
        rows_to_update = df_new_outage_data[df_new_outage_data['Memo'].isin(update_scenarios)]

        for _, new_outage_row in rows_to_update.iterrows():
            generator_name = new_outage_row['Child Object']
            updated_from_date = new_outage_row['Date From']
            updated_to_date = new_outage_row['Date To']

            generator_mask = df_existing_outages['Child Object'] == generator_name
            df_existing_outages.loc[generator_mask, 'Date From'] = updated_from_date
            df_existing_outages.loc[generator_mask, 'Date To'] = updated_to_date

        new_outage_periods = df_new_outage_data[
            df_new_outage_data['Memo'] == 'Different Outage Period'
        ].copy()

        if not new_outage_periods.empty:
            new_outage_periods['Scenario'] = self.node_scenario
            new_outage_periods['Memo'] = None
            new_outage_periods = new_outage_periods[df_existing_outages.columns]
            df_final_outages = pd.concat([df_existing_outages, new_outage_periods], ignore_index=True)
        else:
            df_final_outages = df_existing_outages

        df_final_outages = convert_date_format(df_final_outages)
        df_final_outages.to_csv(self.output_paths['gen_unit_out'], index=False)

        logger.info(f"Updated generator outages SRD created with shape: {df_final_outages.shape}")
        return df_final_outages

    def update_must_run_generators_for_islands(self, df_gen_unit_out_srd_final):
        mask = self.df_gen_must_run["Child Object"].isin(df_gen_unit_out_srd_final["Child Object"])

        self.df_gen_must_run['Scenario'] = self.df_gen_must_run['Scenario'].astype(object)
        self.df_gen_must_run.loc[mask, 'Scenario'] = self.must_run_scenario

        df_must_run_helper = self.df_gen_must_run[mask].copy()
        df_must_run_helper.to_csv(self.output_paths['gen_must_run_helper'], index=False)
        logger.info(f"Generator Must Run helper SRD created with shape: {df_must_run_helper.shape}")

        self.df_gen_must_run.to_csv(self.output_paths['gen_must_run'], index=False)
        logger.info(f"Generator Must Run SRD created with shape: {self.df_gen_must_run.shape}")

    def build_dc_tie_units_prop(self, df_node_srd):
        dc_tie_units_df = pd.merge(
            df_node_srd,
            self.df_dc_region_node_memb[['parent_object', 'child_object']],
            left_on='Child Object', right_on='parent_object', how='left'
        )

        dc_tie_units_df = dc_tie_units_df[dc_tie_units_df['child_object'].notna()]
        dc_tie_units_df = dc_tie_units_df[['child_object', 'Date From', 'Date To']]
        dc_tie_units_df.rename(columns={'child_object': 'Child Object'}, inplace=True)
        dc_tie_units_df = dc_tie_units_df.assign(**self.dc_region_units_data)
        dc_tie_units_df = dc_tie_units_df[SRD_COLUMNS]
        dc_tie_units_df.to_csv(self.output_paths['dc_tie_units'], index=False)
        logger.info(f"DC Tie Units SRD created with shape: {dc_tie_units_df.shape}")


# ============================================================
# PIPELINE ORCHESTRATION
# ============================================================

class OptimizedPipeline:
    """Main pipeline that connects all classes without intermediate files."""

    def __init__(self, output_dir, branch_data, network_data, plexos_input,
                 start_date, end_date, default_from_date,
                 node_scenario, must_run_scenario):
        os.makedirs(output_dir, exist_ok=True)

        output_paths = {
            'grid_data':           os.path.join(output_dir, 'grid_data.csv'),
            'hourly_data':         os.path.join(output_dir, 'hourly_data.parquet'),
            'node_srd':            os.path.join(output_dir, 'island_node_srd.csv'),
            'gen_unit_out':        os.path.join(output_dir, 'island_gen_unit_out_srd.csv'),
            'gen_unit_out_helper': os.path.join(output_dir, 'island_gen_unit_out_srd_helper.csv'),
            'gen_must_run':        os.path.join(output_dir, 'island_gen_must_run_srd.csv'),
            'gen_must_run_helper': os.path.join(output_dir, 'island_gen_must_run_srd_helper.csv'),
            'dc_tie_units':        os.path.join(output_dir, 'dc_tie_units_srd.csv'),
        }
        self.output_paths = output_paths

        self.grid_processor = GridDataProcessor(
            input_file=branch_data,
            network_file=network_data,
            output_file=output_paths['grid_data'],
            output_dir=output_dir,
            default_from_date=default_from_date,
        )
        self.outage_generator = OutageReportGenerator(
            start_date=start_date, end_date=end_date, output_dir=output_dir,
        )
        self.island_detector = IslandDetector()
        self.consolidator = IslandReportConsolidator(output_dir=output_dir)
        self.srd_builder = SRDBuilder(
            plexos_input_path=plexos_input,
            start_date=start_date, end_date=end_date,
            output_paths=output_paths,
            node_scenario=node_scenario,
            must_run_scenario=must_run_scenario,
        )

    def run_complete_analysis(self):
        logger.info("Starting the complete analysis pipeline...")

        # Step 1: Process grid data
        logger.info("Processing grid data...")
        df_grid_data = self.grid_processor.process_grid_data()

        # Step 2: Generate hourly status data
        logger.info("Generating hourly status data...")
        hourly_data = self.outage_generator.generate_hourly_outage_status(df_grid_data)

        for col in HOURLY_DATA_STRING_COLS:
            if col in hourly_data.columns:
                hourly_data[col] = hourly_data[col].astype(str)
        hourly_data.to_parquet(self.output_paths['hourly_data'], index=False)

        hourly_data.drop(
            columns=['From Name', 'To Name', 'Category', 'Child Object'],
            inplace=True, errors='ignore'
        )

        # Step 3: Detect islands
        logger.info("Detecting islands...")
        island_df = self.island_detector.detect_islands_hourly(
            hourly_data_df=hourly_data,
        )

        # Step 4: Generate final reports
        logger.info("Generating final reports...")
        final_island_periods = self.consolidator.summarize_island_periods(island_df)

        # Step 5: Build SRDs
        logger.info("Building SRDs...")
        df_node_srd_p1 = self.srd_builder.build_island_node_srd(final_island_periods.copy())
        df_node_srd = self.srd_builder.build_resource_node_srd(final_island_periods.copy(), df_node_srd_p1)

        df_gen_mapped = self.srd_builder.build_gen_unit_outage_srd(df_node_srd.copy())
        df_gen_unit_out_srd = self.srd_builder.label_generator_outage_scenarios(df_gen_mapped)
        df_gen_unit_out_srd_updated = self.srd_builder.merge_partial_overlap_periods(df_gen_unit_out_srd)
        df_gen_unit_out_srd_final = self.srd_builder.update_generator_outage_records(df_gen_unit_out_srd_updated)
        self.srd_builder.update_must_run_generators_for_islands(df_gen_unit_out_srd_final)
        self.srd_builder.build_dc_tie_units_prop(df_node_srd.copy())
        logger.info("SRD building completed successfully!")


# ============================================================
# SRD MODEL IMPORTER
# ============================================================

class SRDImporter:
    """
    Imports SRD CSV property data into a PLEXOS model database (.db),
    then regenerates the XML model file.

    Uses low-level plexos_sdk (PLEXOSSDK) for DB operations and
    CloudSDK for DB-to-XML conversion.

    Pattern based on replace_model_input_files.py.
    """

    SRD_FILES = [
        'island_node_srd.csv',
        'island_gen_unit_out_srd.csv',
        'island_gen_must_run_srd.csv',
        'dc_tie_units_srd.csv',
    ]

    def __init__(self, model_path: str, cloud_cli_path: str, study_id: str,
                 simulation_path: str, model_name: str = None,
                 node_scenario: str = "Node off island script",
                 must_run_scenario: str = "PUN Must Run"):
        self.model_path = Path(model_path)
        self.cloud_cli_path = cloud_cli_path
        self.study_id = study_id
        self.simulation_path = simulation_path
        self.model_name = model_name
        self.node_scenario = node_scenario
        self.must_run_scenario = must_run_scenario
        # Caches populated during import
        self._collection_lang_ids: dict[str, int] = {}
        self._property_lang_ids: dict[tuple[str, str], int] = {}

    # ------------------------------------------------------------------
    # Name-to-lang-id discovery (direct SQLite queries, same as
    # replace_model_input_files.py)
    # ------------------------------------------------------------------

    def _discover_class_lang_id(self, class_name: str) -> int:
        query = """
        SELECT lang_id, name FROM t_class
        WHERE lower(name) = lower(?)
           OR lower(name) = lower(? || 's')
        ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, class_id
        LIMIT 1
        """
        with sqlite3.connect(str(self.model_path)) as conn:
            row = conn.execute(query, (class_name, class_name, class_name)).fetchone()
        if not row:
            raise ValueError(f"Class '{class_name}' not found in model.")
        lang_id, matched = row
        logger.info(f"  Resolved class '{matched}' -> lang_id={lang_id}")
        return int(lang_id)

    def _discover_collection_lang_id(self, collection_name: str) -> int:
        query = """
        SELECT lang_id, name FROM t_collection
        WHERE lower(name) = lower(?)
           OR lower(name) LIKE lower(?)
        ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, collection_id
        LIMIT 1
        """
        like_pattern = f"%{collection_name}%"
        with sqlite3.connect(str(self.model_path)) as conn:
            row = conn.execute(query, (collection_name, like_pattern, collection_name)).fetchone()
        if not row:
            raise ValueError(f"Collection '{collection_name}' not found in model.")
        lang_id, matched = row
        logger.info(f"  Resolved collection '{matched}' -> lang_id={lang_id}")
        return int(lang_id)

    def _discover_property_lang_id(self, collection_lang_id: int, property_name: str) -> int:
        query = """
        SELECT p.lang_id, p.name FROM t_property p
        JOIN t_collection col ON col.collection_id = p.collection_id
        WHERE col.lang_id = ?
          AND (lower(p.name) = lower(?) OR lower(p.name) LIKE lower(?))
        ORDER BY CASE WHEN lower(p.name) = lower(?) THEN 0 ELSE 1 END, p.property_id
        LIMIT 1
        """
        like_pattern = f"%{property_name}%"
        with sqlite3.connect(str(self.model_path)) as conn:
            row = conn.execute(
                query, (collection_lang_id, property_name, like_pattern, property_name)
            ).fetchone()
        if not row:
            raise ValueError(
                f"Property '{property_name}' not found in collection lang_id={collection_lang_id}."
            )
        lang_id, matched = row
        logger.info(f"  Resolved property '{matched}' -> lang_id={lang_id}")
        return int(lang_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_collection_lang_id(self, collection_name: str) -> int:
        if collection_name not in self._collection_lang_ids:
            self._collection_lang_ids[collection_name] = self._discover_collection_lang_id(
                collection_name
            )
        return self._collection_lang_ids[collection_name]

    def _get_property_lang_id(self, collection_name: str, property_name: str) -> int:
        key = (collection_name, property_name)
        if key not in self._property_lang_ids:
            coll_lang_id = self._get_collection_lang_id(collection_name)
            self._property_lang_ids[key] = self._discover_property_lang_id(
                coll_lang_id, property_name
            )
        return self._property_lang_ids[key]

    @staticmethod
    def _parse_oa_date(date_str):
        """Parse a date value for the SDK. Returns the date string as-is,
        or None if empty/NaN. The SDK handles conversion internally."""
        if pd.isna(date_str) or not str(date_str).strip():
            return None
        return str(date_str).strip()

    @staticmethod
    def _get_or_create_scenario(sdk, scenario_class_lang_id: int, name: str):
        """Get an existing Scenario object or create it if missing."""

        try:
            return sdk.get_object_by_name(scenario_class_lang_id, name)
        except ObjectNotFoundError:
            pass
        try:
            return sdk.add_object(class_lang_id=scenario_class_lang_id, object_name=name)
        except ObjectAlreadyExistsError:
            return sdk.get_object_by_name(scenario_class_lang_id, name)

    # ------------------------------------------------------------------
    # Scenario activation
    # ------------------------------------------------------------------

    def _enable_scenarios_on_model(self, model_name: str, scenario_cache):
        """
        Enable all imported scenarios on a specific Model object using
        direct SQL (avoids SDK add_membership API differences).
        """
        with sqlite3.connect(str(self.model_path)) as conn:
            # 1. Find the collection_id (and class IDs) for Model -> Scenario
            row = conn.execute("""
                SELECT col.collection_id, col.parent_class_id, col.child_class_id
                FROM t_collection col
                JOIN t_class pc ON pc.class_id = col.parent_class_id
                JOIN t_class cc ON cc.class_id = col.child_class_id
                WHERE lower(pc.name) = 'model' AND lower(cc.name) = 'scenario'
                LIMIT 1
            """).fetchone()
            if not row:
                logger.warning("Could not find Model->Scenario collection; scenarios not auto-enabled.")
                return
            collection_id = int(row[0])
            parent_class_id = int(row[1])
            child_class_id = int(row[2])

            # 2. Find the model object_id
            row = conn.execute("""
                SELECT o.object_id FROM t_object o
                JOIN t_class c ON c.class_id = o.class_id
                WHERE lower(c.name) = 'model' AND o.name = ?
            """, (model_name,)).fetchone()
            if not row:
                logger.warning(f"Model '{model_name}' not found in DB; scenarios not auto-enabled.")
                return
            model_object_id = int(row[0])
            logger.info(f"  Model '{model_name}' -> object_id={model_object_id}")

            # 3. For each scenario, insert membership if missing
            for scenario_name in scenario_cache:
                # Find scenario object_id
                row = conn.execute("""
                    SELECT o.object_id FROM t_object o
                    JOIN t_class c ON c.class_id = o.class_id
                    WHERE lower(c.name) = 'scenario' AND o.name = ?
                """, (scenario_name,)).fetchone()
                if not row:
                    logger.warning(f"  Scenario '{scenario_name}' not found in DB; skipping.")
                    continue
                scenario_object_id = int(row[0])

                # Check if membership already exists
                existing = conn.execute("""
                    SELECT membership_id FROM t_membership
                    WHERE collection_id = ?
                      AND parent_object_id = ?
                      AND child_object_id = ?
                """, (collection_id, model_object_id, scenario_object_id)).fetchone()
                if existing:
                    logger.info(f"  Scenario '{scenario_name}' already on Model '{model_name}'")
                    continue

                # Insert the membership (include class IDs — PLEXOS requires them)
                conn.execute("""
                    INSERT INTO t_membership
                        (parent_class_id, child_class_id, collection_id,
                         parent_object_id, child_object_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (parent_class_id, child_class_id, collection_id,
                       model_object_id, scenario_object_id))
                logger.info(f"  Enabled scenario '{scenario_name}' on Model '{model_name}'")

            conn.commit()

    # ------------------------------------------------------------------
    # Main import
    # ------------------------------------------------------------------

    def import_srd_files(self, srd_dir: str) -> bool:
        """
        Read all SRD CSV files from *srd_dir*, write their properties into
        the model DB, and regenerate the XML.

        Returns True on success, False on failure.
        """

        if not self.model_path.is_file():
            logger.error(f"Model file not found: {self.model_path}")
            return False

        # 1. Discover class lang_ids (one-time, via direct SQLite)
        logger.info("Discovering class/collection/property lang_ids ...")
        system_class_lang_id = self._discover_class_lang_id("System")
        scenario_class_lang_id = self._discover_class_lang_id("Scenario")

        # 2. Open SDK and process all SRD files in one transaction
        logger.info(f"Opening model: {self.model_path}")
        total_added = 0
        total_skipped = 0

        with PLEXOSSDK(str(self.model_path)) as sdk:
            with sdk.transaction():
                scenario_cache: dict[str, object] = {}  # name -> Object

                for srd_file in self.SRD_FILES:
                    csv_path = os.path.join(srd_dir, srd_file)
                    if not os.path.isfile(csv_path):
                        logger.warning(f"SRD file not found, skipping: {csv_path}")
                        continue

                    df = pd.read_csv(csv_path)
                    if df.empty:
                        logger.info(f"  {srd_file}: empty, skipping")
                        continue

                    # Only import rows tagged with OUR scenarios.
                    # gen_unit_out_srd and gen_must_run_srd contain existing
                    # model outages (e.g. "Unplanned Resource Outages") that
                    # must NOT be re-added — they are already in the DB.
                    if 'Scenario' in df.columns:
                        own_scenarios = {self.node_scenario, self.must_run_scenario}
                        before = len(df)
                        df = df[
                            df['Scenario'].fillna('').str.strip().isin(own_scenarios)
                        ].reset_index(drop=True)
                        if len(df) < before:
                            logger.info(
                                f"  Filtered {srd_file}: {before} -> {len(df)} rows "
                                f"(kept only {own_scenarios})"
                            )
                        if df.empty:
                            logger.info(f"  {srd_file}: no rows with own scenarios, skipping")
                            continue

                    logger.info(f"Processing {srd_file}: {len(df)} rows")
                    added = 0
                    skipped = 0

                    for _, row in df.iterrows():
                        child_name = str(row['Child Object'])
                        removed = False
                        try:
                            collection_name = str(row['Collection'])
                            parent_name = str(row['Parent Object'])
                            property_name = str(row['Property'])
                            value = float(row['Value'])
                            band_id = int(row['Band']) if pd.notna(row.get('Band')) else 1

                            # Resolve collection & property lang_ids (cached)
                            coll_lang_id = self._get_collection_lang_id(collection_name)
                            prop_lang_id = self._get_property_lang_id(
                                collection_name, property_name
                            )

                            # Resolve membership
                            membership = sdk.get_membership_by_names(
                                parent_class_lang_id=system_class_lang_id,
                                collection_lang_id=coll_lang_id,
                                parent_name=parent_name,
                                child_name=child_name,
                            )

                            # Resolve property object
                            property_obj = sdk.get_property(
                                parent_class_lang_id=system_class_lang_id,
                                collection_lang_id=coll_lang_id,
                                property_lang_id=prop_lang_id,
                            )

                            # Parse dates
                            date_from = self._parse_oa_date(row.get('Date From'))
                            date_to = self._parse_oa_date(row.get('Date To'))

                            # Resolve scenario (get or create)
                            scenario_obj = None
                            scenario_name = row.get('Scenario')
                            if pd.notna(scenario_name) and str(scenario_name).strip():
                                scenario_name = str(scenario_name).strip()
                                if scenario_name not in scenario_cache:
                                    scenario_cache[scenario_name] = (
                                        self._get_or_create_scenario(
                                            sdk, scenario_class_lang_id, scenario_name
                                        )
                                    )
                                scenario_obj = scenario_cache[scenario_name]

                            # Remove any existing assignment to avoid
                            # "defined multiple times" engine errors.
                            # Pass band_id to scope the removal.
                            try:
                                sdk.remove_property(
                                    membership=membership,
                                    property_obj=property_obj,
                                    band_id=band_id,
                                )
                                removed = True
                            except Exception:
                                pass  # nothing to remove — fine

                            # Add property to model
                            sdk.add_property(
                                membership=membership,
                                property_obj=property_obj,
                                value=value,
                                band_id=band_id,
                                date_from=date_from,
                                date_to=date_to,
                                scenario_tag=scenario_obj,
                            )
                            added += 1

                        except Exception as e:
                            if removed:
                                # add_property failed after remove_property
                                # succeeded — re-raise to abort the transaction
                                # rather than committing a partial deletion.
                                raise
                            logger.warning(f"  Skipped '{child_name}': {e}")
                            skipped += 1

                    logger.info(f"  {srd_file}: {added} added, {skipped} skipped")
                    total_added += added
                    total_skipped += skipped

                # Collect scenario names for enabling after SDK releases the DB
                scenario_names_to_enable = list(scenario_cache.keys()) if scenario_cache else []

        # 3. Enable scenarios on the target Model object (outside SDK context
        #    so the database is no longer locked by the SDK)
        if scenario_names_to_enable and self.model_name:
            logger.info(f"Enabling scenarios on Model '{self.model_name}'...")
            self._enable_scenarios_on_model(self.model_name, scenario_names_to_enable)

        logger.info(
            f"SRD import complete: {total_added} properties added, "
            f"{total_skipped} skipped"
        )

        # 3. Regenerate XML from modified DB
        if total_added > 0:
            return self._regenerate_xml()
        else:
            logger.warning("No properties were added — skipping XML regeneration.")
            return True

    # ------------------------------------------------------------------
    # DB -> XML conversion (pattern from replace_model_input_files.py)
    # ------------------------------------------------------------------

    def _regenerate_xml(self) -> bool:
        """
        Convert reference.db back to project.xml using CloudSDK.
        Backs up existing XML and restores on failure.
        """
        xml_path = Path(self.simulation_path) / "project.xml"
        backup_path = Path(str(xml_path) + ".bak")
        db_path = self.model_path

        logger.info(f"Regenerating XML: {db_path} -> {xml_path}")
        try:
            if xml_path.exists():
                os.rename(xml_path, backup_path)
                logger.info(f"  Backed up existing XML: {backup_path}")

            pxc = CloudSDK(cli_path=self.cloud_cli_path)
            response = pxc.inputdata.convert_database_to_xml(
                db_file_path=str(db_path),
                xml_file_path=str(xml_path),
                study_id=self.study_id,
                print_message=False,
            )

            result = SDKBase.get_response_data(response)
            if result is None:
                logger.error(f"DB-to-XML conversion failed: {response.Message}")
                if backup_path.exists():
                    os.rename(backup_path, xml_path)
                    logger.info(f"  Restored original XML from backup")
                return False

            if not xml_path.exists():
                logger.error("XML file was not created after conversion.")
                if backup_path.exists():
                    os.rename(backup_path, xml_path)
                    logger.info(f"  Restored original XML from backup")
                return False

            if backup_path.exists():
                os.remove(backup_path)

            logger.info(f"  XML regenerated successfully: {xml_path}")
            return True

        except Exception as exc:
            logger.error(f"XML regeneration failed: {exc}")
            if backup_path.exists():
                if xml_path.exists():
                    os.remove(xml_path)
                os.rename(backup_path, xml_path)
                logger.info(f"  Restored original XML from backup")
            return False


def _resolve_model_path() -> Path | None:
    """
    Resolve the PLEXOS model DB path from environment variables.
    Primary: simulation_path/reference.db
    Fallback: sqlite_input_path
    """
    simulation_path = os.environ.get("simulation_path", "/simulation")
    candidate = Path(simulation_path) / "reference.db"
    if candidate.is_file():
        return candidate

    sqlite_input_path = os.environ.get("sqlite_input_path")
    if sqlite_input_path:
        p = Path(sqlite_input_path)
        if p.is_file():
            return p

    return None


# ============================================================
# MAIN (Pre-Script Entry Point)
# ============================================================

def _normalize_date(raw, default_time='00:00'):
    """
    Normalize a date string that may arrive as:
      - '2025-03-01T00:00'  (ISO with T — preferred, no quoting needed)
      - '2025-03-01 00:00'  (space-separated, needs quoting on some shells)
      - '2025-03-01'        (date only — cloud platform may strip the time)
    Also handles nargs='+' list input: ['2025-03-01', '00:00'].
    Returns 'YYYY-MM-DD HH:MM'.
    """
    if isinstance(raw, list):
        raw = ' '.join(raw)
    raw = raw.strip().replace('T', ' ')
    if len(raw) == 10:  # date-only, e.g. '2025-03-01'
        raw = f"{raw} {default_time}"
    return raw


def parse_args():
    parser = argparse.ArgumentParser(
        description="Island Node Pre-Script for PLEXOS Cloud"
    )
    parser.add_argument(
        '--start-date', nargs='+', required=True,
        help="Analysis start date, e.g. 2025-03-01T00:00"
    )
    parser.add_argument(
        '--end-date', nargs='+', required=True,
        help="Analysis end date, e.g. 2025-09-02T23:00"
    )
    parser.add_argument(
        '--output-folder', required=True,
        help="DataHub remote folder for output files, e.g. IslandScript/outputs"
    )
    parser.add_argument(
        '--model-name', nargs='+', required=True,
        help="PLEXOS Model object name to enable scenarios on, e.g. WY2025 woPTC_hourly"
    )
    parser.add_argument(
        '--branch-data-file', nargs='+', required=True,
        help="DataHub path to branch outage CSV, e.g. IslandScript/inputs/Plexos Branch Data.csv"
    )
    parser.add_argument(
        '--network-data-file', nargs='+', required=True,
        help="DataHub path to network topology Excel, e.g. IslandScript/inputs/Network Branch Data.xlsx"
    )
    parser.add_argument(
        '--plexos-input-file', nargs='+', required=True,
        help="DataHub path to PLEXOS input Excel, e.g. IslandScript/inputs/Island Script data 0527.xlsx"
    )
    parser.add_argument(
        '--scenario', nargs='+', required=True,
        help="Scenario name for SRD entries, e.g. Node off island script"
    )
    parser.add_argument(
        '--default-from-date', default='12/1/2024 0:00',
        help="Default From Date for outages missing a start date (default: 12/1/2024 0:00)"
    )
    args = parser.parse_args()
    # Normalize dates (handles T-separator, date-only, and split tokens)
    args.start_date = _normalize_date(args.start_date, default_time='00:00')
    args.end_date = _normalize_date(args.end_date, default_time='23:00')
    # Join space-separated tokens (handles names/paths without quotes)
    args.model_name = ' '.join(args.model_name)
    args.branch_data_file = ' '.join(args.branch_data_file)
    args.network_data_file = ' '.join(args.network_data_file)
    args.plexos_input_file = ' '.join(args.plexos_input_file)
    args.scenario = ' '.join(args.scenario)
    return args


def main() -> int:
    """
    Pre-script entry point for PLEXOS cloud execution.

    Reads pipeline arguments from CLI, platform config from env vars,
    downloads inputs from DataHub, runs the island detection pipeline,
    writes outputs to output_path, and uploads results to DataHub.
    """
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # ------------------------------------------------------------------
    # 1. Read required platform environment variables (fail fast)
    # ------------------------------------------------------------------
    try:
        cloud_cli_path = os.environ["cloud_cli_path"]
    except KeyError:
        print("[FAIL] Required environment variable 'cloud_cli_path' is not set.")
        sys.exit(1)

    try:
        output_path = os.environ["output_path"]
    except KeyError:
        print("[FAIL] Required environment variable 'output_path' is not set.")
        sys.exit(1)

    try:
        study_id = os.environ["study_id"]
    except KeyError:
        print("[FAIL] Required environment variable 'study_id' is not set.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Resolve CLI arguments
    # ------------------------------------------------------------------
    start_date = args.start_date
    end_date = args.end_date
    default_from_date = args.default_from_date
    datahub_output_folder = args.output_folder
    scenario = args.scenario

    logger.info("=" * 60)
    logger.info("Island Node Pre-Script — Configuration")
    logger.info(f"  cloud_cli_path       = {cloud_cli_path}")
    logger.info(f"  output_path          = {output_path}")
    logger.info(f"  start_date           = {start_date}")
    logger.info(f"  end_date             = {end_date}")
    logger.info(f"  default_from_date    = {default_from_date}")
    logger.info(f"  datahub_output_folder= {datahub_output_folder}")
    logger.info(f"  branch_data_file     = {args.branch_data_file}")
    logger.info(f"  network_data_file    = {args.network_data_file}")
    logger.info(f"  plexos_input_file    = {args.plexos_input_file}")
    logger.info(f"  scenario             = {scenario}")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 2. Initialize CloudSDK
    # ------------------------------------------------------------------
    logger.info("Initializing CloudSDK...")
    pxc = init_cloud_sdk(cloud_cli_path)

    # ------------------------------------------------------------------
    # 3. Download input files from DataHub
    # ------------------------------------------------------------------
    local_input_dir = os.path.join(output_path, "_inputs")
    download_inputs_from_datahub(
        pxc,
        remote_files=[args.branch_data_file, args.network_data_file, args.plexos_input_file],
        local_dir=local_input_dir,
    )

    # Resolve local paths for the three input files (basename — flattened by download)
    branch_data = os.path.join(local_input_dir, os.path.basename(args.branch_data_file))
    network_data = os.path.join(local_input_dir, os.path.basename(args.network_data_file))
    plexos_input = os.path.join(local_input_dir, os.path.basename(args.plexos_input_file))

    for f in [branch_data, network_data, plexos_input]:
        if not os.path.isfile(f):
            logger.error(f"Expected input file not found after download: {f}")
            return 1

    # ------------------------------------------------------------------
    # 4. Run the island detection pipeline
    # ------------------------------------------------------------------
    logger.info("Running island detection pipeline...")
    pipeline = OptimizedPipeline(
        output_dir=output_path,
        branch_data=branch_data,
        network_data=network_data,
        plexos_input=plexos_input,
        start_date=start_date,
        end_date=end_date,
        default_from_date=default_from_date,
        node_scenario=scenario,
        must_run_scenario=scenario,
    )
    pipeline.run_complete_analysis()

    # ------------------------------------------------------------------
    # 5. Upload output files to DataHub (exclude _inputs/ staging dir)
    # ------------------------------------------------------------------
    upload_outputs_to_datahub(
        pxc, output_path, datahub_output_folder,
        glob_patterns=["*.csv", "*.parquet", "*.xlsx"],
    )

    # ------------------------------------------------------------------
    # 6. Apply SRD properties to model
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("Applying SRD properties to PLEXOS model...")
    logger.info("=" * 60)

    model_path = _resolve_model_path()
    if model_path is None:
        logger.error(
            "Cannot apply to model: no model DB found. "
            "Check simulation_path/reference.db or sqlite_input_path."
        )
        return 1

    simulation_path = os.environ.get("simulation_path", "/simulation")
    logger.info(f"  model_path      = {model_path}")
    logger.info(f"  simulation_path = {simulation_path}")
    logger.info(f"  study_id        = {study_id}")

    importer = SRDImporter(
        model_path=str(model_path),
        cloud_cli_path=cloud_cli_path,
        study_id=study_id,
        simulation_path=simulation_path,
        model_name=args.model_name,
        node_scenario=scenario,
        must_run_scenario=scenario,
    )

    if not importer.import_srd_files(srd_dir=output_path):
        logger.error("SRD model import failed.")
        return 1

    logger.info("SRD model import completed successfully!")

    # ------------------------------------------------------------------
    # 7. Upload modified model DB and XML to DataHub for verification
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("Uploading modified model DB and XML to DataHub...")
    logger.info("=" * 60)

    model_upload_dir = os.path.join(output_path, "_model_artifacts")
    os.makedirs(model_upload_dir, exist_ok=True)

    xml_path = Path(simulation_path) / "project.xml"
    for src_file in [model_path, xml_path]:
        if src_file.is_file():
            dst = os.path.join(model_upload_dir, src_file.name)
            shutil.copy2(str(src_file), dst)
            logger.info(f"  Copied {src_file} -> {dst}")
        else:
            logger.warning(f"  Model artifact not found, skipping: {src_file}")

    try:
        upload_outputs_to_datahub(
            pxc, model_upload_dir,
            f"{datahub_output_folder}/model_artifacts",
            glob_patterns=["**/*.db", "**/*.xml"],
        )
        logger.info("Model artifacts uploaded to DataHub successfully.")
    except Exception as exc:
        logger.warning(f"Failed to upload model artifacts to DataHub: {exc}")

    logger.info("Island Node Pre-Script completed successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
