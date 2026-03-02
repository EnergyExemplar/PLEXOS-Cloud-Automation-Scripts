"""
Convert Parquet files to CSV format.

This script can be run standalone OR imported by other automation scripts.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import pandas as pd


class ParquetCsvConverter:
    """Reusable Parquet to CSV converter for automation scripts."""
    
    @staticmethod
    def convert_file(parquet_path: Path, csv_path: Optional[Path] = None) -> Path:
        """
        Convert Parquet file to CSV format.
        
        Args:
            parquet_path: Path to input Parquet file
            csv_path: Path for output CSV file
            
        Returns:
            Path to output CSV file
        """
        parquet_path = Path(parquet_path)
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
        
        if csv_path is None:
            csv_path = parquet_path.with_suffix('.csv')
        else:
            csv_path = Path(csv_path)
        
        print(f"[CONVERT] Reading Parquet: {parquet_path}")
        df = pd.read_parquet(parquet_path)
        
        print(f"[CONVERT] Loaded {len(df):,} rows, {len(df.columns)} columns")
        print(f"[CONVERT] Writing CSV: {csv_path}")
        
        df.to_csv(csv_path, index=False)
        
        file_size = csv_path.stat().st_size
        print(f"[OK] Converted: {csv_path} ({file_size:,} bytes)")
        
        return csv_path
    
    @staticmethod
    def convert_directory(source_dir: Path, output_dir: Optional[Path] = None,
                         pattern: str = "*.parquet") -> List[Path]:
        """
        Convert multiple Parquet files to CSV format.
        
        Args:
            source_dir: Directory containing Parquet files
            output_dir: Output directory for CSV files
            pattern: Glob pattern for Parquet files
            
        Returns:
            List of converted CSV file paths
        """
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {source_dir}")

        explicit_output = output_dir is not None
        if explicit_output:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        parquet_files = list(source_dir.glob(pattern))
        if not parquet_files:
            print(f"[WARN] No Parquet files matching '{pattern}' in {source_dir}")
            return []

        print(f"[BATCH] Converting {len(parquet_files)} Parquet file(s) to CSV")

        converted = []
        for parquet_file in parquet_files:
            try:
                if explicit_output:
                    # Preserve relative subdirectory structure under output_dir
                    rel = parquet_file.relative_to(source_dir)
                    csv_file = output_dir / rel.with_suffix('.csv')
                    csv_file.parent.mkdir(parents=True, exist_ok=True)
                else:
                    # Write alongside the source Parquet file
                    csv_file = parquet_file.with_suffix('.csv')
                result = ParquetCsvConverter.convert_file(parquet_file, csv_file)
                converted.append(result)
            except Exception as ex:
                print(f"[SKIP] Failed to convert {parquet_file.name}: {ex}")
                continue
        
        print(f"[OK] Converted {len(converted)}/{len(parquet_files)} file(s)")
        return converted


def main() -> int:
    """
    Main entry point for command-line usage.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Convert Parquet files to CSV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert single file
  python parquet_to_csv.py -i input.parquet -o output.csv

  # Convert directory of Parquet files
  python parquet_to_csv.py --input-dir ./parquet_files --output-dir ./csv_files

  # Convert and upload to DataHub
  python parquet_to_csv.py -i input.parquet -o output.csv \\
    -c /usr/local/bin/plexos-cloud -e prod \\
    --upload Project/Study/Results
        '''
    )
    
    parser.add_argument('-i', '--input', help='Input Parquet file path')
    parser.add_argument('-o', '--output', help='Output CSV file path')
    parser.add_argument('--input-dir', help='Input directory containing Parquet files')
    parser.add_argument('--output-dir', help='Output directory for CSV files')
    parser.add_argument('--pattern', default='**/*.parquet', help='Glob pattern for Parquet files (default: **/*.parquet, recurses into subdirectories)')
    parser.add_argument('-c', '--cli-path', help='CLI path (required if using --upload)')
    parser.add_argument('-e', '--environment', help='Environment (required if using --upload)')
    parser.add_argument('--upload', help='Upload converted files to this DataHub path')
    
    args = parser.parse_args()
    
    if not args.input and not args.input_dir:
        print("❌ ERROR: Must specify either --input or --input-dir")
        return 1
    
    if args.upload and (not args.cli_path or not args.environment):
        print("❌ ERROR: --cli-path and --environment required when using --upload")
        return 1
    
    try:
        converted_files = []
        
        if args.input:
            print(f"[MODE] Single file conversion")
            result = ParquetCsvConverter.convert_file(
                Path(args.input),
                Path(args.output) if args.output else None
            )
            converted_files.append(result)
        
        elif args.input_dir:
            print(f"[MODE] Batch directory conversion")
            converted_files = ParquetCsvConverter.convert_directory(
                Path(args.input_dir),
                Path(args.output_dir) if args.output_dir else None,
                args.pattern
            )
        
        if not converted_files:
            print("❌ No files were converted")
            return 1
        
        if args.upload:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from UploadToDataHub.upload_to_datahub import DataHubUploader
            
            print(f"\n[UPLOAD] Uploading {len(converted_files)} file(s) to DataHub")
            uploader = DataHubUploader(cli_path=args.cli_path, environment=args.environment)
            
            for csv_file in converted_files:
                try:
                    uploader.upload_file(csv_file, args.upload, overwrite=True)
                except Exception as ex:
                    print(f"[ERROR] Failed to upload {csv_file.name}: {ex}")
        
        print(f"\n{'='*60}")
        print(f"[SUMMARY] Successfully converted {len(converted_files)} file(s)")
        for cfile in converted_files:
            print(f"  - {cfile.name}: {cfile.stat().st_size:,} bytes")
        print(f"{'='*60}\n")
        return 0
        
    except Exception as ex:
        print(f"\n❌ FATAL ERROR: {ex}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
