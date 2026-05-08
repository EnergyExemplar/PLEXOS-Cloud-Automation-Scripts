# PLEXOS SDK — Comprehensive Example

> **Reference only.** This document shows how to build a complete, runnable PLEXOS model from scratch using the Python SDK. Each section is a self-contained example; copy any code block into a `.py` file to execute.

---

## Table of Contents

1. [Overview](#overview)
2. [Imports & Setup](#imports--setup)
3. [Create Database](#create-database)
4. [Categories](#categories)
5. [Generators](#generators)
6. [Batteries](#batteries)
7. [Companies, Nodes, Fuels](#companies-nodes-fuels)
8. [Transmission Lines](#transmission-lines)
9. [Relationships](#relationships)
10. [Reports & Diagnostics](#reports--diagnostics)
11. [Horizons](#horizons)
12. [Scenarios & Bulk Operations](#scenarios--bulk-operations)
13. [Data Retrieval & Memos](#data-retrieval--memos)
14. [Verification Queries](#verification-queries)
15. [XML Export & Round-Trip](#xml-export--round-trip)
16. [Validation](#validation)

---

## Overview

This example builds a realistic multi-node energy system:

| Component | Count | Details |
|---|---|---|
| Nodes | 10 | Ring + mesh topology |
| Regions | 10 | One per node, 400–1500 MW demand |
| Generators | 100 | 5 categories: large thermal, medium thermal, peakers, renewables, baseload |
| Batteries | 100 | 3 categories: large (4–8h), medium (2–4h), small (1–2h) |
| Fuels | 100 | Gas, coal, nuclear, biomass, diesel, hydrogen |
| Companies | 100 | Ownership on first 50 generators |
| Lines | 15 | Ring + cross-links |

**SDK features covered:** `SQLDatabaseCreator`, `add_category`, `add_object`, `get_property`, `add_property`, `get_collection`, `add_membership`, `transaction`, `add_attribute_by_lang_id`, `add_report_configuration`, `create_report`, `get_report_configurations`, `create_horizon`, `list_all_horizons`, `get_horizon_by_name`, `bulk_add_property`, `bulk_update_property`, `bulk_delete_property`, `get_property_data`, `get_property_data_all`, `get_membership_by_child_name`, `add_memo_data`, `get_memo_data`, `get_objects`, `XmlConverter.db_to_xml`, `PLEXOSSDK.from_xml`, `sdk.validate`.

---

## Imports & Setup

```python
import os
import random
from datetime import datetime

from plexos_sdk.enums.system_enums import *
from plexos_sdk import PLEXOSSDK, XmlConverter
from plexos_sdk.sql_database_creator import SQLDatabaseCreator
from plexos_sdk.models.plexos_models import *

DB_PATH = "example_model.db"
XML_PATH = "example_model.xml"
# Seed data ships with the plexos_sdk package — adjust this path to your local install
SEED_DATA_PATH = "seeddata/sdk_seed_data.zip"
```

---

## Create Database

Create a blank PLEXOS model database from the SDK seed data:

```python
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

creator = SQLDatabaseCreator()
creator.create_database_from_zip(
    output_path=DB_PATH,
    zip_path=SEED_DATA_PATH,
    system_type="electric",
    overwrite=True,
)
```

---

## Categories

Categories organize objects for display and filtering. Each category belongs to a specific class (Generator, Battery, etc.):

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        # Generator categories (5 types)
        gen_cat_1 = sdk.add_category(
            category_name="LargeThermal",
            description="Large thermal generators (200-800 MW)",
            class_lang_id=ClassEnum.Generator,
        )
        gen_cat_2 = sdk.add_category(
            category_name="MediumThermal",
            description="Medium thermal generators (100-400 MW)",
            class_lang_id=ClassEnum.Generator,
        )
        gen_cat_3 = sdk.add_category(
            category_name="Peakers",
            description="Small peaking generators (50-200 MW)",
            class_lang_id=ClassEnum.Generator,
        )
        gen_cat_4 = sdk.add_category(
            category_name="Renewables",
            description="Renewable generators (20-150 MW)",
            class_lang_id=ClassEnum.Generator,
        )
        gen_cat_5 = sdk.add_category(
            category_name="Baseload",
            description="Baseload generators (300-1000 MW)",
            class_lang_id=ClassEnum.Generator,
        )

        # Battery categories (3 sizes)
        bat_cat_large = sdk.add_category(
            category_name="LargeBattery",
            description="Large batteries, 4-8 hour duration",
            class_lang_id=ClassEnum.Battery,
        )
        bat_cat_medium = sdk.add_category(
            category_name="MediumBattery",
            description="Medium batteries, 2-4 hour duration",
            class_lang_id=ClassEnum.Battery,
        )
        bat_cat_small = sdk.add_category(
            category_name="SmallBattery",
            description="Small batteries, 1-2 hour duration",
            class_lang_id=ClassEnum.Battery,
        )

        # Company categories (2)
        for i in range(2):
            sdk.add_category(
                category_name=f"TestCompanyCat_{i + 1}",
                description=f"Test company category {i + 1}",
                class_lang_id=ClassEnum.Company,
            )

        # Node categories (2)
        for i in range(2):
            sdk.add_category(
                category_name=f"TestNodeCat_{i + 1}",
                description=f"Test node category {i + 1}",
                class_lang_id=ClassEnum.Node,
            )

        # Fuel categories (3)
        for i in range(3):
            sdk.add_category(
                category_name=f"TestFuelCat_{i + 1}",
                description=f"Test fuel category {i + 1}",
                class_lang_id=ClassEnum.Fuel,
            )

        # Region categories (2)
        for i in range(2):
            sdk.add_category(
                category_name=f"TestRegionCat_{i + 1}",
                description=f"Test region category {i + 1}",
                class_lang_id=ClassEnum.Region,
            )
```

---

## Generators

Look up property definitions once, then create objects and assign properties. Each generator gets a System membership automatically — use it to set properties:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        # Look up property definitions (do this ONCE, reuse for all generators)
        capacity_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.MaxCapacity,
        )
        min_load_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.MinLoad,
        )
        heat_rate_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.HeatRate,
        )
        fuel_price_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.FuelPrice,
        )
        units_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.Units,
        )

        # Create a generator with properties
        gen = sdk.add_object(
            class_lang_id=ClassEnum.Generator,
            object_name="TestGen_001",
            category_obj=gen_cat_1,          # Category from step 2
            description="Large thermal unit",
        )

        # The System membership is auto-created — use it for properties
        membership = gen.child_memberships[0]

        sdk.add_property(membership, capacity_prop, 500.0)    # 500 MW
        sdk.add_property(membership, min_load_prop, 150.0)    # 150 MW min
        sdk.add_property(membership, units_prop, 1)           # 1 unit
        sdk.add_property(membership, heat_rate_prop, 8.5)     # 8.5 MMBtu/MWh
        sdk.add_property(membership, fuel_price_prop, 4.5)    # $4.50/GJ
```

**Scaling to 100 generators** — loop with category-based parameters (continues inside the same `with sdk.transaction()` block):

```python
    # ... inside with PLEXOSSDK(DB_PATH) as sdk / with sdk.transaction(): ...

    generator_categories = [gen_cat_1, gen_cat_2, gen_cat_3, gen_cat_4, gen_cat_5]
    generators = []

    for i in range(100):
        category = generator_categories[i % 5]
        gen = sdk.add_object(
            class_lang_id=ClassEnum.Generator,
            object_name=f"TestGen_{i + 1:03d}",
            category_obj=category,
        )
        generators.append(gen)

        mem = gen.child_memberships[0]
        cat_idx = i % 5

        # Vary capacity by category
        if cat_idx == 0:    capacity = random.uniform(200, 800)
        elif cat_idx == 1:  capacity = random.uniform(100, 400)
        elif cat_idx == 2:  capacity = random.uniform(50, 200)
        elif cat_idx == 3:  capacity = random.uniform(20, 150)
        else:               capacity = random.uniform(300, 1000)

        sdk.add_property(mem, capacity_prop, capacity)
        sdk.add_property(mem, units_prop, 1)

        # MinLoad — percentage of capacity, varies by category
        if cat_idx == 0:    min_load = capacity * 0.3
        elif cat_idx == 1:  min_load = capacity * 0.2
        elif cat_idx == 2:  min_load = capacity * 0.1
        elif cat_idx == 3:  min_load = 0          # Renewables can be zero
        else:               min_load = capacity * 0.4
        sdk.add_property(mem, min_load_prop, min_load)

        # Heat rate only for thermal categories
        if cat_idx in [0, 1, 4]:
            sdk.add_property(mem, heat_rate_prop, random.uniform(6.0, 12.0))

        # FuelPrice ($/GJ) — direct cost, varies by category
        if cat_idx == 0:    sdk.add_property(mem, fuel_price_prop, random.uniform(3.0, 6.0))
        elif cat_idx == 1:  sdk.add_property(mem, fuel_price_prop, random.uniform(4.0, 8.0))
        elif cat_idx == 2:  sdk.add_property(mem, fuel_price_prop, random.uniform(6.0, 12.0))
        elif cat_idx == 3:  sdk.add_property(mem, fuel_price_prop, random.uniform(0.0, 0.5))
        else:               sdk.add_property(mem, fuel_price_prop, random.uniform(1.5, 3.0))
```

---

## Batteries

Same pattern — look up properties, create objects, assign values:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        max_power_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Batteries,
            property_lang_id=PropertyEnum_Batteries.MaxPower,
        )
        capacity_bat_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Batteries,
            property_lang_id=PropertyEnum_Batteries.Capacity,
        )
        duration_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Batteries,
            property_lang_id=PropertyEnum_Batteries.Duration,
        )
        units_bat_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Batteries,
            property_lang_id=PropertyEnum_Batteries.Units,
        )

        battery_categories = [bat_cat_large, bat_cat_medium, bat_cat_small]
        batteries = []

        for i in range(100):
            cat = battery_categories[i % 3]
            bat = sdk.add_object(
                class_lang_id=ClassEnum.Battery,
                object_name=f"TestBattery_{i + 1:03d}",
                category_obj=cat,
            )
            batteries.append(bat)

            mem = bat.child_memberships[0]
            cat_idx = i % 3

            if cat_idx == 0:    power = random.uniform(50, 200);  hrs = random.uniform(4, 8)
            elif cat_idx == 1:  power = random.uniform(20, 80);   hrs = random.uniform(2, 4)
            else:               power = random.uniform(5, 30);    hrs = random.uniform(1, 2)

            sdk.add_property(mem, max_power_prop, power)
            sdk.add_property(mem, capacity_bat_prop, power * hrs)
            sdk.add_property(mem, duration_prop, hrs)
            sdk.add_property(mem, units_bat_prop, 1)
```

---

## Companies, Nodes, Fuels

Simple objects — companies and nodes have no required properties. Fuels get a `Price`. This example assumes `categories` was built earlier (see [Categories](#categories)); alternatively, pass `category_obj=None` to skip:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        # Assume categories dict was built in the Categories section above
        company_categories = categories.get(ClassEnum.Company, [None])
        companies = []
        for i in range(100):
            companies.append(sdk.add_object(
                class_lang_id=ClassEnum.Company,
                object_name=f"TestCompany_{i + 1:03d}",
                category_obj=company_categories[i % len(company_categories)],
                description=f"Test company {i + 1}",
            ))

        node_categories = categories.get(ClassEnum.Node, [None])
        nodes = []
        for i in range(10):
            nodes.append(sdk.add_object(
                class_lang_id=ClassEnum.Node,
                object_name=f"TestNode_{i + 1:03d}",
                category_obj=node_categories[i % len(node_categories)],
                description=f"Test node {i + 1}",
            ))

        # Fuels — with category assignment and Price property
        fuel_categories = categories.get(ClassEnum.Fuel, [None])
        fuel_price_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Fuels,
            property_lang_id=PropertyEnum_Fuels.Price,
        )

        fuel_types = ["Natural Gas", "Coal", "Nuclear", "Biomass", "Diesel", "Hydrogen"]
        fuel_prices = {
            "Natural Gas": (3, 6), "Coal": (1.5, 3), "Nuclear": (0.5, 1),
            "Biomass": (2, 4), "Diesel": (8, 15), "Hydrogen": (10, 20),
        }

        fuels = []
        for i in range(100):
            ftype = fuel_types[i % len(fuel_types)]
            fuel = sdk.add_object(
                class_lang_id=ClassEnum.Fuel,
                object_name=f"TestFuel_{ftype}_{i + 1:03d}",
                category_obj=fuel_categories[i % len(fuel_categories)],
                description=f"Test fuel {i + 1}",
            )
            fuels.append(fuel)
            lo, hi = fuel_prices[ftype]
            sdk.add_property(fuel.child_memberships[0], fuel_price_prop, random.uniform(lo, hi))
```

---

## Transmission Lines

Lines connect nodes. Use `Collection` queries to find the `Node From` and `Node To` collections, then create memberships:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        max_flow_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Lines,
            property_lang_id=PropertyEnum_Lines.MaxFlow,
        )

        line_class = Class.get(Class.name == "Line")
        node_class = Class.get(Class.name == "Node")

        node_from_coll = Collection.get(
            (Collection.name == "Node From")
            & (Collection.parent_class == line_class)
            & (Collection.child_class == node_class)
            & (Collection.is_enabled == True)
        )
        node_to_coll = Collection.get(
            (Collection.name == "Node To")
            & (Collection.parent_class == line_class)
            & (Collection.child_class == node_class)
            & (Collection.is_enabled == True)
        )

        # Ring topology: 0→1→2→...→9→0
        n = len(nodes)
        connections = [(i, (i + 1) % n) for i in range(n)]
        # Cross-links for mesh redundancy
        connections += [(i, (i + 3) % n) for i in range(0, n, 2)]

        for from_idx, to_idx in connections:
            line = sdk.add_object(
                class_lang_id=ClassEnum.Line,
                object_name=f"Line_{nodes[from_idx].name}_to_{nodes[to_idx].name}",
            )
            sdk.add_membership(collection=node_from_coll, parent=line, child=nodes[from_idx])
            sdk.add_membership(collection=node_to_coll, parent=line, child=nodes[to_idx])

            # MaxFlow (MW)
            sdk.add_property(line.child_memberships[0], max_flow_prop, random.uniform(500, 2000))
```

---

## Relationships

Objects must be wired together. Key collection rules:
- **Node → Region:** required (min_count=1). Each node needs exactly one region.
- **Generator → Node:** required. Each generator must sit on a node.
- **Battery → Node:** required.
- **Generator → Company:** optional.
- **Generator → Fuel:** optional, unlimited (max_count=-1).

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        # Get relationship collections
        gen_nodes_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Nodes)
        gen_companies_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Companies)
        gen_fuels_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Fuels)
        regions_coll = sdk.get_collection(ClassEnum.System, CollectionEnum.Regions)

        # Inspect collection rules — useful for understanding cardinality constraints
        print(f"Companies: is_one_to_many={gen_companies_coll.is_one_to_many}, "
              f"max_count={gen_companies_coll.max_count}")
        print(f"Nodes: is_one_to_many={gen_nodes_coll.is_one_to_many}, "
              f"max_count={gen_nodes_coll.max_count}")
        print(f"Fuels: is_one_to_many={gen_fuels_coll.is_one_to_many}, "
              f"max_count={gen_fuels_coll.max_count}")
        print(f"Regions: is_one_to_many={regions_coll.is_one_to_many}, "
              f"max_count={regions_coll.max_count}")

        node_class = Class.get(Class.name == "Node")
        region_class = Class.get(Class.name == "Region")
        battery_class = Class.get(Class.name == "Battery")

        node_region_coll = Collection.get(
            (Collection.name == "Region")
            & (Collection.parent_class == node_class)
            & (Collection.child_class == region_class)
            & (Collection.is_enabled == True)
        )
        bat_nodes_coll = Collection.get(
            (Collection.name == "Nodes")
            & (Collection.parent_class == battery_class)
            & (Collection.child_class == node_class)
            & (Collection.is_enabled == True)
        )

        # Region.Load property for setting demand
        load_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Regions,
            property_lang_id=PropertyEnum_Regions.Load,
        )

        # Node → Region (one region per node, with demand)
        base_demands = [1200, 800, 600, 1500, 400, 1000, 700, 900, 500, 1100]
        for i, node in enumerate(nodes):
            region = sdk.add_object(
                class_lang_id=ClassEnum.Region,
                object_name=node.name,
            )
            sdk.add_membership(collection=node_region_coll, parent=node, child=region)
            sdk.add_property(region.child_memberships[0], load_prop, base_demands[i])

        # Generator → Node (required, cycle through nodes)
        for i, gen in enumerate(generators):
            sdk.add_membership(collection=gen_nodes_coll, parent=gen, child=nodes[i % len(nodes)])

        # Battery → Node (required)
        for i, bat in enumerate(batteries):
            sdk.add_membership(collection=bat_nodes_coll, parent=bat, child=nodes[i % len(nodes)])

        # Generator → Company (first 50 generators)
        for i, gen in enumerate(generators[:50]):
            sdk.add_membership(collection=gen_companies_coll, parent=gen,
                               child=companies[i % len(companies)])

        # Generator → Fuel (first 20 generators, 2 fuels each)
        for i, gen in enumerate(generators[:20]):
            for j in range(2):
                sdk.add_membership(collection=gen_fuels_coll, parent=gen,
                                   child=fuels[(i + j) % len(fuels)])
```

> **Note:** `generators`, `batteries`, `companies`, `nodes`, and `fuels` are lists built in the earlier sections.

---

## Reports & Diagnostics

### Report Object

Configure which output properties to include and at what granularity:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        report = sdk.add_object(ClassEnum.Report, "TestReport")

        # Enable output granularities
        sdk.add_attribute_by_lang_id(report, AttributeEnum_Report.OutputResultsByHour, -1)
        sdk.add_attribute_by_lang_id(report, AttributeEnum_Report.OutputResultsByDay, -1)
        sdk.add_attribute_by_lang_id(report, AttributeEnum_Report.OutputStatistics, -1)
        sdk.add_attribute_by_lang_id(report, AttributeEnum_Report.OutputResultsBySample, -1)

        # Add reporting configurations
        reporting_items = [
            (CollectionEnum.Generators, ReportingEnum_Generators.Generation),
            (CollectionEnum.Generators, ReportingEnum_Generators.GenerationCost),
            (CollectionEnum.Generators, ReportingEnum_Generators.NetRevenue),
            (CollectionEnum.Fuels,      ReportingEnum_Fuels.Cost),
            (CollectionEnum.Batteries,  ReportingEnum_Batteries.Load),
            (CollectionEnum.Batteries,  ReportingEnum_Batteries.Soc),
        ]

        for coll_id, report_id in reporting_items:
            sdk.add_report_configuration(
                object_obj=report,
                collection_lang_id=coll_id,
                reporting_lang_id=report_id,
                phase_id=4,
                report_period=True,
                report_samples=True,
                report_statistics=True,
                report_summary=True,
                write_flat_files=False,
            )
```

### One-Call `create_report` Convenience Method

Creates a Report, attaches it to a Model, and adds reporting configs in a single call:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        model = sdk.add_object(ClassEnum.Model, "DemoModel")
        report = sdk.create_report(
            model_obj=model,
            report_name="QuickReport",
            reporting_lang_ids=[
                (CollectionEnum.Generators, ReportingEnum_Generators.Generation),
                (CollectionEnum.Generators, ReportingEnum_Generators.GenerationCost),
                (CollectionEnum.Batteries,  ReportingEnum_Batteries.Load),
            ],
            report_period=True,
            report_summary=True,
        )

        # Query report configurations back
        configs = sdk.get_report_configurations(
            report,
            CollectionEnum.Generators,
            ReportingEnum_Generators.Generation,
        )
        # configs -> list of ReportConfig objects
```

### Diagnostic Object

Enable LP/MPS file output and attach to all models:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        diag = sdk.add_object(ClassEnum.Diagnostic, "TestDiagnostic")
        sdk.add_attribute_by_lang_id(diag, AttributeEnum_Diagnostic.LpFiles, -1)
        sdk.add_attribute_by_lang_id(diag, AttributeEnum_Diagnostic.MpsFiles, -1)

        # Attach to all existing Model objects
        model_class = Class.get(Class.name == "Model")
        diag_class = Class.get(Class.name == "Diagnostic")
        model_diag_coll = Collection.get(
            (Collection.name == "Diagnostic")
            & (Collection.parent_class == model_class)
            & (Collection.child_class == diag_class)
            & (Collection.is_enabled == True)
        )

        for model in Object.select().where(Object.class_id == model_class.class_id):
            sdk.add_membership(collection=model_diag_coll, parent=model, child=diag)
```

---

## Horizons

Create a simulation horizon and assign it to a Model. The `max_count=1` constraint on the Horizon collection means you must remove the existing horizon before adding a new one:

**Step Type (Planning):** 1=Day, 2=Week, 3=Month, 4=Year
**Chrono Step Type (ST Schedule):** -1=Second, 0=Minute, 1=Hour, 2=Day, 3=Week

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        # Enable the Reliability model
        reliability = sdk.get_object_by_name(ClassEnum.Model, "Reliability")
        sdk.add_attribute_by_lang_id(reliability, AttributeEnum_Model.Enabled, -1)

        # Create a 5-day horizon
        horizon = sdk.create_horizon(
            name="5-Day Test",
            date_from=datetime(2025, 1, 1),
            step_count=5,
            step_type=1,              # Day
            chrono_date_from=datetime(2025, 1, 1),
            chrono_step_count=5,
            chrono_step_type=2,       # Day (chrono enum differs from planning enum)
            description="5-day ST schedule for testing",
        )

        # Swap horizon on model (max_count=1 — must remove old first)
        horizon_coll = sdk.get_collection(ClassEnum.Model, CollectionEnum.Horizon)
        existing = sdk.get_child_memberships(ClassEnum.Model, CollectionEnum.Horizon, "Reliability")
        for mem in existing:
            sdk.remove_membership(mem)
        sdk.add_membership(collection=horizon_coll, parent=reliability, child=horizon)
```

**Lookup methods:**

```python
with PLEXOSSDK(DB_PATH) as sdk:
    # List all horizons
    all_horizons = sdk.list_all_horizons()

    # Look up by name
    h = sdk.get_horizon_by_name("5-Day Test")
```

---

## Scenarios & Bulk Operations

Create a Scenario and use bulk operations to mass-modify properties:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        scenario = sdk.add_object(ClassEnum.Scenario, "HighCapacity2025")

        capacity_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.MaxCapacity,
        )

        # bulk_add: add capacity=999 MW to ALL generators under this scenario
        added = sdk.bulk_add_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_obj=capacity_prop,
            value=999.0,
            scenario_tag=scenario,
        )
        # added = 100 (one row per generator)

        # bulk_update: apply +10% transform to all scenario-tagged rows
        updated = sdk.bulk_update_property(
            scenario_tag=scenario,
            property_obj=capacity_prop,
            transform=lambda v: v * 1.10,
        )
        # All rows now 999 * 1.10 = 1098.9

        # bulk_delete: remove all scenario-tagged capacity rows
        deleted = sdk.bulk_delete_property(
            scenario_tag=scenario,
            property_obj=capacity_prop,
        )
```

---

## Data Retrieval & Memos

Query property data back from the model and attach memo annotations:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    with sdk.transaction():
        scenario = sdk.add_object(ClassEnum.Scenario, "RetrievalDemo")

        # Look up the MaxCapacity property (defined in Generators section)
        capacity_prop = sdk.get_property(
            parent_class_lang_id=ClassEnum.System,
            collection_lang_id=CollectionEnum.Generators,
            property_lang_id=PropertyEnum_Generators.MaxCapacity,
        )

        # Look up a specific generator's membership
        gen1_mem = sdk.get_membership_by_child_name(
            ClassEnum.System, CollectionEnum.Generators, "System", "TestGen_001",
        )

        # Add multi-band and scenario-tagged data
        sdk.add_property(gen1_mem, capacity_prop, 500.0, band_id=2)
        sdk.add_property(
            gen1_mem, capacity_prop, 750.0,
            scenario_tag=scenario,
            date_from="2025-06-01T00:00:00",
        )

    # Retrieve ALL Data rows for a membership + property
    all_data = sdk.get_property_data_all(gen1_mem, capacity_prop)
    for d in all_data:
        tags = [t.object.name for t in d.tags] if d.tags else []
        bands = [b.band_id for b in d.bands] if d.bands else []
        print(f"value={d.value}, bands={bands}, tags={tags}")

    # Retrieve a specific row by filter
    specific = sdk.get_property_data(gen1_mem, capacity_prop, scenario_tag=scenario)
    # specific.value == 750.0

    # Attach memos to document assumptions or overrides
    with sdk.transaction():
        sdk.add_memo_data(specific, "Override for summer peak demand analysis")
        memo = sdk.get_memo_data(specific)
        # memo.value == "Override for summer peak demand analysis"

        base = sdk.get_property_data(gen1_mem, capacity_prop)
        sdk.add_memo_data(base, "Based on 2024 nameplate rating from NERC GADS")

        # Memo on a different generator — flag for review
        gen5_mem = sdk.get_membership_by_child_name(
            ClassEnum.System, CollectionEnum.Generators, "System", "TestGen_005",
        )
        gen5_cap = sdk.get_property_data(gen5_mem, capacity_prop)
        sdk.add_memo_data(gen5_cap, "Capacity derated pending maintenance — review Q3 2025")
```

---

## Verification Queries

Use `get_objects()` and direct ORM queries to verify the model after creation:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    all_generators = sdk.get_objects(class_lang_id=ClassEnum.Generator)
    all_batteries = sdk.get_objects(class_lang_id=ClassEnum.Battery)
    all_companies = sdk.get_objects(class_lang_id=ClassEnum.Company)
    all_nodes = sdk.get_objects(class_lang_id=ClassEnum.Node)
    all_fuels = sdk.get_objects(class_lang_id=ClassEnum.Fuel)
    all_regions = sdk.get_objects(class_lang_id=ClassEnum.Region)

    print(f"Generators: {len(all_generators)}")
    print(f"Batteries: {len(all_batteries)}")
    print(f"Companies: {len(all_companies)}")
    print(f"Nodes: {len(all_nodes)}")
    print(f"Fuels: {len(all_fuels)}")
    print(f"Regions: {len(all_regions)}")

    # Count total memberships and property rows via ORM
    total_memberships = Membership.select().count()
    total_properties = Data.select().count()
    print(f"Total Memberships: {total_memberships}")
    print(f"Total Properties: {total_properties}")

    # Count memberships per collection
    companies_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Companies)
    nodes_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Nodes)
    fuels_coll = sdk.get_collection(ClassEnum.Generator, CollectionEnum.Fuels)
    regions_coll = sdk.get_collection(ClassEnum.System, CollectionEnum.Regions)

    print(f"Generator->Company memberships: "
          f"{Membership.select().where(Membership.collection_id == companies_coll.collection_id).count()}")
    print(f"Generator->Node memberships: "
          f"{Membership.select().where(Membership.collection_id == nodes_coll.collection_id).count()}")
    print(f"Generator->Fuel memberships: "
          f"{Membership.select().where(Membership.collection_id == fuels_coll.collection_id).count()}")
    print(f"System->Region memberships: "
          f"{Membership.select().where(Membership.collection_id == regions_coll.collection_id).count()}")
```

---

## XML Export & Round-Trip

Export the database to XML and verify round-trip fidelity:

```python
# Export DB → XML
converter = XmlConverter()
converter.db_to_xml(DB_PATH, XML_PATH, overwrite=True)

# Round-trip: XML → fresh DB → read
roundtrip_db = "roundtrip_test.db"
with PLEXOSSDK.from_xml(XML_PATH, roundtrip_db) as sdk:
    generators = sdk.get_objects(class_lang_id=ClassEnum.Generator)
    horizons = sdk.list_all_horizons()
    print(f"Generators: {len(generators)}, Horizons: {len(horizons)}")

os.remove(roundtrip_db)
```

---

## Validation

The SDK prevents most invalid state at creation time. Use `validate()` as a diagnostic audit for databases built by external tools or modified outside the SDK:

```python
with PLEXOSSDK(DB_PATH) as sdk:
    warnings = sdk.validate()
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    else:
        print("Database clean — 0 warnings")
```

> **Note:** On large databases this scan checks every data row and may be slow.
