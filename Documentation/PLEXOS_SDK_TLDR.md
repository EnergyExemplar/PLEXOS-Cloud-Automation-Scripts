<!--ALWAYS refer to SDK_METHODS.md to ensure examples are accurate and show correct parameters. Ensure SDK_METHODS.md is accurate and up to date. STOP and ask if you have a question-->
# PLEXOS SDK - TLDR Quick Reference

## 📋 Table of Contents
- [PLEXOS SDK - TLDR Quick Reference](#plexos-sdk---tldr-quick-reference)
  - [📋 Table of Contents](#-table-of-contents)
  - [🚀 Installation \& Setup](#-installation--setup)
  - [🔄 Transactions](#-transactions)
  - [🏗️ Hydrated Models](#️-hydrated-models)
  - [🔧 Basic Usage](#-basic-usage)
  - [📋 Core Operations](#-core-operations)
    - [Objects](#objects)
    - [Attributes](#attributes)
      - [Method 1: Using Attribute Objects (Recommended for bulk operations)](#method-1-using-attribute-objects-recommended-for-bulk-operations)
      - [Method 2: Using Lang IDs (Simpler for single assignments but has to make extra database calls so inefficient for loops and bulk operations)](#method-2-using-lang-ids-simpler-for-single-assignments-but-has-to-make-extra-database-calls-so-inefficient-for-loops-and-bulk-operations)
    - [Memberships](#memberships)
    - [Properties](#properties)
      - [Properties do not have 2 different methods like attributes, but may be included in future versions if requested.](#properties-do-not-have-2-different-methods-like-attributes-but-may-be-included-in-future-versions-if-requested)
    - [Report Configuration](#report-configuration)
    - [Categories](#categories)
  - [⏰ Time Management](#-time-management)
    - [Horizons](#horizons)
    - [Date Utilities](#date-utilities)
  - [🚀 Quick Start Example](#-quick-start-example)
  - [🗄️ Database Management](#️-database-management)
    - [Creating Databases](#creating-databases)
      - [Advanced feature to start a new empty database.](#advanced-feature-to-start-a-new-empty-database)
  - [🎯 Enum Generation](#-enum-generation)
    - [Python API](#python-api)
    - [CLI Tools](#cli-tools)
  - [🌱 Seed Data Management](#-seed-data-management)
    - [SQL-Based Seed Data](#sql-based-seed-data)
    - [Zip Package Management](#zip-package-management)
  - [🖥️ Command Line Tools](#️-command-line-tools)
  - [🎯 Data Enums/Identifiers](#-data-enumsidentifiers)
  - [🔍 Query Methods](#-query-methods)
  - [🔧 Error Handling](#-error-handling)
  - [📚 Common Patterns](#-common-patterns)
  - [⚠️ Important Notes](#️-important-notes)
    - [Data Integrity](#data-integrity)
    - [Performance](#performance)
    - [Limitations](#limitations)
    - [Date Ranges](#date-ranges)
<div style="page-break-after: always;"></div>

## 🚀 Installation & Setup

```bash
# Install locally
pip install plexos_sdk-*.whl
```

## 🔄 Transactions

**Recommended to use transactions for ALL inserts or updates. This ensures your changes are all valid, or nothing is updated. This reduces chance of corrupting data**

```python
# Use transactions for data integrity
with sdk.transaction():
    sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")
    sdk.add_membership(collection=collection_obj, parent=system_obj, child=generator_obj)
    # All operations succeed or fail together
```

## 🏗️ Hydrated Models

**All SDK methods return fully hydrated ORM models, not just IDs or raw data.** This means:

- **Object operations** return `Object` models with all properties and relationships loaded
- **Property operations** return `Data` models linked to their `Membership` and `Property` 
- **Attribute operations** return `AttributeData` models linked to their `Object` and `Attribute`
- **Collection queries** return `List[Collection]`, `List[Property]`, etc. with full model access
- **Type hints shown** in examples indicate the exact model type returned

```python
# Example: All return fully hydrated models you can immediately use
system: Object = sdk.get_object_by_name(ClassEnum.System, "System")
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="WindFarm1")
membership: Membership = sdk.add_membership(collection, system, generator)  
data: Data = sdk.add_property(membership, property_obj, 500.0)  # Returns hydrated Data with relationships loaded

# Access model properties directly
print(f"Generator: {generator.name}, Class: {generator.class_ref.name}")
print(f"Property Value: {data.value}, Property: {data.property_ref.name}")

# NEW: Access text and tag relationships directly (if created)
if data.texts:
    print(f"Data File Text: {data.texts[0].value}")
if data.tags:
    print(f"Data File Tag: {data.tags[0].object_ref.name}")
```
<div style="page-break-after: always;"></div>
## 🔧 Basic Usage

```python
from plexos_sdk import PLEXOSSDK
from plexos_sdk.models.plexos_models import * # access to all classes
from plexos_sdk.exceptions import * # access to any custom exceptions
#domain/version specific enum.py file
from electric_enums import * # access to ENUMS

# Connect to database
with PLEXOSSDK("my_model.db") as sdk:
    try:
        with sdk.transaction():
            # All write/update operations go here. read/query also acceptable but not required
            sdk.create_something_fantastic()
        
        # Any read/query operations go here (outside transaction)
        sdk.read_interesting_data()

    except Exception as e:
        print(f"Operations failed: {e}")
        import traceback
        traceback.print_exc()
        return
```
<div style="page-break-after: always;"></div>

## 📋 Core Operations

### Objects
```python
# Add object (automatically adds to System membership) -> returns Object model
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")

# Add object with category object (recommended)
category: Category = sdk.get_category_by_name(ClassEnum.Generator, "Wind")
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1", category_obj=category, description="Wind generator")

# Add object with category name (legacy)
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1", category_name="Wind", description="Wind generator")

# Get object -> returns Object model
obj: Object = sdk.get_object_by_name(class_lang_id=ClassEnum.Generator, object_name="Generator1")

# Remove object -> returns bool
success: bool = sdk.remove_object_by_name(class_lang_id=ClassEnum.Generator, object_name="Generator1")
```
<div style="page-break-after: always;"></div>

### Attributes

#### Method 1: Using Attribute Objects (Recommended for bulk operations)
```python
# Get attribute object first -> returns Attribute 
attribute_obj: Attribute = sdk.get_attribute(
    class_lang_id=ClassEnum.Generator, 
    attribute_lang_id=AttributeEnum_Generator.MaxOutput
)

# Add attribute using object -> returns AttributeData
attr_data: AttributeData = sdk.add_attribute(object_obj=generator_obj, attribute=attribute_obj, value=600.0)

# Get attribute value -> returns float value
value: float = sdk.get_attribute_value(object_obj=generator_obj, attribute=attribute_obj)
```

#### Method 2: Using Lang IDs (Simpler for single assignments but has to make extra database calls so inefficient for loops and bulk operations)
```python
# Add attribute using lang_id (simpler for single assignments) -> returns AttributeData
attr_data: AttributeData = sdk.add_attribute_by_lang_id(
    object_obj=generator_obj, 
    attribute_lang_id=AttributeEnum_Generator.MaxOutput, 
    value=600.0
)

# Get attribute value by IDs -> returns float value
value: float = sdk.get_attribute_value_by_ids(
    class_lang_id=ClassEnum.Generator, 
    object_name="Generator1", 
    attribute_lang_id=AttributeEnum_Generator.MaxOutput
)
```

<div style="page-break-after: always;"></div>

### Memberships
```python
# Add object with automatic System membership -> returns Object
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")  # System membership is always created

# Add membership (parent -> child) -> returns Membership
membership: Membership = sdk.add_membership(collection=collection_obj, parent=parent_obj, child=child_obj)

# Remove membership -> returns bool
success: bool = sdk.remove_membership(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName", child_name="ChildName")

# Get memberships -> returns model lists
parents: List[Object] = sdk.get_parent_members(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, child_name="ChildName")
children: List[Object] = sdk.get_child_members(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName")
memberships: List[Membership] = sdk.get_child_memberships(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName")
```
<div style="page-break-after: always;"></div>

### Properties 
#### Flexible property specification with automatic text/tag creation
```python
# Basic property (backward compatible) -> returns hydrated Data
data: Data = sdk.add_property(membership=membership, property_obj=property_obj, value=value, band_id=1)

# Property with flexible specification (Property object, lang_id, or name)
data: Data = sdk.add_property(membership=membership, property_spec=PropertyEnum_Generators.MaxOutput, value=500.0)
data: Data = sdk.add_property(membership=membership, property_spec=123, value=500.0)  # Using lang_id
data: Data = sdk.add_property(membership=membership, property_spec="MaxOutput", value=500.0)  # Using name

# Property with date range -> returns hydrated Data
data: Data = sdk.add_property(membership=membership, property_obj=property_obj, value=value, 
                date_from="2030-01-01T00:00:00", 
                date_to="2030-12-31T00:00:00")

# Property with automatic text creation (NEW - no need to create Text objects manually)
data: Data = sdk.add_property(membership=membership, property_obj=property_obj, value=value,
                data_file_text="path/to/data.csv",  # Auto-creates Text for data file
                time_slice_text="M7-12")  # Auto-creates Text for time slice (July-December)

# Property with automatic tag creation (NEW - no need to create Tag objects manually)
data: Data = sdk.add_property(membership=membership, property_obj=property_obj, value=value,
                data_file_tag=data_file_obj,  # Auto-creates Tag for data file
                scenario_tag=scenario_obj,  # Auto-creates Tag for scenario
                expression_tag=expression_obj)  # Auto-creates Tag for expression

# Combined example with multiple features
data: Data = sdk.add_property(
    membership=membership, 
    property_spec=PropertyEnum_Generators.MaxOutput,
    value=500.0,
    data_file_text="wind_data.csv",
    time_slice_text="M1-6",  # January-June
    data_file_tag=data_file_obj,
    band_id=2,
    date_from="2030-01-01T00:00:00",
    date_to="2030-06-30T00:00:00"
)

# Get property value -> returns float value
value: float = sdk.get_property_value(membership=membership, property_obj=property_obj)

# Update property -> returns updated Data model
updated_data: Data = sdk.update_property(membership=membership, property_obj=property_obj, value=new_value)

# Remove property -> returns bool
success: bool = sdk.remove_property(membership=membership, property_obj=property_obj)
```
<div style="page-break-after: always;"></div>

### Report Configuration
```python
# Create a Report object first -> returns Object
report_object: Object = sdk.add_object(class_lang_id=ClassEnum.Report, object_name="TestReport")

# Configure report attributes (what types of output to generate) -> returns AttributeData
attr1: AttributeData = sdk.add_attribute_by_lang_id(report_object, AttributeEnum_Report.OutputResultsByHour, -1)
attr2: AttributeData = sdk.add_attribute_by_lang_id(report_object, AttributeEnum_Report.OutputResultsByDay, -1)
attr3: AttributeData = sdk.add_attribute_by_lang_id(report_object, AttributeEnum_Report.OutputStatistics, -1)
attr4: AttributeData = sdk.add_attribute_by_lang_id(report_object, AttributeEnum_Report.OutputResultsBySample, -1)

# Add report configuration for selected reporting properties
reporting_lang_ids = [
    ReportingEnum_Generators.Generation,
    ReportingEnum_Generators.GenerationCost,
    ReportingEnum_Generators.NetRevenue,
    ReportingEnum_Fuels.Cost,
    ReportingEnum_Batteries.Load,
    ReportingEnum_Batteries.Soc
]

for reporting_lang_id in reporting_lang_ids:
    # Add report configuration -> returns Report
    report_config: Report = sdk.add_report_configuration(
        object_obj=report_object,
        reporting_lang_id=reporting_lang_id,
        phase_id=4,
        report_period=True,
        report_samples=True,
        report_statistics=True,
        report_summary=True,
        write_flat_files=False
    )

```
<div style="page-break-after: always;"></div>

### Categories
```python
# Add category -> returns Category
category: Category = sdk.add_category(class_lang_id=ClassEnum.Generator, category_name="Wind", description="Wind generators")

# Get category by name -> returns Category
category: Category = sdk.get_category_by_name(class_lang_id=ClassEnum.Generator, category_name="Wind")

# Get all categories for a class -> returns list of Categories
categories: List[Category] = sdk.get_categories(class_lang_id=ClassEnum.Generator)

# Add object to category -> returns bool
success: bool = sdk.add_object_category(class_lang_id=ClassEnum.Generator, object_name="Generator1", category_name="Wind")

# Get objects in category -> returns list of Objects
objects: List[Object] = sdk.get_objects_in_category(class_lang_id=ClassEnum.Generator, category_name="Wind")
```

## ⏰ Time Management

### Horizons
Horizons define simulation time periods. Common step types: 1=Day, 2=Week, 3=Month, 4=Year.

```python
from datetime import datetime

# Create monthly horizon -> returns Object (Horizon class)
horizon: Object = sdk.create_horizon(
    name="2024 Monthly", date_from=datetime(2024, 1, 1), step_count=12, step_type=3, description="MonthlyHorizon for 2024")

# List all horizons -> returns list of Objects
horizons: List[Object] = sdk.list_all_horizons()
```

### Date Utilities
```python
from plexos_sdk import to_oa_date, from_oa_date

# Convert between Python datetime and PLEXOS format
oa_date = to_oa_date(datetime(2024, 1, 1))
dt = from_oa_date(44927.0)
```
<div style="page-break-after: always;"></div>

## 🚀 Quick Start Example

Complete workflow using core SDK functionality:

```python
from plexos_sdk import PLEXOSSDK
from electric_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators, AttributeEnum_Generator
from datetime import datetime

# Work with existing database
with PLEXOSSDK("my_model.db") as sdk:
    with sdk.transaction():
        # 1. Create time horizon -> returns Object (Horizon class)
        horizon: Object = sdk.create_horizon(
            name="2024 Analysis",
            date_from=datetime(2024, 1, 1),
            step_count=12,
            step_type=3  # Monthly
        )
        
        # 2. Add generator with category -> returns models
category: Category = sdk.add_category(ClassEnum.Generator, "Wind", "Wind generators")
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="WindFarm1", category_obj=category)
        
        # 3. Add attributes (object-level settings) -> returns AttributeData
attr_data: AttributeData = sdk.add_attribute_by_lang_id(generator, AttributeEnum_Generator.MaxOutput, 600.0)
        
        # 4. Add properties (membership-level settings) -> returns hydrated Data models
membership: Membership = sdk.get_membership_by_child_name(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators, parent_name="System", child_name="WindFarm1")

# Method 1: Using Property object (traditional)
capacity_prop: Property = sdk.get_property(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators, property_lang_id=PropertyEnum_Generators.Capacity)
data: Data = sdk.add_property(membership, capacity_prop, 500.0)

# Method 2: Using flexible property specification (NEW)
data: Data = sdk.add_property(membership, PropertyEnum_Generators.Capacity, 500.0)  # Using enum
data: Data = sdk.add_property(membership, "Capacity", 500.0)  # Using property name
data: Data = sdk.add_property(membership, 123, 500.0)  # Using lang_id

# Method 3: With automatic text/tag creation (NEW)
data: Data = sdk.add_property(
    membership, 
    PropertyEnum_Generators.Capacity, 
    500.0,
    data_file_text="wind_capacity.csv",
    time_slice_text="M1-12",  # January-December
    data_file_tag=data_file_obj
)
```

> **Pro Tip:** For database creation and enum generation, see [Database Management](#-database-management) and [Enum Generation](#-enum-generation) sections.
<div style="page-break-after: always;"></div>

## 🗄️ Database Management

### Creating Databases
#### Advanced feature to start a new empty database. 
```python
from plexos_sdk import SeedDataManager

# Create new database using SQL-based seed data
with SeedDataManager("source_database.db") as manager:
    # Generate SQL scripts for all system types
    results = manager.generate_seed_data_sql("sql_output/")
    
    # Create database from SQL script
    manager.create_database("my_model.db", "electric", results["electric"])
```

## 🎯 Enum Generation

Generate type-safe enums for your domain to get better IDE support and validation.

### Python API
```python
from plexos_sdk import generate_enums_from_database

# Generate enums from your database
enums = generate_enums_from_database(
    database_path="my_database.db",
    domain_name="electric",
    output_dir="my_enums/"
)

# Use generated enums
from my_enums.electric_enums import ClassEnum, PropertyEnum_Generators
generator = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="WindFarm1")
```
<div style="page-break-after: always;"></div>

### CLI Tools
```bash
# Generate enums with auto-detected domain
python -m plexos_sdk.enum_generator my_database.db --output enums/

# Generate enums for specific domain
python -m plexos_sdk.enum_generator my_database.db --domain electric --output enums/

# Generate enums with analysis report
python -m plexos_sdk.enum_generator my_database.db --domain gas --output enums/ --analysis
```

## 🌱 Seed Data Management

### SQL-Based Seed Data
Modern approach using human-readable SQL scripts:

```python
from plexos_sdk import SeedDataManager

# Extract seed data to SQL scripts
with SeedDataManager("source_database.db") as manager:
    # Generate SQL scripts for all system types
    results = manager.generate_seed_data_sql("sql_output/")
    
    # Create database from SQL script
    manager.create_database("new_model.db", "electric", results["electric"])
```

### Zip Package Management
Create versioned zip files for distribution:

```python
from plexos_sdk import SeedDataManager

# Generate zip package with SQL scripts
with SeedDataManager("source_database.db") as manager:
    manager.generate_seed_data_zip(
        "seeddata.zip", 
        ["electric", "gas", "water"], 
        "11.03.75"
    )
    
    # Create database from zip package
    manager.create_database_from_zip(
        "new_model.db", 
        "seeddata.zip", 
        "electric", 
        "11.03.75"
    )
```

## 🖥️ Command Line Tools

```bash
# Database creation
plexos-sdk create-db my_model.db

# SQL-based seed data (new approach)
plexos-sdk extract-sql source.db sql_output/
plexos-sdk create-from-sql source.db new_model.db electric
plexos-sdk package-sql source.db seeddata.zip

# Enum generation
python -m plexos_sdk.enum_generator my_database.db --output enums/

# List available sources
plexos-sdk list-sources

# Legacy commands (deprecated)
plexos-sdk generate-seed-data source_path output.zip --overwrite
```
<div style="page-break-after: always;"></div>

## 🎯 Data Enums/Identifiers

The SDK supports enums for better developer experience. Import domain-specific enums for type safety and IDE support.

```python
# Import domain-specific enums
from electric_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators, PropertyEnum_Fuels, AttributeEnum_Generator

# Use enums instead of IDs -> returns models
generator: Object = sdk.add_object(
    class_lang_id=ClassEnum.Generator, 
    object_name="WindFarm1", 

)
properties: List[Property] = sdk.get_properties_by_collection(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators)
memberships: List[Membership] = sdk.get_memberships_by_collection(parent_class_lang_id=ClassEnum.Generator, collection_lang_id=CollectionEnum.Fuels)
```

## 🔍 Query Methods

```python
# Get all objects of a class -> returns list of Object models
objects: List[Object] = sdk.get_objects(class_lang_id=ClassEnum.Generator)

# Get all memberships for a collection -> returns list of Membership models
memberships: List[Membership] = sdk.get_memberships_by_collection(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators)

# Get enabled properties -> returns list of property names
properties: List[str] = sdk.get_enabled_properties()

# Get object membership count -> returns dict with counts
counts: dict = sdk.get_object_membership_count(class_lang_id=ClassEnum.Generator, object_name="ObjectName")

# Collection retrieval -> returns Collection models
collection: Collection = sdk.get_collection(parent_class_lang_id=ClassEnum.Generator, collection_lang_id=CollectionEnum.Companies)  # Generator → Company
collection: Collection = sdk.get_collection(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators)   # System → Generator
```

<div style="page-break-after: always;"></div>

## 🔧 Error Handling

```python
from plexos_sdk.exceptions import (
    InvalidObjectNameError, ObjectNotFoundError, SystemObjectError,
    ClassNotFoundError, CollectionDisabledError, ValidationError,
    InvalidDateError, PropertyAlreadyExistsError, AttributeAlreadyExistsError,
    MembershipAlreadyExistsError, CategoryAlreadyExistsError,
    InvalidLangIdError, TextValidationError, TagValidationError,
    InvalidStepTypeError, InvalidStepCountError, HorizonError
)

# Handle specific errors with descriptive messages
try:
    generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Invalid@Name")
except InvalidObjectNameError as e:
    print(f"Invalid name: {e}")  # Clear, actionable error message

try:
    data: Data = sdk.add_property(membership, property_obj, 100.0, date_from="invalid-date")
except InvalidDateError as e:
    print(f"Date error: {e}")  # Descriptive error with expected format

try:
    duplicate_property: Data = sdk.add_property(membership, property_obj, 200.0)
except PropertyAlreadyExistsError as e:
    print(f"Property exists: {e}")  # Clear duplication error

# Handle entity not found errors
try:
    obj: Object = sdk.get_object_by_name(ClassEnum.Generator, "NonExistentGenerator")
except ObjectNotFoundError as e:
    print(f"Object not found: {e}")  # Clear error message

try:
    collection: Collection = sdk.get_collection(ClassEnum.System, 99999)  # Invalid collection
except CollectionNotFoundError as e:
    print(f"Collection not found: {e}")  # Clear error message
```
<div style="page-break-after: always;"></div>

## 📚 Common Patterns

```python
from plexos_sdk.models.plexos_models import Text, Tag

# Complete workflow with horizon and object creation
with sdk.transaction():
    # 1. Create horizon for the simulation -> returns Object (Horizon class)
    horizon: Object = sdk.create_horizon(name="2024-2025 Analysis", date_from=datetime(2024, 1, 1), step_count=24, step_type=3, description="24-month analysis period")
    
    # 2. Add object (automatically adds to System membership) -> returns Object
wind_farm_obj: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="WindFarm1", category_name="Wind", description="Wind farm")
    
    # Get the membership that was automatically created -> returns Membership model
membership: Membership = sdk.get_membership_by_child_name(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators, parent_name="System", child_name="WindFarm1"))

    # Basic capacity property (traditional method) -> returns hydrated Data models
capacity_prop: Property = sdk.get_property(parent_class_lang_id=ClassEnum.System, collection_lang_id=CollectionEnum.Generators, property_lang_id=PropertyEnum_Generators.Capacity)
capacity_data: Data = sdk.add_property(membership=membership, property_obj=capacity_prop, value=500.0)

# Property with flexible specification (NEW) -> returns hydrated Data models
capacity_data: Data = sdk.add_property(membership=membership, property_spec=PropertyEnum_Generators.Capacity, value=500.0)
capacity_data: Data = sdk.add_property(membership=membership, property_spec="Capacity", value=500.0)

# Property with automatic text creation (NEW) -> returns hydrated Data models
availability_data: Data = sdk.add_property(
    membership=membership, 
    property_spec=PropertyEnum_Generators.Availability, 
    value=0.95,
    data_file_text="availability_data.csv",
    time_slice_text="M7-12"  # July-December
)

# Property with automatic tag creation and date range (NEW) -> returns hydrated Data models
fuel_cost_data: Data = sdk.add_property(
    membership=membership, 
    property_spec=PropertyEnum_Generators.FuelCost, 
    value=45.0,
    data_file_tag=data_file_obj,
    date_from="2030-01-01T00:00:00"
)

# Add attributes -> returns Attribute and AttributeData
max_output_attr: Attribute = sdk.get_attribute(class_lang_id=ClassEnum.Generator, attribute_lang_id=AttributeEnum_Generator.MaxOutput)
attr_data: AttributeData = sdk.add_attribute(object_obj=wind_farm_obj, attribute=max_output_attr, value=600.0)
```

<div style="page-break-after: always;"></div>


## ⚠️ Important Notes

### Data Integrity
- **Always use transactions** for multiple operations
- **Memberships cannot be edited** - delete and recreate if needed
- **Object names** are case-sensitive and unique within class. Additional validation is performed against a REGEX to conform to web security practices.

### Performance
- **Use enums** for better IDE support and type safety
- **Batch operations** in single transactions
- **Validate object names** before creation

### Limitations
- **Seed data** (classes, collections) cannot be modified
- **Properties/Attributes** must match collection/class IDs
- **Date ranges** require ISO format: `"2024-01-01T00:00:00"`

### Date Ranges
- **Format**: ISO format `"2030-01-01T00:00:00"`
- **Independent**: Can use `date_from` or `date_to` separately
- **Validation**: `date_from` ≤ `date_to` when both provided

### Property Management (NEW Features)
- **Flexible Specification**: `add_property` accepts Property objects, lang_ids, or property names
- **Automatic Text Creation**: Use `data_file_text` and `time_slice_text` parameters to auto-create Text objects
- **Automatic Tag Creation**: Use `data_file_tag`, `scenario_tag`, and `expression_tag` parameters to auto-create Tag objects
- **Hydrated Returns**: `add_property` returns fully hydrated Data objects with relationships loaded
- **Backward Compatible**: Old signature still works for existing code