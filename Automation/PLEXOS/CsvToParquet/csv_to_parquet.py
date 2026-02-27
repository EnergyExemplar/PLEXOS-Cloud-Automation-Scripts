"""
Convert CSV files to Parquet format.

This script can be run standalone OR imported by other automation scripts.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import pandas as pd
import pyarrow.parquet as pq


class CsvParquetConverter:
    """Reusable CSV to Parquet converter for automation scripts."""
    
    @staticmethod
    def convert_file(csv_path: Path, parquet_path: Optional[Path] = None,
                    compression: str = 'zstd') -> Path:
        """
        Convert CSV file to Parquet format.
        
        Args:
            csv_path: Path to input CSV file
            parquet_path: Path for output Parquet file
            compression: Compression algorithm
            
        Returns:
            Path to output Parquet file
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        if parquet_path is None:
            parquet_path = csv_path.with_suffix('.parquet')
        else:
            parquet_path = Path(parquet_path)
        
        print(f"[CONVERT] Reading CSV: {csv_path}")
        df = pd.read_csv(csv_path)
        
        print(f"[CONVERT] Loaded {len(df):,} rows, {len(df.columns)} columns")
        print(f"[CONVERT] Writing Parquet with {compression} compression: {parquet_path}")
        
        df.to_parquet(parquet_path, compression=compression, index=False)
        
        file_size = parquet_path.stat().st_size
        print(f"[OK] Converted: {parquet_path} ({file_size:,} bytes)")
        
        return parquet_path
    
    @staticmethod
    def convert_directory(source_dir: Path, output_dir: Optional[Path] = None,
                         pattern: str = "*.csv", compression: str = 'zstd') -> List[Path]:
        """
        Convert multiple CSV files to Parquet format.
        
        Args:
            source_dir: Directory containing CSV files
            output_dir: Output directory for Parquet files
            pattern: Glob pattern for CSV files
            compression: Compression algorithm
            
        Returns:
            List of converted Parquet file paths
        """
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {source_dir}")
        
        if output_dir is None:
            output_dir = source_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_files = list(source_dir.glob(pattern))
        if not csv_files:
            print(f"[WARN] No CSV files matching '{pattern}' in {source_dir}")
            return []
        
        print(f"[BATCH] Converting {len(csv_files)} CSV file(s) to Parquet")
        
        converted = []
        for csv_file in csv_files:
            try:
                relative = csv_file.relative_to(source_dir)
                parquet_file = output_dir / relative.with_suffix('.parquet')
                parquet_file.parent.mkdir(parents=True, exist_ok=True)
                result = CsvParquetConverter.convert_file(csv_file, parquet_file, compression)
                converted.append(result)
            except Exception as ex:
                print(f"[SKIP] Failed to convert {csv_file.name}: {ex}")
                continue
        
        print(f"[OK] Converted {len(converted)}/{len(csv_files)} file(s)")
        return converted


def main() -> int:
    """
    Main entry point for command-line usage.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Convert CSV files to Parquet format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert single file
  python csv_to_parquet.py -i input.csv -o output.parquet

  # Convert directory of CSV files
  python csv_to_parquet.py --input-dir ./csv_files --output-dir ./parquet_files

  # Convert and upload to DataHub
  python csv_to_parquet.py -i input.csv -o output.parquet \\
    -c /usr/local/bin/plexos-cloud -e prod \\
    --upload Project/Study/Results
        '''
    )
    
    parser.add_argument('-i', '--input', help='Input CSV file path')
    parser.add_argument('-o', '--output', help='Output Parquet file path')
    parser.add_argument('--input-dir', help='Input directory containing CSV files')
    parser.add_argument('--output-dir', help='Output directory for Parquet files')
    parser.add_argument('--pattern', default='*.csv', help='Glob pattern for CSV files')
    parser.add_argument('--compression', choices=['zstd', 'gzip', 'snappy', 'none'], 
                       default='zstd', help='Compression algorithm')
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
            result = CsvParquetConverter.convert_file(
                Path(args.input), 
                Path(args.output) if args.output else None,
                args.compression
            )
            converted_files.append(result)
        
        elif args.input_dir:
            print(f"[MODE] Batch directory conversion")
            converted_files = CsvParquetConverter.convert_directory(
                Path(args.input_dir),
                Path(args.output_dir) if args.output_dir else None,
                args.pattern,
                args.compression
            )
        
        if not converted_files:
            print("❌ No files were converted")
            return 1
        
        if args.upload:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from UploadToDataHub.upload_to_datahub import DataHubUploader
            
            print(f"\n[UPLOAD] Uploading {len(converted_files)} file(s) to DataHub")
            uploader = DataHubUploader(cli_path=args.cli_path, environment=args.environment)
            
            upload_root = Path(args.output_dir) if args.output_dir else Path(args.input_dir) if args.input_dir else None
            
            for parquet_file in converted_files:
                try:
                    if upload_root and upload_root in parquet_file.parents:
                        relative_subdir = parquet_file.relative_to(upload_root).parent
                        datahub_path = '/'.join([args.upload.rstrip('/')] + [p for p in relative_subdir.parts if p])
                    else:
                        datahub_path = args.upload
                    uploader.upload_file(parquet_file, datahub_path, overwrite=True)
                except Exception as ex:
                    print(f"[ERROR] Failed to upload {parquet_file.name}: {ex}")
        
        print(f"\n{'='*60}")
        print(f"[SUMMARY] Successfully converted {len(converted_files)} file(s)")
        for pfile in converted_files:
            print(f"  - {pfile.name}: {pfile.stat().st_size:,} bytes")
        print(f"{'='*60}\n")
        return 0
        
    except Exception as ex:
        print(f"\n❌ FATAL ERROR: {ex}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
