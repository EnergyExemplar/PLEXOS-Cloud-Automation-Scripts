<!--ALWAYS refer to SDK_METHODS.md to ensure examples are accurate and show correct parameters. Ensure SDK_METHODS.md is accurate and up to date. STOP and ask if you have a question-->
# PLEXOS SDK - TLDR Quick Reference

## 📋 Table of Contents
- [PLEXOS SDK - TLDR Quick Reference](#plexos-sdk---tldr-quick-reference)
  - [📋 Table of Contents](#-table-of-contents)
  - [🚀 Installation \& Setup](#-installation--setup)
  - [🔄 Transactions](#-transactions)
      - [Manual Transaction Control](#manual-transaction-control)
  - [🏗️ Hydrated Models](#️-hydrated-models)
  - [🔧 Basic Usage](#-basic-usage)
  - [📋 Core Operations](#-core-operations)
    - [Objects](#objects)
    - [Attributes](#attributes)
      - [Method 1: Using Attribute Objects (Recommended for bulk operations)](#method-1-using-attribute-objects-recommended-for-bulk-operations)
      - [Method 2: Using Lang IDs (Simpler for single assignments but has to make extra database calls so inefficient for loops and bulk operations)](#method-2-using-lang-ids-simpler-for-single-assignments-but-has-to-make-extra-database-calls-so-inefficient-for-loops-and-bulk-operations)
      - [Update \& Remove Attributes](#update--remove-attributes)
    - [Memberships](#memberships)
    - [Properties](#properties)
    - [Memos](#memos)
      - [Data Memos](#data-memos)
      - [Membership Memos](#membership-memos)
      - [Object Memos (Custom Columns)](#object-memos-custom-columns)
    - [Categories](#categories)
  - [🛠️ Helpers \& Utilities](#️-helpers--utilities)
    - [Horizons](#horizons)
    - [Date Utilities](#date-utilities)
    - [Report Configuration](#report-configuration)
  - [🚀 Quick Start Example](#-quick-start-example)
  - [🗄️ Database Management](#️-database-management)
    - [XML Conversion](#xml-conversion)
  - [⚙️ Database Configuration](#️-database-configuration)
  - [🔍 Database Validation](#-database-validation)
  - [🎯 Enum Generation](#-enum-generation)
    - [From SDK (preferred — no separate step)](#from-sdk-preferred--no-separate-step)
    - [From CLI](#from-cli)
  - [🎯 Data Enums/Identifiers](#-data-enumsidentifiers)
  - [🔍 Query Methods](#-query-methods)
  - [🔧 Error Handling](#-error-handling)
  - [📚 Common Patterns](#-common-patterns)
  - [🌱 Seed Data Management](#-seed-data-management)
    - [Why Seed Data?](#why-seed-data)
    - [How Seed Data Is Produced](#how-seed-data-is-produced)
      - [Step-by-Step: Building a Seed Data Package](#step-by-step-building-a-seed-data-package)
    - [Creating Databases from Seed Data](#creating-databases-from-seed-data)
    - [Additional CLI Commands](#additional-cli-commands)
  - [⚠️ Important Notes](#️-important-notes)
    - [Automatic System Relationships](#automatic-system-relationships)
    - [Property Duplicate Detection](#property-duplicate-detection)
    - [Data Integrity](#data-integrity)
    - [Performance](#performance)
    - [Limitations](#limitations)
    - [Date Ranges](#date-ranges)



## 🚀 Installation & Setup

```bash
# Install locally
pip install plexos_sdk-*.whl
```

## 🔄 Transactions

**Recommended to use transactions for ALL inserts or updates. This ensures your changes are all valid, or nothing is updated. This reduces chance of corrupting data**

```python
# Use transactions for data integrity (recommended — auto-commits on success, auto-rolls back on error)
with sdk.transaction():
    sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")
    sdk.add_membership(collection=collection_obj, parent=system_obj, child=generator_obj)
    # All operations succeed or fail together
```

#### Manual Transaction Control
The context manager auto-commits when the `with` block exits successfully. For advanced scenarios you can commit or rollback manually:

```python
# Manual commit (rarely needed — the context manager commits automatically)
with sdk.transaction():
    sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")
    sdk.commit()  # Explicitly commit mid-transaction

# Rollback — undo all changes since the transaction started
# Useful when validation logic AFTER writes determines the batch is invalid
with sdk.transaction():
    sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")
    if some_validation_fails:
        sdk.rollback()  # Discard all changes — database unchanged

# Check if currently inside a transaction
if sdk.in_transaction():
    print("Inside a transaction")
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

# Access text and tag relationships directly (if created)
if data.texts:
    print(f"Data File Text: {data.texts[0].value}")
if data.tags:
    print(f"Data File Tag: {data.tags[0].object_ref.name}")
```

## 🔧 Basic Usage

```python
from plexos_sdk import PLEXOSSDK
from plexos_sdk.enums.system_enums import * # access to ENUMS
# Or regenerate from your own database (replaces shipped file, no import change):
# sdk.generate_enums()

with PLEXOSSDK("my_model.db") as sdk:
    try:
        with sdk.transaction():
            # Add a generator — returns hydrated Object with relationships loaded
            gen = sdk.add_object(ClassEnum.Generator, "WindFarm1")

            # Access the auto-created System -> Generator membership via the model
            membership = gen.child_memberships[0]

            # Set capacity for a date period
            capacity = sdk.get_property(
                ClassEnum.System, CollectionEnum.Generators, PropertyEnum_Generators.MaxCapacity
            )
            data = sdk.add_property(
                membership, capacity, 500.0,
                date_from="2030-01-01T00:00:00",
                date_to="2030-12-31T00:00:00",
            )

        # Hydrated models give you access to the full relationship graph
        print(f"{gen.name} -> {data.property_ref.name}: {data.value}")

    except Exception as e:
        print(f"Operations failed: {e}")
```


## 📋 Core Operations

### Objects
```python
# Add object (automatically adds to System membership) -> returns Object model
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")

# Add object with category object (recommended)
category: Category = sdk.get_category_by_name(ClassEnum.Generator, "Wind")
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1", category_obj=category, description="Wind generator")

# Get object -> returns Object model
obj: Object = sdk.get_object_by_name(class_lang_id=ClassEnum.Generator, object_name="Generator1")

# Remove object -> returns bool
success: bool = sdk.remove_object_by_name(class_lang_id=ClassEnum.Generator, object_name="Generator1")
```


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

#### Update & Remove Attributes
```python
# Update an existing attribute value -> returns AttributeData
updated: AttributeData = sdk.update_attribute(object_obj=generator_obj, attribute=attribute_obj, value=750.0)

# Remove an attribute from an object -> returns bool
success: bool = sdk.remove_attribute(object_obj=generator_obj, attribute=attribute_obj)
```



### Memberships
```python
# Add object with automatic System membership -> returns Object
generator: Object = sdk.add_object(class_lang_id=ClassEnum.Generator, object_name="Generator1")  # System membership is always created

# Add membership (parent -> child) -> returns Membership
membership: Membership = sdk.add_membership(collection=collection_obj, parent=parent_obj, child=child_obj)

# Remove membership -> returns bool
success: bool = sdk.remove_membership_by_lang_id(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName", child_name="ChildName")

# Get memberships -> returns model lists
parents: List[Object] = sdk.get_parent_members(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, child_name="ChildName")
children: List[Object] = sdk.get_child_members(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName")
memberships: List[Membership] = sdk.get_child_memberships(parent_class_lang_id=ClassEnum.Fuel, collection_lang_id=CollectionEnum.Fuels, parent_name="ParentName")
```


### Properties
```python
# Get property first (required)
property_obj = sdk.get_property(
    parent_class_lang_id=ClassEnum.System,
    collection_lang_id=CollectionEnum.Generators,
    property_lang_id=PropertyEnum_Generators.MaxOutput
)

# Basic property
data: Data = sdk.add_property(membership=membership,property_obj=property_obj, value=500.0)

# With date range
data: Data = sdk.add_property(
    membership=membership, 
    property_obj=property_obj, 
    value=500.0,
    date_from="2030-01-01T00:00:00", 
    date_to="2030-12-31T00:00:00"
)

# With text creation (writes to t_text with appropriate class_id)
data: Data = sdk.add_property(
    membership=membership, 
    property_obj=property_obj, 
    value=500.0,
    data_file_text="path/to/data.csv",
    time_slice_text="M7-12",  # July-December
    expression_text="x * 1.5"  # Expression text (Variable class)
)

# With tags (writes to t_tag referencing existing objects)
data: Data = sdk.add_property(
    membership=membership, 
    property_obj=property_obj, 
    value=500.0,
    data_file_tag=data_file_obj,
    scenario_tag=scenario_obj,
    expression_tag=variable_obj  # mutually exclusive with expression_text
)

# Method 1: Lookup action first (recommended for bulk operations)
action_obj = Action.get(Action.action_symbol == "×")
variable_obj = sdk.add_object(ClassEnum.Variable, "MyVariable")
scenario_obj = sdk.add_object(ClassEnum.Scenario, "MyScenario")
data: Data = sdk.add_property(
    membership=membership,
    property_obj=property_obj,
    value=500.0,
    scenario_tag=scenario_obj,
    expression_tag=variable_obj,
    action=action_obj  # Using Action object
)

# Method 2: Specify action symbol directly (simpler for single operations)
variable_obj2 = sdk.add_object(ClassEnum.Variable, "MyVariable")
scenario_obj2 = sdk.add_object(ClassEnum.Scenario, "MyScenario")
data: Data = sdk.add_property(
    membership=membership,
    property_obj=property_obj,
    value=500.0,
    scenario_tag=scenario_obj2,
    expression_tag=variable_obj2,
    action="×"  # Action symbol string
)

# Other property operations
value: float = sdk.get_property_value(membership=membership, property_obj=property_obj)
updated_data: Data = sdk.update_property(membership=membership, property_obj=property_obj, value=new_value)
success: bool = sdk.remove_property(membership=membership, property_obj=property_obj)

# Retrieve all Data rows for a membership+property (full property graph)
all_data: List[Data] = sdk.get_property_data_all(membership=membership, property_obj=property_obj)

# Retrieve a specific Data row by filter (e.g., by scenario)
data: Data = sdk.get_property_data(membership=membership, property_obj=property_obj, scenario_tag=scenario_obj)

# Bulk operations — add/update/delete across all memberships in a collection for a scenario
capacity = sdk.get_property(ClassEnum.System, CollectionEnum.Generators, PropertyEnum_Generators.MaxCapacity)
added: int = sdk.bulk_add_property(ClassEnum.System, CollectionEnum.Generators, capacity, 500.0, scenario_tag=scenario_obj)
updated: int = sdk.bulk_update_property(scenario_obj, property_obj=capacity, transform=lambda v: v * 1.1)  # +10%
deleted: int = sdk.bulk_delete_property(scenario_obj, property_obj=capacity)
```

### Memos
Memos attach free-text annotations to data records, memberships, or objects. They are added **after** the entity is created — memos are not part of `add_property` or `add_membership`.

#### Data Memos
Attach notes to individual property data rows (e.g., explaining why a value was chosen).
```python
# Add a data record first
data: Data = sdk.add_property(membership, property_obj, 500.0)

# Add memo to data -> returns MemoData (or None if memo already exists)
memo: MemoData = sdk.add_memo_data(data=data, value="Based on 2024 capacity study")

# Get memo -> returns MemoData or None
memo: MemoData = sdk.get_memo_data(data=data)
print(memo.value)  # "Based on 2024 capacity study"

# Update memo -> returns MemoData or None
updated_memo: MemoData = sdk.update_memo_data(data=data, value="Revised per Q3 review")

# Remove memo -> returns bool
success: bool = sdk.remove_memo_data(data=data)
```

#### Membership Memos
Attach notes to parent-child relationships.
```python
# Add memo to membership -> returns MemoMembership (or None if exists)
memo: MemoMembership = sdk.add_memo_membership(membership=membership, value="Primary fuel supply link")

# Get, update, remove
memo: MemoMembership = sdk.get_memo_membership(membership=membership)
updated: MemoMembership = sdk.update_memo_membership(membership=membership, value="Updated note")
success: bool = sdk.remove_memo_membership(membership=membership)
```

#### Object Memos (Custom Columns)
Attach notes to objects using custom column definitions. Custom columns allow user-defined metadata fields on objects.
```python
from plexos_sdk.models.plexos_models import CustomColumn

# Get or reference a custom column
column: CustomColumn = CustomColumn.get(CustomColumn.name == "Notes")

# Add memo to object+column -> returns MemoObject (or None if exists)
memo: MemoObject = sdk.add_memo_object(object=generator_obj, column=column, value="Commissioned 2024")

# Get, update, remove
memo: MemoObject = sdk.get_memo_object(object=generator_obj, column=column)
updated: MemoObject = sdk.update_memo_object(object=generator_obj, column=column, value="Decommission planned 2030")
success: bool = sdk.remove_memo_object(object=generator_obj, column=column)
```


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

## 🛠️ Helpers & Utilities

### Horizons
Horizons define simulation time periods.
- Planning step types: 1=Day, 2=Week, 3=Month, 4=Year
- Chrono step types (ST Schedule): -1=Second, 0=Minute, 1=Hour, 2=Day, 3=Week
- Raises ObjectAlreadyExistsError if name exists — use update_horizon() to modify.

```python
from datetime import datetime

# Create monthly horizon -> returns Object (Horizon class)
horizon: Object = sdk.create_horizon(
    name="2024 Monthly", date_from=datetime(2024, 1, 1), step_count=12, step_type=3, description="Monthly horizon for 2024")

# With chronological parameters (ST Schedule configuration)
# NOTE: chrono period must fit within planning horizon — SDK raises ValidationError if chrono end exceeds horizon end
horizon: Object = sdk.create_horizon(
    name="2024 With Chrono",
    date_from=datetime(2024, 1, 1), step_count=12, step_type=3,
    chrono_date_from=datetime(2024, 1, 1),
    chrono_step_count=365,                    # 365 days — must not exceed horizon window
    chrono_step_type=2                        # Day (chrono enum, not planning enum)
)

# Get a specific horizon by name -> returns Object
horizon: Object = sdk.get_horizon_by_name("2024 Monthly")

# Update an existing horizon -> returns Object
updated: Object = sdk.update_horizon(
    horizon=horizon,
    step_count=24,                            # Extend to 24 months
    chrono_step_count=26                      # Extend chrono range
)

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

# Convenience: create report, attach to model, and configure properties in one call
report: Object = sdk.create_report(
    model_obj=model,
    report_name="My Report",
    reporting_lang_ids=[
        ReportingEnum_Generators.Generation,
        ReportingEnum_Generators.GenerationCost,
        ReportingEnum_Regions.Price,
    ],
    report_period=True,
    report_summary=True,
)

# Batch configure reporting properties on an existing Report object -> returns List[Report]
configs: List[Report] = sdk.configure_report_properties(
    object_obj=report_object,
    reporting_lang_ids=[ReportingEnum_Generators.Generation, ReportingEnum_Fuels.Cost],
    phase_id=4,
    report_period=True,
    report_summary=True
)

# Query existing report configurations -> returns List[Report]
existing: List[Report] = sdk.get_report_configurations(
    object_obj=report_object,
    reporting_lang_id=ReportingEnum_Generators.Generation,
    phase_id=4  # Optional filter
)
```

## 🚀 Quick Start Example

Complete workflow using core SDK functionality:

```python
from plexos_sdk import PLEXOSSDK
from plexos_sdk.enums.system_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators, AttributeEnum_Generator
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

        # 4. Add properties (membership-level settings)
        membership: Membership = sdk.get_membership_by_child_name(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            parent_name="System",
            child_name="WindFarm1"
        )

        capacity_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.Capacity
        )
        data: Data = sdk.add_property(membership, capacity_prop, 500.0)

        # With text/tag creation
        data: Data = sdk.add_property(
            membership,
            property_obj=capacity_prop,
            value=500.0,
            data_file_text="wind_capacity.csv",
            time_slice_text="M1-12",
            data_file_tag=data_file_obj
        )
```

> **Pro Tip:** For database creation and enum generation, see [Database Management](#-database-management) and [Enum Generation](#-enum-generation) sections.


## 🗄️ Database Management

Most users will work with **existing PLEXOS databases** — either exported from PLEXOS Desktop or provided by their team. The SDK opens these databases directly and reads/writes model data.

For users who need to **create new blank databases** programmatically (without PLEXOS Desktop), see [Seed Data Management](#-seed-data-management).

### XML Conversion
PLEXOS Desktop saves models as `.xml` files. The SDK works with `.db` (SQLite) files. Convert between formats:

```bash
# Convert PLEXOS XML to SQLite database
plexos-sdk xml-to-db model.xml model.db
plexos-sdk xml-to-db model.xml model.db --overwrite

# Convert SQLite database back to PLEXOS XML
plexos-sdk db-to-xml model.db model.xml
plexos-sdk db-to-xml model.db model.xml --overwrite
```

```python
# Open a PLEXOS XML file directly as an SDK instance
with PLEXOSSDK.from_xml("model.xml", "model.db") as sdk:
    # Work with the database — model.db is kept for future use
    with sdk.transaction():
        generator = sdk.add_object(ClassEnum.Generator, "WindFarm1")

# Convert programmatically
from plexos_sdk import XmlConverter
converter = XmlConverter()
converter.xml_to_db("model.xml", "model.db")
converter.db_to_xml("model.db", "model.xml")
```

## ⚙️ Database Configuration

```python
# Set unit system and hydro model type
sdk.set_base_unit_type(units="Metric", hydro_model="Energy")  # defaults
sdk.set_base_unit_type(units="Imperial", hydro_model="Level")
# Valid units: "Metric", "Imperial"
# Valid hydro_model: "Auto", "Energy", "Level", "Volume"
```

## 🔍 Database Validation

```python
# Run all integrity checks — returns list of warning strings (empty = clean)
warnings = sdk.validate()
for w in warnings:
    print(w)

```

## 🎯 Enum Generation

Enums provide type-safe identifiers for classes, collections, properties, and attributes — giving you IDE autocomplete, compile-time validation, and readable code instead of raw integer IDs.

**Shipped default:** The SDK ships with `system_enums.py` for the electric domain (latest version). Use it directly — no generation step needed:
```python
from plexos_sdk.enums.system_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators
```

**Regenerate for your version/domain:** If your PLEXOS version differs or you use a different domain (gas, water, universal), regenerate from your own database. The output is always `system_enums.py` so import statements stay the same.

### From SDK (preferred — no separate step)
```python
from plexos_sdk.enums.system_enums import ClassEnum, PropertyEnum_Generators

with PLEXOSSDK("my_database.db") as sdk:
    sdk.generate_enums()  # replaces shipped enums with your database's version
    # Same import above now reflects your version/domain — no changes needed
```

## 🎯 Data Enums/Identifiers

The SDK supports enums for better developer experience. Import domain-specific enums for type safety and IDE support.

```python
# Import enums (shipped with SDK, or regenerated from your database)
from plexos_sdk.enums.system_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators, PropertyEnum_Fuels, AttributeEnum_Generator

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



## 🔧 Error Handling

```python
from plexos_sdk.exceptions import (
    ActionNotFoundError, InvalidObjectNameError, ObjectNotFoundError, SystemObjectError,
    ClassNotFoundError, CollectionNotFoundError, CollectionDisabledError, ValidationError,
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

try:
    variable_obj = sdk.add_object(ClassEnum.Variable, "TestVariable")
    data: Data = sdk.add_property(membership, property_obj, 100.0, 
                                   expression_tag=variable_obj,
                                   action="NonExistentAction")
except ActionNotFoundError as e:
    print(f"Action not found: {e}")  # Clear error message when action symbol doesn't exist
except ValidationError as e:
    print(f"Validation error: {e}")  # Error if action provided without expression_tag
```


## 📚 Common Patterns

```python
from plexos_sdk.models.plexos_models import Text, Tag

# Complete workflow with horizon and object creation
with sdk.transaction():
    # 1. Create horizon for the simulation -> returns Object (Horizon class)
    horizon: Object = sdk.create_horizon(
        name="2024-2025 Analysis",
        date_from=datetime(2024, 1, 1),
        step_count=24,
        step_type=3,
        description="24-month analysis period"
    )

    # 2. Add object (automatically adds to System membership) -> returns Object
    category: Category = sdk.get_category_by_name(ClassEnum.Generator, "Wind")
    wind_farm_obj: Object = sdk.add_object(
        class_lang_id=ClassEnum.Generator,
        object_name="WindFarm1",
        category_obj=category,
        description="Wind farm"
    )

    # Get the membership that was automatically created
    membership: Membership = sdk.get_membership_by_child_name(
        parent_class_lang_id=ClassEnum.System,
        collection_lang_id=CollectionEnum.Generators,
        parent_name="System",
        child_name="WindFarm1"
    )

    # Get property and add it
    capacity_prop = sdk.get_property(
        parent_class_lang_id=ClassEnum.System,
        collection_lang_id=CollectionEnum.Generators,
        property_lang_id=PropertyEnum_Generators.Capacity
    )
    capacity_data: Data = sdk.add_property(membership=membership, property_obj=capacity_prop, value=500.0)

    # With text creation
    availability_prop = sdk.get_property(
        parent_class_lang_id=ClassEnum.System,
        collection_lang_id=CollectionEnum.Generators,
        property_lang_id=PropertyEnum_Generators.Availability
    )
    availability_data: Data = sdk.add_property(
        membership=membership,
        property_obj=availability_prop,
        value=0.95,
        data_file_text="availability_data.csv",
        time_slice_text="M7-12"
    )

    # With tags and date range
    fuel_cost_prop = sdk.get_property(
        parent_class_lang_id=ClassEnum.System,
        collection_lang_id=CollectionEnum.Generators,
        property_lang_id=PropertyEnum_Generators.FuelCost
    )
    fuel_cost_data: Data = sdk.add_property(
        membership=membership,
        property_obj=fuel_cost_prop,
        value=45.0,
        data_file_tag=data_file_obj,
        date_from="2030-01-01T00:00:00"
    )

    # Add attributes -> returns Attribute and AttributeData
    max_output_attr: Attribute = sdk.get_attribute(
        class_lang_id=ClassEnum.Generator,
        attribute_lang_id=AttributeEnum_Generator.MaxOutput
    )
    attr_data: AttributeData = sdk.add_attribute(object_obj=wind_farm_obj, attribute=max_output_attr, value=600.0)
```




## 🌱 Seed Data Management

> **Audience:** This is an advanced feature for users who want to create completely blank PLEXOS databases programmatically — a capability that was previously limited to PLEXOS Desktop. Most users (90%+) will work with existing versioned databases and can skip this section.

### Why Seed Data?

Every PLEXOS database requires a foundation of **system-defined metadata** — classes, collections, properties, attributes, and their relationships. This metadata defines what object types exist (Generators, Fuels, Regions, etc.), what properties they support, and how they relate to each other.

This metadata is **version-specific**. PLEXOS 11.05.112 has different metadata than 11.03.75 — new properties, renamed collections, updated validation rules. When creating a blank database, the seed data must match the PLEXOS version the user will run simulations against. Using mismatched seed data can cause upgrade/downgrade issues when the database is opened in PLEXOS Desktop.

### How Seed Data Is Produced

Seed data is extracted from **blank PLEXOS databases** — one per system type. The SDK converts these into portable SQL scripts and packages them into a versioned zip file that ships with the SDK.

**System types:** `electric`, `gas`, `water`, `universal`

#### Step-by-Step: Building a Seed Data Package

**Step 1 — Create source databases in PLEXOS Desktop**

Open PLEXOS Desktop and create a new blank project for each system type. Save each as XML:
- `electric.xml` — blank Electric project
- `gas.xml` — blank Gas project
- `water.xml` — blank Water project
- `universal.xml` — blank Universal project

**Step 2 — Convert XML files to SQLite databases**

The database files **must be named** to match their system type exactly:
```bash
plexos-sdk xml-to-db electric.xml electric.db
plexos-sdk xml-to-db gas.xml gas.db
plexos-sdk xml-to-db water.xml water.db
plexos-sdk xml-to-db universal.xml universal.db
```

**Step 3 — Package all databases into a versioned zip**

Place all 4 `.db` files in one folder, then package them:
```bash
plexos-sdk package-sql C:\Data\seed_dbs\ seeddata/sdk_seed_data.zip
```
The PLEXOS version is auto-detected from the databases (e.g., `11.05.112`). The zip supports **multiple versions** — running this again with databases from a different PLEXOS version appends a new version folder to the existing zip.

```bash
# Override auto-detected version
plexos-sdk package-sql C:\Data\seed_dbs\ seeddata/sdk_seed_data.zip --version 11.05.112

# Replace an existing version in the zip
plexos-sdk package-sql C:\Data\seed_dbs\ seeddata/sdk_seed_data.zip --overwrite-version
```

**Zip structure:**
```
sdk_seed_data.zip
├── 11.05.112/
│   ├── seed_data_electric.sql
│   ├── seed_data_gas.sql
│   ├── seed_data_water.sql
│   ├── seed_data_universal.sql
│   └── metadata.json
├── 11.03.75/
│   ├── seed_data_electric.sql
│   ├── ...
│   └── metadata.json
└── package_metadata.json
```

### Creating Databases from Seed Data

Once the seed data package exists, users can create new blank databases:

```bash
# Create a blank database (schema only, no seed data)
plexos-sdk create-db my_database.db

# Create a populated database from a source database's seed data
plexos-sdk create-from-sql source.db new_model.db electric
plexos-sdk create-from-sql source.db new_model.db electric --overwrite
```

```python
from plexos_sdk import SeedDataManager

# Extract seed data SQL scripts from a source database
with SeedDataManager("source_database.db") as manager:
    results = manager.generate_seed_data_sql("sql_output/")

    # Create a new database from the extracted SQL
    manager.create_database("new_model.db", "electric", results["electric"])

# Or create directly from a versioned zip package
with SeedDataManager("source_database.db") as manager:
    manager.create_database_from_zip(
        "new_model.db",
        "seeddata/sdk_seed_data.zip",
        "electric",
        "11.05.112"  # Optional — defaults to newest version in zip
    )
```

### Additional CLI Commands

```bash
# Extract seed data from a single database to SQL scripts
plexos-sdk extract-sql source.db output_dir/
plexos-sdk extract-sql source.db output_dir/ --system-types electric gas
plexos-sdk extract-sql source.db output_dir/ --overwrite

# Package from a single database (instead of a directory of 4)
plexos-sdk package-sql source.db seeddata/sdk_seed_data.zip
```

## ⚠️ Important Notes

### Automatic System Relationships

**When you create an object, the SDK automatically creates a System membership** for that object. This is the default parent-child relationship in PLEXOS where all objects belong to the System.

**How it works:**
- When you call `add_object()`, the SDK automatically:
  1. Creates the object
  2. Finds the appropriate collection for `System → ObjectClass` relationship
  3. Creates a membership linking `System` (parent) to your new object (child)
  4. Returns the object with the membership already created

**Important points:**
- **No manual membership creation needed** - The System membership is created automatically
- **Collection is auto-detected** - The SDK finds the correct collection based on the object's class
- **All classes get System memberships** - Any class that has a System → Class collection defined in seed data
- **Access the membership** - Use `get_membership_by_child_name()` or access via `object.child_memberships`

**Example:**
```python
# Create a generator - System membership is automatically created
generator: Object = sdk.add_object(ClassEnum.Generator, "WindFarm1")

# Access the automatically created System membership
membership: Membership = sdk.get_membership_by_child_name(
    parent_class_lang_id=ClassEnum.System,
    collection_lang_id=CollectionEnum.Generators,
    parent_name="System",
    child_name="WindFarm1"
)

# Or access via object's child_memberships (if hydrated)
if generator.child_memberships:
    system_membership = generator.child_memberships[0]
    print(f"System membership ID: {system_membership.membership_id}")
```

### Property Duplicate Detection

The SDK performs comprehensive duplicate detection when adding properties. Two properties are considered duplicates only if **ALL** aspects of the property graph match:

- **Membership and Property**: Same membership and property
- **Band ID**: Same band_id (default is 1)
- **Value**: Same numeric value
- **Texts**: Same set of Text objects (data_file_text, time_slice_text, expression_text) - compared by class_id, value, and action_id
- **Tags**: Same set of Tag objects (data_file_tag, scenario_tag, expression_tag) - compared by object_id and action_id
- **Date Ranges**: Same date_from and date_to values

**Note:** Memos are **not** part of duplicate detection because they are added after property creation using `add_memo_data()`. Properties with the same property graph but different memos can coexist - the memo is added separately after the property is created.

**Important behaviors:**
- Properties with different **scenario tags** are considered **unique** (different scenarios = different records)
- Properties with different **expression tags** (Variables) are considered **unique**
- Properties with different **data_file_tags** are considered **unique**
- Properties can have **multiple tags** - all tags are compared as a set
- Properties with different **date ranges** are considered **unique**
- Properties with different **band_ids** are considered **unique**

**Example:**
```python
# These are UNIQUE (different scenario tags)
sdk.add_property(membership, prop, 100.0, scenario_tag=scenario1)  # OK
sdk.add_property(membership, prop, 100.0, scenario_tag=scenario2)  # OK - different scenario

# This would raise PropertyAlreadyExistsError (exact duplicate)
sdk.add_property(membership, prop, 100.0, scenario_tag=scenario1)  # Error - duplicate
```

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