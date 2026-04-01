# PLEXOS SDK

## Notation

### Basic Types
s=string
i=integer
f=float
b=boolean
dt=datetime
*=any type
[]=array/list

### Markers & Constraints
!=required parameter
?=optional parameter
+=non-empty array/list
==default value
(a|b)=enumeration
[x|y]=exclusive parameters (only one allowed)
(x+y)=parameters must be used together
->returns specific type
<-=value derived from operation

### Core Model Hierarchy & Relationships

#### Primary Models
Object{object_id:i,name:s,class_ref:Class{},category:Category{}?,description:s?,unique_id:s,x:i?,y:i?,z:i?}
Class{class_id:i,name:s,lang_id:i,is_enabled:b,description:s?,class_group:ClassGroup{}?,inherits_from:i?}
ClassGroup{class_group_id:i,name:s,lang_id:i}
Category{category_id:i,name:s,rank:i,class_ref:Class{}}
Collection{collection_id:i,name:s,lang_id:i,is_enabled:b,parent_class:Class{},child_class:Class{},is_one_to_many:b,min_count:i?,max_count:i?,description:s?}

#### Relationship Models
Membership{membership_id:i,parent_object:Object{},child_object:Object{},collection:Collection{},parent_class:Class{}?,child_class:Class{}?}
Property{property_id:i,name:s,lang_id:i,collection:Collection{},is_enabled:b,is_multi_band:b,is_dynamic:b,is_key:b,default_value:f?,validation_rule:s?,unit:Unit{}?,property_group:PropertyGroup{}?,max_band_id:i?,period_type_id:i?}
Attribute{attribute_id:i,name:s,lang_id:i,class_ref:Class{},is_enabled:b,is_integer:b,default_value:f?,validation_rule:s?,unit:Unit{}?}

#### Data Models
Data{data_id:i,value:f,uid:i?,membership:Membership{},property_ref:Property{}}
+Band{data_id:i,band_id:i}?,DateFrom{data_id:i,date:s}?,DateTo{data_id:i,date:s}?,MemoData{data_id:i,value:s}?,Text{data_id:i,class_id:i,value:s}[]?,Tag{data_id:i,object_id:i}[]?

AttributeData{object_id:i,attribute_id:i,value:f} #composite_key

#### Supporting Models
Unit{unit_id:i,value:s,description:s?,default:s?,imperial_energy:s?,metric_level:s?}
PropertyGroup{property_group_id:i,name:s,lang_id:i}
Action{action_id:i,action_symbol:s}
CustomColumn{column_id:i,name:s,position:i,class_ref:Class{},unique_id:s}

#### Memo/Report Models
MemoData{data_id:i,value:s},MemoMembership{membership_id:i,value:s},MemoObject{object_id:i,column_id:i,value:s} #composite_key
Report{object_id:i,property_id:i,phase_id:i,report_period:b,report_samples:b,report_statistics:b,report_summary:b,write_flat_files:b} #composite_key

### Patterns
Context: with PLEXOSSDK(db_path:(s|Path)!) as sdk
Transactions: with sdk.transaction() #required_for_writes
Returns: Hydrated Peewee models with relationships loaded
Auto-creates: Text,Tag,Band,DateFrom,DateTo when params provided

## Core SDK Methods

# Initialize SDK with database connection
PLEXOSSDK(database_path:(s|Path)!)->context_manager
PLEXOSSDK.from_xml(xml_path:(s|Path)!,db_path:(s|Path)!)->PLEXOSSDK

# XML conversion
XmlConverter.xml_to_db(xml_path:s!,db_path:s!,overwrite:b=False)->s
XmlConverter.db_to_xml(db_path:s!,xml_path:s!,overwrite:b=False)->s

# Transaction management for data integrity
transaction(savepoint_name:s?)->context_manager
rollback()->None
commit()->None
in_transaction()->b

# Object operations
add_object(class_lang_id:i!,object_name:s!,category_obj:Category?,description:s?)->Object
get_object(object_id:i!)->Object
get_objects(class_lang_id:i!)->Object[]
get_object_by_name(class_lang_id:i!,object_name:s!)->Object
remove_object_by_name(class_lang_id:i!,object_name:s!)->b

# Membership operations
add_membership(collection:Collection!,parent:Object!,child:Object!)->Membership
remove_membership_by_lang_id(parent_class_lang_id:i!,collection_lang_id:i!,parent_name:s!,child_name:s!)->b
remove_membership(membership:Membership!)->b
get_parent_members(parent_class_lang_id:i!,collection_lang_id:i!,child_name:s!)->Object[]
get_child_members(parent_class_lang_id:i!,collection_lang_id:i!,parent_name:s!)->Object[]
get_child_memberships(parent_class_lang_id:i!,collection_lang_id:i!,parent_name:s!)->Membership[]
get_membership_by_child_name(parent_class_lang_id:i!,collection_lang_id:i!,parent_name:s!,child_name:s!)->Membership
get_membership_by_names(parent_class_lang_id:i!,collection_lang_id:i!,parent_name:s!,child_name:s!)->Membership
get_object_parent_memberships(class_lang_id:i!,object_name:s!)->Membership[]
get_object_child_memberships(class_lang_id:i!,object_name:s!)->Membership[]
get_object_all_memberships(class_lang_id:i!,object_name:s!)->Membership[]
get_object_membership_count(class_lang_id:i!,object_name:s!)->dict
get_memberships_by_collection(parent_class_lang_id:i!,collection_lang_id:i!)->Membership[]

# Property operations
add_property(membership:Membership!,property_obj:Property!,value:f?,data_file_text:s?,time_slice_text:s?,expression_text:s?,data_file_tag:Object?,scenario_tag:Object?,expression_tag:Object?,band_id:i=1,period_type_id:i?,date_from:s?,date_to:s?,action:(Action|s)?)->Data
get_property_value(membership:Membership!,property_obj:Property!,band_id:i=1)->f?
remove_property(membership:Membership!,property_obj:Property!,band_id:i=1)->b
update_property(membership:Membership!,property_obj:Property!,value:f!,band_id:i=1,period_type_id:i?)->Data
get_property_values_with_bands(membership:Membership!,property_obj:Property!)->(f,i)[]
get_property_data_all(membership:Membership!,property_obj:Property!)->Data[]
get_property_data(membership:Membership!,property_obj:Property!,scenario_tag:Object?,expression_tag:Object?,data_file_tag:Object?,band_id:i?,date_from:s?,date_to:s?)->Data?
bulk_add_property(parent_class_lang_id:i!,collection_lang_id:i!,property_obj:Property!,value:f!,scenario_tag:Object!,band_id:i=1,date_from:s?,date_to:s?)->i
bulk_update_property(scenario_tag:Object!,parent_class_lang_id:i?,collection_lang_id:i?,property_obj:Property?,value:f?,transform:Callable?)->i
bulk_delete_property(scenario_tag:Object!,parent_class_lang_id:i?,collection_lang_id:i?,property_obj:Property?)->i
get_properties_by_collection(parent_class_lang_id:i!,collection_lang_id:i!)->Property[]
get_properties_on_membership(membership_id:i!)->Property[]
get_enabled_properties()->s[]
get_enabled_properties_for_collection(parent_class_lang_id:i!,collection_lang_id:i!)->Property[]

# Attribute operations
add_attribute(object_obj:Object!,attribute:Attribute!,value:f!)->AttributeData
add_attribute_by_lang_id(object_obj:Object!,attribute_lang_id:i!,value:f!)->AttributeData
remove_attribute(object_obj:Object!,attribute:Attribute!)->b
update_attribute(object_obj:Object!,attribute:Attribute!,value:f!)->AttributeData
get_attribute_value(object_obj:Object!,attribute:Attribute!)->f?
get_attribute_value_by_ids(class_lang_id:i!,object_name:s!,attribute_lang_id:i!)->f?
get_enabled_attributes_for_class(class_lang_id:i!)->Attribute[]

# Category operations
add_category(class_lang_id:i!,category_name:s!,description:s?)->Category
remove_category(class_lang_id:i!,category_name:s!)->b
get_categories(class_lang_id:i!)->Category[]
add_object_category(class_lang_id:i!,object_name:s!,category_name:s!)->b
get_objects_in_category(class_lang_id:i!,category_name:s!)->Object[]
get_category_by_name(class_lang_id:i!,category_name:s!)->Category

# Time management (Horizons)
create_horizon(name:s!,date_from:dt!,step_count:i!,step_type:i!,description:s?,chrono_date_from:dt?,chrono_step_count:i?,chrono_step_type:i?)->Object
update_horizon(horizon:Object!,date_from:dt?,step_count:i?,step_type:i?,chrono_date_from:dt?,chrono_step_count:i?,chrono_step_type:i?)->Object
get_horizon_by_name(name:s!)->Object
list_all_horizons()->Object[]

# Report configuration
add_report_configuration(object_obj:Object!,reporting_lang_id:i!,phase_id:i!,report_period:b!,report_samples:b!,report_statistics:b!,report_summary:b!,write_flat_files:b!)->Report
get_report_configurations(object_obj:Object!,reporting_lang_id:i!,phase_id:i?)->Report[]
configure_report_properties(object_obj:Object!,reporting_lang_ids:i[]!,phase_id:i=4,report_period:b=True,report_samples:b=False,report_statistics:b=False,report_summary:b=True,write_flat_files:b=False)->Report[]
create_report(model_obj:Object!,report_name:s!,reporting_lang_ids:i[]!,phase_id:i=4,report_period:b=True,report_samples:b=False,report_statistics:b=False,report_summary:b=True,write_flat_files:b=False)->Object

# Memo operations
get_memo_data(data:Data!)->MemoData?
add_memo_data(data:Data!,value:s!)->MemoData?
update_memo_data(data:Data!,value:s!)->MemoData?
remove_memo_data(data:Data!)->b
get_memo_membership(membership:Membership!)->MemoMembership?
add_memo_membership(membership:Membership!,value:s!)->MemoMembership?
update_memo_membership(membership:Membership!,value:s!)->MemoMembership?
remove_memo_membership(membership:Membership!)->b
get_memo_object(object:Object!,column:CustomColumn!)->MemoObject?
add_memo_object(object:Object!,column:CustomColumn!,value:s!)->MemoObject?
update_memo_object(object:Object!,column:CustomColumn!,value:s!)->MemoObject?
remove_memo_object(object:Object!,column:CustomColumn!)->b

# Lang ID helpers
get_class(class_lang_id:i!)->Class
get_collection(parent_class_lang_id:i!,collection_lang_id:i!)->Collection
get_property(parent_class_lang_id:i!,collection_lang_id:i!,property_lang_id:i!)->Property
get_attribute(class_lang_id:i!,attribute_lang_id:i!)->Attribute

# Enum generation
generate_enums(output_dir:(s|Path)?=None,domain_name:s?,save_analysis:b=False)->s

# Utility methods
validate_value_by_rule(value:f!,validation_rule:s!)->ValidationResult
to_oa_date(dt:dt!)->f
from_oa_date(oa_date:(f|i)!)->dt
refresh_cache(cache_type:s?)->None

## Seed Data Management Classes

# SQL-based seed data extraction
SQLSeedDataExtractor(source_database_path:s!)
extract_to_sql(output_path:s!,system_type:s="universal",version:s?,overwrite:b=False)->s
extract_all_system_types(output_directory:s!,version:s?,overwrite:b=False)->dict[s,s]
create_seed_data_zip(output_zip_path:s!,system_types:s[]?,version:s?,overwrite:b=False)->s

# Database creation from SQL
SQLDatabaseCreator(schema_path:s?)
create_blank_database(output_path:s!)->s
populate_with_sql(database_path:s!,sql_script_path:s!)->None
create_database_from_sql(output_path:s!,sql_script_path:s!,overwrite:b=False)->s
create_database_from_zip(output_path:s!,zip_path:s!,system_type:s!,version:s?,overwrite:b=False)->s

# SQL script packaging
SQLSeedDataPackager()
package_sql_scripts(sql_files:dict[s,s]!,output_zip_path:s!,version:s!,metadata:dict[s,*]?,overwrite:b=False)->s
extract_from_zip(zip_path:s!,output_directory:s!,version:s?,system_types:s[]?)->dict[s,s]

# High-level seed data management
SeedDataManager(source_database_path:s!)
generate_seed_data_sql(output_directory:s!,system_types:s[]?,version:s?,overwrite:b=False)->dict[s,s]
create_database(output_path:s!,system_type:s!,sql_script_path:s!,overwrite:b=False)->s
create_database_from_zip(output_path:s!,zip_path:s!,system_type:s!,version:s?,overwrite:b=False)->s
generate_seed_data_zip(output_zip_path:s!,system_types:s[]?,version:s?,overwrite:b=False)->s

## Common Exceptions
InvalidObjectNameError: Object name validation failed
ObjectNotFoundError: Object not found by name/ID
SystemObjectError: Multiple System objects not allowed
CategoryNotFoundError: Category not found
MembershipAlreadyExistsError: Membership already exists
PropertyAlreadyExistsError: Property already exists on membership
AttributeAlreadyExistsError: Attribute already exists on object
InvalidDateError: Date format validation failed (use ISO: "2024-01-01T00:00:00")
ValidationError: Value validation against rule failed
ClassNotFoundError: Class not found by lang_id
CollectionNotFoundError: Collection not found by lang_id
PropertyNotFoundError: Property not found by lang_id
AttributeNotFoundError: Attribute not found by lang_id
ActionNotFoundError: Action not found by action_symbol

## Example
```python
from plexos_sdk import PLEXOSSDK
from plexos_sdk.enums.system_enums import ClassEnum, CollectionEnum, PropertyEnum_Generators

with PLEXOSSDK("model.db") as sdk:
    with sdk.transaction():
        category = sdk.get_category_by_name(ClassEnum.Generator, "Wind")
        gen = sdk.add_object(ClassEnum.Generator, "WindFarm1", category_obj=category)
        membership = sdk.get_membership_by_child_name(ClassEnum.System, CollectionEnum.Generators, "System", "WindFarm1")

        # Auto-creates Text[], DateFrom, DateTo
        data = sdk.add_property(membership, capacity_prop, 500.0,
            data_file_text="wind_capacity.csv", time_slice_text="M1-6",
            date_from="2024-01-01T00:00:00", date_to="2024-12-31T00:00:00")

        attr_data = sdk.add_attribute_by_lang_id(gen, AttributeEnum_Generator.MaxOutput, 600.0)

        # Access via hydrated models
        print(data.property_ref.name, data.membership.collection.name)
```
