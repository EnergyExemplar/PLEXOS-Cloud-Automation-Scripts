<!--This document must be kept up to date whenever changes to the SDK is made. The SDK is the source of truth. All public methods except for Core SDK Methods, Cache Management should be documented with accurate parameter names, ordinal placement and types -->
# PLEXOS SDK Methods Reference

This document lists all public methods available in the PLEXOS SDK with their type hints and parameters.

## 🔄 Transaction Management

### `transaction(savepoint_name: Optional[str] = None)`
Create transaction context for data integrity.

### `rollback()`
Rollback current transaction.

### `commit()`
Commit current transaction.

### `in_transaction() -> bool`
Check if currently in a transaction.

## 🎯 Object Management

### `add_object(class_lang_id: int, object_name: str, category_obj: Optional[Category] = None, description: Optional[str] = None) -> Object`
Add a new object to the database. System membership is automatically created.

**Raises:**
- `InvalidObjectNameError`: If object name is invalid
- `InvalidClassIdError`: If class ID is invalid
- `ObjectAlreadyExistsError`: If object already exists
- `SystemObjectError`: If trying to create multiple System objects
- `CategoryNotFoundError`: If category is not found

### `get_object(object_id: int) -> Object`
Get object by ID.

**Raises:**
- `ObjectNotFoundError`: If object is not found

### `get_objects(class_lang_id: int) -> List[Object]`
Get objects by class lang_id.

### `get_object_by_name(class_lang_id: int, object_name: str) -> Object`
Get object by name and class lang_id.

**Raises:**
- `InvalidObjectNameError`: If object name is invalid
- `ObjectNotFoundError`: If object is not found

### `remove_object_by_name(class_lang_id: int, object_name: str) -> bool`
Remove object from the database by name and class lang_id.

## 🔗 Membership Management

### `add_membership(collection: Collection, parent: Object, child: Object) -> Membership`
Add membership between parent and child objects.

**Raises:**
- `InvalidObjectClassError`: If parent or child class doesn't match collection
- `MembershipAlreadyExistsError`: If membership already exists

### `remove_membership(parent_class_lang_id: int, collection_lang_id: int, parent_name: str, child_name: str) -> bool`
Remove membership between parent and child objects using deterministic collection lookup.

### `remove_membership(membership: Membership) -> bool`
Remove membership using membership object.

### `get_parent_members(parent_class_lang_id: int, collection_lang_id: int, child_name: str) -> List[Object]`
Get parent members for a child object in a collection using deterministic collection lookup.

### `get_child_members(parent_class_lang_id: int, collection_lang_id: int, parent_name: str) -> List[Object]`
Get child members for a parent object in a collection using deterministic collection lookup.

### `get_child_memberships(parent_class_lang_id: int, collection_lang_id: int, parent_name: str) -> List[Membership]`
Get child memberships for a parent object in a collection using deterministic collection lookup.

### `get_membership_by_child_name(parent_class_lang_id: int, collection_lang_id: int, parent_name: str, child_name: str) -> Membership`
Get membership by child name in a collection using deterministic collection lookup.

**Raises:**
- `MembershipNotFoundError`: If membership is not found

### `get_membership_by_names(parent_class_lang_id: int, collection_lang_id: int, parent_name: str, child_name: str) -> Membership`
Get membership by parent class, collection, and object names for determinism.

**Raises:**
- `MembershipNotFoundError`: If membership is not found

### `get_object_parent_memberships(class_lang_id: int, object_name: str) -> List[Membership]`
Get all parent memberships for an object by name and class lang_id.

### `get_object_child_memberships(class_lang_id: int, object_name: str) -> List[Membership]`
Get all child memberships for an object by name and class lang_id.

### `get_object_all_memberships(class_lang_id: int, object_name: str) -> List[Membership]`
Get all memberships (parent and child) for an object by name and class lang_id.

### `get_object_membership_count(class_lang_id: int, object_name: str) -> dict`
Get membership count for an object by name and class lang_id.

### `get_memberships_by_collection(parent_class_lang_id: int, collection_lang_id: int) -> List[Membership]`
Get all memberships for a collection by parent class and collection lang_id for determinism.

## 📝 Category Management

### `add_category(class_lang_id: int, category_name: str, description: Optional[str] = None) -> Category`
Add a new category for a class.

**Raises:**
- `InvalidObjectNameError`: If category name is invalid
- `CategoryAlreadyExistsError`: If category already exists

### `remove_category(class_lang_id: int, category_name: str) -> bool`
Remove a category from a class.

### `get_categories(class_lang_id: int) -> List[Category]`
Get all categories for a class.

### `add_object_category(class_lang_id: int, object_name: str, category_name: str) -> bool`
Add an object to a category.

### `get_objects_in_category(class_lang_id: int, category_name: str) -> List[Object]`
Get all objects in a category.

### `get_category_by_name(class_lang_id: int, category_name: str) -> Category`
Get category by name for a class.

**Raises:**
- `CategoryNotFoundError`: If category is not found

## ⚙️ Property Management

### `add_property(membership: Membership, property_obj: Property, value: Optional[float] = None, *, data_file_text: Optional[str] = None, time_slice_text: Optional[str] = None, data_file_tag: Optional[Object] = None, scenario_tag: Optional[Object] = None, expression_tag: Optional[Object] = None, band_id: int = 1, period_type_id: Optional[int] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, action: Optional[Union[Action, str]] = None) -> Data`
Add property to membership with strongly typed parameters and optional text/tag creation. Returns hydrated Data object.

**Important Notes:**
- **Actions**: The `action` parameter applies only to `expression_tag` (Variable tags). Scenario tags and Data File tags never receive actions.
- **Automatic Property Configuration**: When `expression_tag` is provided, the SDK automatically:
  - Enables the property (`is_enabled=1`) if not already enabled
  - Sets `is_dynamic=1` to ensure tagged properties display correctly in PLEXOS Desktop
- **Action Specification**: Actions can be provided as Action objects or action_symbol strings (e.g., "×", "FuelPriceMultiplier")

**Raises:**
- `ActionNotFoundError`: If action symbol is provided but action is not found in database
- `ValidationError`: If action is provided but `expression_tag` is not provided

### `get_property_value(membership: Membership, property_obj: Property, band_id: int = 1) -> Optional[float]`
Get property value for membership.

### `remove_property(membership: Membership, property_obj: Property, band_id: int = 1) -> bool`
Remove property from membership.

### `update_property(membership: Membership, property_obj: Property, value: float, band_id: int = 1, period_type_id: int = None) -> Data`
Update property value for membership.

### `get_property_values_with_bands(membership: Membership, property_obj: Property) -> List[tuple[float, int]]`
Get all property values with their band IDs for a membership.

### `get_properties_by_collection(parent_class_lang_id: int, collection_lang_id: int) -> List[Property]`
Get properties by parent class lang_id and collection lang_id for determinism.

### `get_properties_on_membership(membership_id: int) -> List[Property]`
Get properties on a specific membership.

### `get_enabled_properties() -> List[str]`
Get all enabled properties.

### `get_enabled_properties_for_collection(parent_class_lang_id: int, collection_lang_id: int) -> List[Property]`
Get enabled properties for a collection by parent class and collection lang_id for determinism.

## 🔧 Attribute Management

### `add_attribute(object_obj: Object, attribute: Attribute, value: float) -> AttributeData`
Add attribute to object using attribute object.

### `add_attribute_by_lang_id(object_obj: Object, attribute_lang_id: int, value: float) -> AttributeData`
Add attribute to object using lang_id.

### `remove_attribute(object_obj: Object, attribute: Attribute) -> bool`
Remove attribute from object.

### `update_attribute(object_obj: Object, attribute: Attribute, value: float) -> AttributeData`
Update attribute value on object.

### `get_attribute_value(object_obj: Object, attribute: Attribute) -> Optional[float]`
Get attribute value from object.

### `get_attribute_value_by_ids(class_lang_id: int, object_name: str, attribute_lang_id: int) -> Optional[float]`
Get attribute value by class lang_id, object name, and attribute lang_id.

### `get_enabled_attributes_for_class(class_lang_id: int) -> List[Attribute]`
Get enabled attributes for a specific class.

## ⏰ Time Management (Horizons)

### `create_horizon(name: str, date_from: datetime, step_count: int, step_type: int, description: Optional[str] = None, chrono_date_from: Optional[datetime] = None, chrono_step_count: Optional[int] = None, chrono_step_type: Optional[int] = None) -> Object`
Create a new horizon with essential parameters.

### `update_horizon(horizon: Object, date_from: Optional[datetime] = None, step_count: Optional[int] = None, step_type: Optional[int] = None, chrono_date_from: Optional[datetime] = None, chrono_step_count: Optional[int] = None, chrono_step_type: Optional[int] = None) -> Object`
Update horizon parameters as a unit of work.

### `get_horizon_by_name(name: str) -> Object`
Get horizon by name.

**Raises:**
- `ObjectNotFoundError`: If horizon is not found

### `list_all_horizons() -> List[Object]`
Get all horizons in the model.

## 📊 Report Configuration

### `add_report_configuration(object_obj: Object, reporting_lang_id: int, phase_id: int, report_period: bool, report_samples: bool, report_statistics: bool, report_summary: bool, write_flat_files: bool) -> Report`
Add a report configuration for an object-reporting property-phase combination.

### `get_report_configurations(object_obj: Object, reporting_lang_id: int, phase_id: Optional[int] = None) -> List[Report]`
Get report configurations for an object-reporting property combination.

### `configure_report_properties(object_obj: Object, reporting_lang_ids: List[int], phase_id: int = 4, report_period: bool = True, report_samples: bool = False, report_statistics: bool = False, report_summary: bool = True, write_flat_files: bool = False) -> List[Report]`
Configure multiple reporting properties for a Report object.

## 📝 Memo Operations

### `get_memo_data(data: Data) -> Optional[MemoData]`
Get memo for data record.

### `add_memo_data(data: Data, value: str) -> Optional[MemoData]`
Add memo to data record.

### `update_memo_data(data: Data, value: str) -> Optional[MemoData]`
Update memo value for data record.

### `remove_memo_data(data: Data) -> bool`
Remove memo from data record.

### `get_memo_membership(membership: Membership) -> Optional[MemoMembership]`
Get memo for membership record.

### `add_memo_membership(membership: Membership, value: str) -> Optional[MemoMembership]`
Add memo to membership record.

### `update_memo_membership(membership: Membership, value: str) -> Optional[MemoMembership]`
Update memo value for membership record.

### `remove_memo_membership(membership: Membership) -> bool`
Remove memo from membership record.

### `get_memo_object(object: Object, column: CustomColumn) -> Optional[MemoObject]`
Get memo for object and custom column combination.

### `add_memo_object(object: Object, column: CustomColumn, value: str) -> Optional[MemoObject]`
Add memo to object and custom column combination.

### `update_memo_object(object: Object, column: CustomColumn, value: str) -> Optional[MemoObject]`
Update memo value for object and custom column combination.

### `remove_memo_object(object: Object, column: CustomColumn) -> bool`
Remove memo from object and custom column combination.

## 🔍 Lang ID Helper Methods

### `get_class(class_lang_id: int) -> Class` 
Get Class object by class_lang_id.

**Raises:**
- `ClassNotFoundError`: If class is not found

### `get_collection(parent_class_lang_id: int, collection_lang_id: int) -> Collection`
Get Collection object by parent_class_lang_id and collection_lang_id.

**Raises:**
- `CollectionNotFoundError`: If collection is not found

### `get_property(parent_class_lang_id: int, collection_lang_id: int, property_lang_id: int) -> Property`
Get Property object by parent_class_lang_id, collection_lang_id, and property_lang_id for determinism.

**Raises:**
- `PropertyNotFoundError`: If property is not found

### `get_attribute(class_lang_id: int, attribute_lang_id: int) -> Attribute`
Get Attribute object by class_lang_id and attribute_lang_id.

**Raises:**
- `AttributeNotFoundError`: If attribute is not found

## 🛠️ Utility Methods

### `validate_value_by_rule(value: float, validation_rule: str) -> ValidationResult`
Validate value using a validation rule.

### `to_oa_date(dt: datetime) -> float`
Convert Python datetime to PLEXOS OA date format.

### `from_oa_date(oa_date: Union[float, int]) -> datetime`
Convert PLEXOS OA date format to Python datetime.

### `refresh_cache(cache_type: str = None) -> None`
Refresh cache for specified type or all caches if no type specified.


## 🌱 Seed Data Management

### `SQLSeedDataExtractor(source_database_path: str)`
Extract seed data from PLEXOS databases and generate SQL scripts or zip packages.

**Methods:**
- `extract_to_sql(output_path: str, system_type: str = 'universal', version: Optional[str] = None, overwrite: bool = False) -> str`
- `extract_all_system_types(output_directory: str, version: Optional[str] = None, overwrite: bool = False) -> Dict[str, str]`
- `create_seed_data_zip(output_zip_path: str, system_types: List[str] = None, version: Optional[str] = None, overwrite: bool = False) -> str`

### `SQLDatabaseCreator(schema_path: Optional[str] = None)`
Create PLEXOS databases from SQL scripts or zip packages.

**Methods:**
- `create_blank_database(output_path: str) -> str`
- `populate_with_sql(database_path: str, sql_script_path: str) -> None`
- `create_database_from_sql(output_path: str, sql_script_path: str, overwrite: bool = False) -> str`
- `create_database_from_zip(output_path: str, zip_path: str, system_type: str, version: str, overwrite: bool = False) -> str`

### `SQLSeedDataPackager()`
Package SQL scripts into versioned zip files for distribution.

**Methods:**
- `package_sql_scripts(sql_files: Dict[str, str], output_zip_path: str, version: str, metadata: Optional[Dict[str, Any]] = None, overwrite: bool = False) -> str`
- `extract_from_zip(zip_path: str, output_directory: str, version: Optional[str] = None, system_types: Optional[List[str]] = None) -> Dict[str, str]`

### `SeedDataManager(source_database_path: str)`
High-level interface for SQL-based seed data operations.

**Methods:**
- `generate_seed_data_sql(output_directory: str, system_types: List[str] = None, version: Optional[str] = None, overwrite: bool = False) -> Dict[str, str]`
- `create_database(output_path: str, system_type: str, sql_script_path: str, overwrite: bool = False) -> str`
- `create_database_from_zip(output_path: str, zip_path: str, system_type: str, version: str, overwrite: bool = False) -> str`
- `generate_seed_data_zip(output_zip_path: str, system_types: List[str] = None, version: Optional[str] = None, overwrite: bool = False) -> str`

