import duckdb
import os
import datetime

def main():
    try:
        simulation_path = os.environ.get('simulation_path', "/simulation")
        output_path = os.environ.get('output_path', "/output") 
        duckFilePath = os.environ.get('duck_db_path', os.path.join(output_path, 'solution_views.ddb'))
            
        print('Starting DUCK')
        with duckdb.connect(duckFilePath) as con:

            query = f"""SELECT
                PhaseName, BandId, PeriodTypeName, 
                ChildObjectName, ChildObjectCategoryName, 
                ParentClassName, CollectionName, ChildClassName, PropertyName, UnitValue, TimesliceName, ModelName, SampleId, SampleName, d.PeriodId,
                Value
            FROM fullkeyinfo AS key
            INNER JOIN data d on d.SeriesId = key.SeriesId
            INNER JOIN Period p on p.PeriodId = d.PeriodId
            WHERE
                key.PeriodTypeName = 'Interval' AND
                key.PhaseName = 'ST' AND
                key.ParentClassName = 'System' 
                -- AND key.ChildClassName = 'Generator'
                AND key.PropertyName IN ('Load', 'Generation', 'Dump Energy', 'Price', 'Generation Capacity');"""

            con.sql(query).show()
            print('Exporting')
            
            today = datetime.date.today()
            date_string = today.strftime("%Y%m%d-%H%M%S")
            report_file_name = f"Report_{date_string}.parquet"
            output_parquet = os.path.join(output_path, report_file_name)
            con.execute(f"COPY ({query}) TO '{output_parquet}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 100_000);")
            
            print("done")
    except Exception as e:
        print(f"Failed to run query: {e}")

if __name__ == "__main__":
    main()
