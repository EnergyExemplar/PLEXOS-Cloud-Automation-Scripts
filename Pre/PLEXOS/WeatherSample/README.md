# Weather Sample – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Generates per-location weather sample CSV files from multi-year weather profile inputs. For each input profile CSV, this script reads climate-year data, applies day-of-week alignment to the simulation horizon, cycles through climate years sequentially, and writes one output CSV per location column under `ExoSampled/<file-stem>/`.

This is **Step 1 of 2** in the weather-year modeling workflow. The output files are consumed by `extend_weather_years.py` (Step 2) to register them into the PLEXOS model database.

### Key Features

1. Process one or more weather profile CSV files in a single run
2. Apply climate-year day-of-week alignment to the simulation horizon start date
3. Cycle climate years sequentially to cover multi-year simulation horizons
4. Handle Feb 29 leap-year fallback automatically (maps to Feb 28)
5. Try multiple CSV encodings automatically (`utf-8-sig`, `windows-1252`, `latin-1`, etc.)
6. Write per-location output CSVs with Year/Month/Day/Period metadata columns
7. URL-decode argument values and strip task-runner quotes for cloud execution

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** `../ExtendWeatherYears/extend_weather_years.py` (registers the generated CSVs into the PLEXOS model database as Step 2)

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--profiles-dir` | Yes | — | Folder containing weather profile CSV files. Resolved relative to `simulation_path` env var if set. |
| `--files` | Yes | — | One or more CSV file names (space-separated) inside `--profiles-dir` to process. Supports URL-encoded values such as `%20` for spaces. |
| `--profile-type` | No | `Weather` | Label string used in log output. |
| `--start-date` | No | `2025-10-01 00:00` | Simulation horizon start datetime (`YYYY-MM-DD HH:MM`). |
| `--end-date` | No | `2030-12-31 23:00` | Simulation horizon end datetime (`YYYY-MM-DD HH:MM`). |
| `--min-climate-year` | No | `1982` | Minimum climate year to include from the profile data. |
| `--max-climate-year` | No | `2016` | Maximum climate year to include from the profile data. |

---

## Environment Variables Used

| Variable | Description |
|---|---|
| `simulation_path` | Base path prepended to `--profiles-dir` when resolving the profiles directory. Defaults to `/simulation` if not set. |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
pandas
```

---

## Chaining This Script

### Chain 1 — Sample weather years (Step 1)

```json
{
  "Name": "Sample weather years",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/WeatherSample/sample_weather_years.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 WeatherSample/sample_weather_years.py --profiles-dir TimeSeries/Weather%20Profiles --files Offshore%20Wind%20Profiles%20CY1982+%20TY1.csv Onshore%20Wind%20Profiles%20CY1982+%20TY1.csv Solar%20Profiles%20CY1982+%20TY1.csv --min-climate-year 2006 --max-climate-year 2016",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

### Chain 2 — Extend weather years in model (Step 2)

```json
{
  "Name": "Register sampled weather files in PLEXOS model",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/ExtendWeatherYears/extend_weather_years.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 ExtendWeatherYears/extend_weather_years.py --study-id 8990056c-a5e8-4266-98e8-4a862543f399 --sampled-dir TimeSeries/ExoSampled --create-variables --variable-name-suffix _CY --link-variables --target-class-name Generator --scenario-name Weather_Variables_CY --scenario-read-order 50001 --adjust-stochastic --stochastic-object-name Weather_Stochastic --stochastic-parent-name i1000%20Play%20Book --stochastic-parent-category i1000 --start-year 2006 --end-year 2016",
  "ContinueOnError": false,
  "ExecutionOrder": 2
}
```

---

## Example Commands

```bash
# Minimal run: process a single profile file with default date range and climate years
python3 sample_weather_years.py --profiles-dir TimeSeries/Weather%20Profiles --files Solar%20Profiles%20CY1982+%20TY1.csv

# Process multiple files with custom climate year range and simulation dates
python3 sample_weather_years.py --profiles-dir TimeSeries/Weather%20Profiles --files Offshore%20Wind%20Profiles%20CY1982+%20TY1.csv Onshore%20Wind%20Profiles%20CY1982+%20TY1.csv Solar%20Profiles%20CY1982+%20TY1.csv --start-date "2025-10-01 00:00" --end-date "2030-12-31 23:00" --min-climate-year 2006 --max-climate-year 2016
```

When arguments are passed through the cloud task runner, surrounding quotes may be preserved as literal characters. This script strips surrounding single or double quotes before URL-decoding argument values, matching the behavior used by other `Pre` scripts.

---

## Output Artifacts

| Artifact | Location | Description |
|---|---|---|
| Per-location sample CSVs | `<profiles-dir>/../ExoSampled/<file-stem>/<location>.csv` | One CSV per location column, per input file. Contains Year/Month/Day/Period metadata plus one sample column per climate year. |

---

## Expected Behaviour

### Success

1. Resolves `profiles_dir` by joining `simulation_path` (if set) with `--profiles-dir`.
2. Validates the resolved directory exists.
3. Validates each file listed in `--files` exists inside `profiles_dir`.
4. For each input CSV file:
   - Reads the profile data, filters to climate years within `[--min-climate-year, --max-climate-year]`.
   - Pre-computes day-of-week-aligned date mappings for the full simulation horizon.
   - For each location column, generates one sample column per climate year.
   - Writes output to `ExoSampled/<file-stem>/<location>.csv`.
5. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `profiles_dir` not found | 1 | Verify `--profiles-dir` path or set `simulation_path` env var |
| Any file listed in `--files` not found | 1 | Verify file names and directory contents |
| No climate years in `[--min-climate-year, --max-climate-year]` range | 1 | Widen climate year range or check that profile CSV contains data in that range |
