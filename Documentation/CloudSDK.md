# CloudSDK Documentation 1.5.2517.414

This document contains comprehensive documentation for all public functions in the CloudSDK, including detailed parameter descriptions, usage examples, and best practices.

## CloudSDK Initialization

```python
from eecloud.cloudsdk import CloudSDK, SDKBase
from eecloud.models import *

pxc: CloudSdk = CloudSDK(cli_path=r"c:\path\to\cli.exe")
```

### Authentication Requirements

**Important:** Unless otherwise specified, all CloudSDK functions require authentication. The typical workflow is:

1. **Environment Setup** - Set your environment using `environment.set_user_environment()`
2. **Authentication** - Authenticate using `auth.login()` or `auth.login_client_credentials()`
3. **Operations** - Execute any other SDK functions

Functions that have special authentication requirements or can be called without authentication will be explicitly documented.

## Table of Contents

- [Environment](#environment)
- [Auth](#auth)
- [Compute](#compute)
- [Datahub](#datahub)
- [Inputdata](#inputdata)
- [Log](#log)
- [Secrets](#secrets)
- [Simulation](#simulation)
- [Solution](#solution)
- [Study](#study)
- [Important Notes](#important-notes)

## Environment

### environment.environment_status

Check the current environment status

**Signature:** `environment_status(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_EnvironmentStatusResponse`

**Response Structure:** 
- `statuses`: Optional[list[Environment_EnvironmentStatus]]
  - `Url`: Optional[str]
  - `Status`: Optional[int]
  - `Message`: Optional[str]
  - `Exception`: Optional[str]

**Example:**
```python
environment_environment_status_resp: list[CommandResponse[Contracts_EnvironmentStatusResponse]] = pxc.environment.environment_status(print_message=True)
environment_environment_status_final: Contracts_EnvironmentStatusResponse = SDKBase.get_response_data(environment_environment_status_resp)

if environment_environment_status_final is not None:
    if environment_environment_status_final.statuses is not None:
        for item in environment_environment_status_final.statuses:
            print(f"Url: {item.Url}")
            print(f"Status: {item.Status}")
            print(f"Message: {item.Message}")
            print(f"Exception: {item.Exception}")
    else:
        print(f"No statuses returned")
else:
    print(f"environment_status failed: {environment_environment_status_resp.Message}")
```

---

### environment.get_user_environment

Get the current user environment configuration

**Signature:** `get_user_environment(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_EnvironmentResponse`

**Response Structure:** 
- `Environment`: Optional[str]

**Example:**
```python
environment_get_user_environment_resp: list[CommandResponse[Contracts_EnvironmentResponse]] = pxc.environment.get_user_environment(print_message=True)
environment_get_user_environment_final: Contracts_EnvironmentResponse = SDKBase.get_response_data(environment_get_user_environment_resp)

if environment_get_user_environment_final is not None:
    print(f"Environment: {environment_get_user_environment_final.Environment}")
else:
    print(f"get_user_environment failed: {environment_get_user_environment_resp.Message}")
```

---

### environment.set_user_environment

Set the user environment for the current session

**Signature:** `set_user_environment(environment: str, print_message: bool)`

**Parameters:**
- `environment` (str) *(required)*: Environment name to connect to
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_EnvironmentResponse`

**Response Structure:** 
- `Environment`: Optional[str]

**Example:**
```python
environment = "NA"

environment_set_user_environment_resp: list[CommandResponse[Contracts_EnvironmentResponse]] = pxc.environment.set_user_environment(environment=environment, print_message=True)
environment_set_user_environment_final: Contracts_EnvironmentResponse = SDKBase.get_response_data(environment_set_user_environment_resp)

if environment_set_user_environment_final is not None:
    print(f"Environment: {environment_set_user_environment_final.Environment}")
else:
    print(f"set_user_environment failed: {environment_set_user_environment_resp.Message}")
```

---

### environment.show_log_file_path

Display the folder path where log files are saved

**Signature:** `show_log_file_path(todays_file: Optional[bool], print_message: bool)`

**Parameters:**
- `todays_file` (Optional[bool]) *(optional)*: Show today's log file path (optional flag) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ShowLogFileResponse`

**Response Structure:** 
- `LoggingPath`: Optional[str]

**Example:**
```python
todays_file = True

environment_show_log_file_path_resp: list[CommandResponse[Contracts_ShowLogFileResponse]] = pxc.environment.show_log_file_path(todays_file=todays_file, print_message=True)
environment_show_log_file_path_final: Contracts_ShowLogFileResponse = SDKBase.get_response_data(environment_show_log_file_path_resp)

if environment_show_log_file_path_final is not None:
    print(f"LoggingPath: {environment_show_log_file_path_final.LoggingPath}")
else:
    print(f"show_log_file_path failed: {environment_show_log_file_path_resp.Message}")
```

---

## Auth

### auth.check_authentication_status

Check if user is currently authenticated

**Signature:** `check_authentication_status(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CheckAuthenticationStatusResponse`

**Response Structure:** 
- `IsAuthenticated`: Optional[bool]
- `Environment`: Optional[str]
- `UserName`: Optional[str]
- `TenantName`: Optional[str]

**Example:**
```python
auth_check_authentication_status_resp: list[CommandResponse[Contracts_CheckAuthenticationStatusResponse]] = pxc.auth.check_authentication_status(print_message=True)
auth_check_authentication_status_final: Contracts_CheckAuthenticationStatusResponse = SDKBase.get_response_data(auth_check_authentication_status_resp)

if auth_check_authentication_status_final is not None:
    print(f"IsAuthenticated: {auth_check_authentication_status_final.IsAuthenticated}")
    print(f"Environment: {auth_check_authentication_status_final.Environment}")
    print(f"UserName: {auth_check_authentication_status_final.UserName}")
    print(f"TenantName: {auth_check_authentication_status_final.TenantName}")
else:
    print(f"check_authentication_status failed: {auth_check_authentication_status_resp.Message}")
```

---

### auth.login_client_credentials

Authenticate using client credentials - automation

**Signature:** `login_client_credentials(use_client_credentials: bool, client_id: str, client_secret: str, tenant_id: str, print_message: bool)`

**Parameters:**
- `use_client_credentials` (bool) *(required)*: use_client_credentials parameter
- `client_id` (str) *(required)*: client_id parameter
- `client_secret` (str) *(required)*: client_secret parameter
- `tenant_id` (str) *(required)*: tenant_id parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_LoginResponse`

**Response Structure:** 
- `IsLoggedIn`: Optional[bool]
- `Environment`: Optional[str]
- `UserName`: Optional[str]
- `TenantName`: Optional[str]

**Example:**
```python
use_client_credentials = True
client_id = "client id"
client_secret = "client secret"
tenant_id = "tenant id"

auth_login_client_credentials_resp: list[CommandResponse[Contracts_LoginResponse]] = pxc.auth.login_client_credentials(
    use_client_credentials=use_client_credentials,
    client_id=client_id,
    client_secret=client_secret,
    tenant_id=tenant_id,
    print_message=True
)
auth_login_client_credentials_final: Contracts_LoginResponse = SDKBase.get_response_data(auth_login_client_credentials_resp)

if auth_login_client_credentials_final is not None:
    print(f"IsLoggedIn: {auth_login_client_credentials_final.IsLoggedIn}")
    print(f"Environment: {auth_login_client_credentials_final.Environment}")
    print(f"UserName: {auth_login_client_credentials_final.UserName}")
    print(f"TenantName: {auth_login_client_credentials_final.TenantName}")
else:
    print(f"login_client_credentials failed: {auth_login_client_credentials_resp.Message}")
```

---

### auth.login

Authenticate user via interactive login - interactive

**Signature:** `login(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_LoginResponse`

**Response Structure:** 
- `IsLoggedIn`: Optional[bool]
- `Environment`: Optional[str]
- `UserName`: Optional[str]
- `TenantName`: Optional[str]

**Example:**
```python
auth_login_resp: list[CommandResponse[Contracts_LoginResponse]] = pxc.auth.login(print_message=True)
auth_login_final: Contracts_LoginResponse = SDKBase.get_response_data(auth_login_resp)

if auth_login_final is not None:
    print(f"IsLoggedIn: {auth_login_final.IsLoggedIn}")
    print(f"Environment: {auth_login_final.Environment}")
    print(f"UserName: {auth_login_final.UserName}")
    print(f"TenantName: {auth_login_final.TenantName}")
else:
    print(f"login failed: {auth_login_resp.Message}")
```

---

### auth.logout

Log out the current user

**Signature:** `logout(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_LoggedOutResponse`

**Response Structure:** 
- `IsLoggedOut`: Optional[bool]

**Example:**
```python
auth_logout_resp: list[CommandResponse[Contracts_LoggedOutResponse]] = pxc.auth.logout(print_message=True)
auth_logout_final: Contracts_LoggedOutResponse = SDKBase.get_response_data(auth_logout_resp)

if auth_logout_final is not None:
    print(f"IsLoggedOut: {auth_logout_final.IsLoggedOut}")
else:
    print(f"logout failed: {auth_logout_resp.Message}")
```

---

## Compute

### compute.create_schedule

Create a recurring schedule for one or more workflows (direct JSON or file)

**Signature:** `create_schedule(name: Optional[str], description: Optional[str], cron_expression: Optional[str], workflows: Optional[str], file_path: Optional[str], print_message: bool)`

**Parameters:**
- `name` (Optional[str]) *(optional)*: Name or identifier for the resource (default: `None`)
- `description` (Optional[str]) *(optional)*: Description text used for filtering or metadata (default: `None`)
- `cron_expression` (Optional[str]) *(optional)*: Cron expression defining schedule frequency (UTC) (default: `None`)
- `workflows` (Optional[str]) *(optional)*: JSON array of workflow configuration objects for schedule create/update (default: `None`)
- `file_path` (Optional[str]) *(optional)*: file_path parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CreateScheduleResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `ScheduleId`: Optional[str]
- `CreatedDate`: Optional[str]

**Example:**
```python
name = "My Name"
description = "Description"
cron_expression = "0 0 * * *"
workflows = '[ {\"workflowId\": \"550e8400-e29b-41d4-a716-446655440000\", \"executionOrder\": 1} ]'
file_path = r"c:\path\to\file.txt"

compute_create_schedule_resp: list[CommandResponse[Contracts_CreateScheduleResponse]] = pxc.compute.create_schedule(
    name=name,
    description=description,
    cron_expression=cron_expression,
    workflows=workflows,
    file_path=file_path,
    print_message=True
)
compute_create_schedule_final: Contracts_CreateScheduleResponse = SDKBase.get_response_data(compute_create_schedule_resp)

if compute_create_schedule_final is not None:
    print(f"Success: {compute_create_schedule_final.Success}")
    print(f"ScheduleId: {compute_create_schedule_final.ScheduleId}")
    print(f"CreatedDate: {compute_create_schedule_final.CreatedDate}")
else:
    print(f"create_schedule failed: {compute_create_schedule_resp.Message}")
```

---

### compute.delete_schedule

Delete a recurring schedule

**Signature:** `delete_schedule(schedule_id: str, print_message: bool)`

**Parameters:**
- `schedule_id` (str) *(required)*: Identifier for a recurring schedule
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DeleteScheduleResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Message`: Optional[str]

**Example:**
```python
schedule_id = "550e8400-e29b-41d4-a716-446655440000"

compute_delete_schedule_resp: list[CommandResponse[Contracts_DeleteScheduleResponse]] = pxc.compute.delete_schedule(schedule_id=schedule_id, print_message=True)
compute_delete_schedule_final: Contracts_DeleteScheduleResponse = SDKBase.get_response_data(compute_delete_schedule_resp)

if compute_delete_schedule_final is not None:
    print(f"Success: {compute_delete_schedule_final.Success}")
    print(f"Message: {compute_delete_schedule_final.Message}")
else:
    print(f"delete_schedule failed: {compute_delete_schedule_resp.Message}")
```

---

### compute.execute_schedule

Trigger a schedule execution immediately ignoring cron timing

**Signature:** `execute_schedule(schedule_id: str, print_message: bool)`

**Parameters:**
- `schedule_id` (str) *(required)*: Identifier for a recurring schedule
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ExecuteScheduleResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `ExecutionDate`: Optional[str]

**Example:**
```python
schedule_id = "550e8400-e29b-41d4-a716-446655440000"

compute_execute_schedule_resp: list[CommandResponse[Contracts_ExecuteScheduleResponse]] = pxc.compute.execute_schedule(schedule_id=schedule_id, print_message=True)
compute_execute_schedule_final: Contracts_ExecuteScheduleResponse = SDKBase.get_response_data(compute_execute_schedule_resp)

if compute_execute_schedule_final is not None:
    print(f"Success: {compute_execute_schedule_final.Success}")
    print(f"ExecutionDate: {compute_execute_schedule_final.ExecutionDate}")
else:
    print(f"execute_schedule failed: {compute_execute_schedule_resp.Message}")
```

---

### compute.list_schedules

List existing recurring schedules

**Signature:** `list_schedules(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSchedulesResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Schedules`: Optional[list[Compute_ScheduleListItem]]
  - `Id`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `CronExpression`: Optional[str]
  - `Status`: Optional[str]
  - `ScheduleType`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `DeletedDate`: Optional[str]
  - `Workflows`: Optional[list[Compute_ScheduledWorkflow]]
    - `WorkflowId`: Optional[str]
    - `ExecutionOrder`: Optional[int]

**Example:**
```python
compute_list_schedules_resp: list[CommandResponse[Contracts_ListSchedulesResponse]] = pxc.compute.list_schedules(print_message=True)
compute_list_schedules_final: Contracts_ListSchedulesResponse = SDKBase.get_response_data(compute_list_schedules_resp)

if compute_list_schedules_final is not None:
    print(f"Success: {compute_list_schedules_final.Success}")
    if compute_list_schedules_final.Schedules is not None:
        for item in compute_list_schedules_final.Schedules:
            print(f"Id: {item.Id}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"CronExpression: {item.CronExpression}")
            # ... and 5 more properties
    else:
        print(f"No Schedules returned")
else:
    print(f"list_schedules failed: {compute_list_schedules_resp.Message}")
```

---

### compute.update_schedule

Update a recurring schedule's metadata or activation state

**Signature:** `update_schedule(schedule_id: str, name: Optional[str], description: Optional[str], cron_expression: Optional[str], is_active: Optional[bool], workflows: Optional[str], print_message: bool)`

**Parameters:**
- `schedule_id` (str) *(required)*: Identifier for a recurring schedule
- `name` (Optional[str]) *(optional)*: Name or identifier for the resource (default: `None`)
- `description` (Optional[str]) *(optional)*: Description text used for filtering or metadata (default: `None`)
- `cron_expression` (Optional[str]) *(optional)*: Cron expression defining schedule frequency (UTC) (default: `None`)
- `is_active` (Optional[bool]) *(optional)*: Activate or deactivate a schedule (default: `None`)
- `workflows` (Optional[str]) *(optional)*: JSON array of workflow configuration objects for schedule create/update (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_UpdateScheduleResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Message`: Optional[str]

**Example:**
```python
schedule_id = "550e8400-e29b-41d4-a716-446655440000"
name = "My Name"
description = "Description"
cron_expression = "0 0 * * *"
is_active = True
workflows = '[ {\"workflowId\": \"550e8400-e29b-41d4-a716-446655440000\", \"executionOrder\": 1} ]'

compute_update_schedule_resp: list[CommandResponse[Contracts_UpdateScheduleResponse]] = pxc.compute.update_schedule(
    schedule_id=schedule_id,
    name=name,
    description=description,
    cron_expression=cron_expression,
    is_active=is_active,
    workflows=workflows,
    print_message=True
)
compute_update_schedule_final: Contracts_UpdateScheduleResponse = SDKBase.get_response_data(compute_update_schedule_resp)

if compute_update_schedule_final is not None:
    print(f"Success: {compute_update_schedule_final.Success}")
    print(f"Message: {compute_update_schedule_final.Message}")
else:
    print(f"update_schedule failed: {compute_update_schedule_resp.Message}")
```

---

### compute.cancel_executions

Request cancellation of a running workflow execution or sub-scope (attempt, stage, task)

**Signature:** `cancel_executions(execution_id: Optional[str], attempt_id: Optional[str], stage_id: Optional[str], task_id: Optional[str], force: Optional[bool], print_message: bool)`

**Parameters:**
- `execution_id` (Optional[str]) *(optional)*: Unique identifier for a specific execution (default: `None`)
- `attempt_id` (Optional[str]) *(optional)*: Attempt identifier for attempt-level operations (default: `None`)
- `stage_id` (Optional[str]) *(optional)*: Stage identifier for stage-level cancellation (default: `None`)
- `task_id` (Optional[str]) *(optional)*: Task identifier for task-level cancellation (default: `None`)
- `force` (Optional[bool]) *(optional)*: Force an operation without interactive confirmation (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CancelExecutionResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Message`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"
attempt_id = "550e8400-e29b-41d4-a716-446655440000"
stage_id = "550e8400-e29b-41d4-a716-446655440000"
task_id = "550e8400-e29b-41d4-a716-446655440000"
force = "value"

compute_cancel_executions_resp: list[CommandResponse[Contracts_CancelExecutionResponse]] = pxc.compute.cancel_executions(
    execution_id=execution_id,
    attempt_id=attempt_id,
    stage_id=stage_id,
    task_id=task_id,
    force=force,
    print_message=True
)
compute_cancel_executions_final: Contracts_CancelExecutionResponse = SDKBase.get_response_data(compute_cancel_executions_resp)

if compute_cancel_executions_final is not None:
    print(f"Success: {compute_cancel_executions_final.Success}")
    print(f"Message: {compute_cancel_executions_final.Message}")
else:
    print(f"cancel_executions failed: {compute_cancel_executions_resp.Message}")
```

---

### compute.get_executions

List workflow executions

**Signature:** `get_executions(execution_id: Optional[str], status: Optional[str], started_after: Optional[str], started_before: Optional[str], sort_field: Optional[str], sort_direction: Optional[GraphQL_SortEnumType], print_message: bool)`

**Parameters:**
- `execution_id` (Optional[str]) *(optional)*: Unique identifier for a specific execution (default: `None`)
- `status` (Optional[str]) *(optional)*: Execution status value used for filtering (default: `None`)
- `started_after` (Optional[str]) *(optional)*: Filter entities started at or after this UTC timestamp (default: `None`)
- `started_before` (Optional[str]) *(optional)*: Filter entities started at or before this UTC timestamp (default: `None`)
- `sort_field` (Optional[str]) *(optional)*: Field name to sort results by (default: `None`)
- `sort_direction` (Optional[GraphQL_SortEnumType]) *(optional)*: Direction to sort results (ASC or DESC) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetExecutionsResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `ExecutionStatuses`: Optional[list[GraphQL_ExecutionStatus]]
  - `Id`: Optional[str]
  - `Status`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `StartedDate`: Optional[str]
  - `CompletedDate`: Optional[str]
  - `Workflows`: Optional[list[GraphQL_ExecutionWorkflowStatus]]
    - `WorkflowId`: Optional[str]
    - `Stages`: Optional[list[GraphQL_ExecutionStage]]
      - `Id`: Optional[str]
      - `CreatedDate`: Optional[str]
      - `Description`: Optional[str]
      - `Demands`: Optional[str]
      - `Definition`: Optional[str]
      - `Attempts`: Optional[list[GraphQL_StageAttempt]]
        - `Id`: Optional[str]
        - `CreatedDate`: Optional[str]
        - `StageId`: Optional[str]
        - `WorkflowId`: Optional[str]
        - `ExecutionId`: Optional[str]
        - `StartedDate`: Optional[str]
        - `CompletedDate`: Optional[str]
        - `Status`: Optional[str]
        - `TaskStatuses`: Optional[list[GraphQL_StageAttemptTaskStatus]]
          - `Id`: Optional[str]
          - `TaskName`: Optional[str]
          - `Status`: Optional[str]
          - `Timestamp`: Optional[str]
          - `Message`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"
status = "Active"
started_after = "2025-01-01T00:00:00Z"
started_before = "2025-12-31T23:59:59Z"
sort_field = "createdDate"
sort_direction = "ASC"

compute_get_executions_resp: list[CommandResponse[Contracts_GetExecutionsResponse]] = pxc.compute.get_executions(
    execution_id=execution_id,
    status=status,
    started_after=started_after,
    started_before=started_before,
    sort_field=sort_field,
    sort_direction=sort_direction,
    print_message=True
)
compute_get_executions_final: Contracts_GetExecutionsResponse = SDKBase.get_response_data(compute_get_executions_resp)

if compute_get_executions_final is not None:
    print(f"Success: {compute_get_executions_final.Success}")
    if compute_get_executions_final.ExecutionStatuses is not None:
        for item in compute_get_executions_final.ExecutionStatuses:
            print(f"Id: {item.Id}")
            print(f"Status: {item.Status}")
            print(f"CreatedDate: {item.CreatedDate}")
            print(f"StartedDate: {item.StartedDate}")
            # ... and 2 more properties
    else:
        print(f"No ExecutionStatuses returned")
else:
    print(f"get_executions failed: {compute_get_executions_resp.Message}")
```

---

### compute.get_stage_attempts

List stage attempts for workflow executions

**Signature:** `get_stage_attempts(execution_id: Optional[str], stage_id: Optional[str], workflow_id: Optional[str], status: Optional[str], started_after: Optional[str], started_before: Optional[str], sort_field: Optional[str], sort_direction: Optional[GraphQL_SortEnumType], print_message: bool)`

**Parameters:**
- `execution_id` (Optional[str]) *(optional)*: Unique identifier for a specific execution (default: `None`)
- `stage_id` (Optional[str]) *(optional)*: Stage identifier for stage-level cancellation (default: `None`)
- `workflow_id` (Optional[str]) *(optional)*: Unique identifier for a specific workflow (default: `None`)
- `status` (Optional[str]) *(optional)*: Execution status value used for filtering (default: `None`)
- `started_after` (Optional[str]) *(optional)*: Filter entities started at or after this UTC timestamp (default: `None`)
- `started_before` (Optional[str]) *(optional)*: Filter entities started at or before this UTC timestamp (default: `None`)
- `sort_field` (Optional[str]) *(optional)*: Field name to sort results by (default: `None`)
- `sort_direction` (Optional[GraphQL_SortEnumType]) *(optional)*: Direction to sort results (ASC or DESC) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetStageAttemptsResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `ExecutionStatuses`: Optional[list[Compute_StageAttemptResult]]
  - `Id`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `StageId`: Optional[str]
  - `WorkflowId`: Optional[str]
  - `ExecutionId`: Optional[str]
  - `StartedDate`: Optional[str]
  - `CompletedDate`: Optional[str]
  - `Status`: Optional[str]
  - `TaskStatuses`: Optional[list[Compute_StageAttemptTaskResult]]
    - `Id`: Optional[str]
    - `TaskName`: Optional[str]
    - `Timestamp`: Optional[str]
    - `Status`: Optional[str]
    - `Message`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"
stage_id = "550e8400-e29b-41d4-a716-446655440000"
workflow_id = "550e8400-e29b-41d4-a716-446655440000"
status = "Active"
started_after = "2025-01-01T00:00:00Z"
started_before = "2025-12-31T23:59:59Z"
sort_field = "createdDate"
sort_direction = "ASC"

compute_get_stage_attempts_resp: list[CommandResponse[Contracts_GetStageAttemptsResponse]] = pxc.compute.get_stage_attempts(
    execution_id=execution_id,
    stage_id=stage_id,
    workflow_id=workflow_id,
    status=status,
    started_after=started_after,
    started_before=started_before,
    sort_field=sort_field,
    sort_direction=sort_direction,
    print_message=True
)
compute_get_stage_attempts_final: Contracts_GetStageAttemptsResponse = SDKBase.get_response_data(compute_get_stage_attempts_resp)

if compute_get_stage_attempts_final is not None:
    print(f"Success: {compute_get_stage_attempts_final.Success}")
    if compute_get_stage_attempts_final.ExecutionStatuses is not None:
        for item in compute_get_stage_attempts_final.ExecutionStatuses:
            print(f"Id: {item.Id}")
            print(f"CreatedDate: {item.CreatedDate}")
            print(f"StageId: {item.StageId}")
            print(f"WorkflowId: {item.WorkflowId}")
            # ... and 5 more properties
    else:
        print(f"No ExecutionStatuses returned")
else:
    print(f"get_stage_attempts failed: {compute_get_stage_attempts_resp.Message}")
```

---

### compute.create_workflow

Create a new workflow definition from a JSON file

**Signature:** `create_workflow(workflow_file_path: str, print_message: bool)`

**Parameters:**
- `workflow_file_path` (str) *(required)*: workflow_file_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CreateWorkflowResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `WorkflowId`: Optional[str]
- `CreatedDate`: Optional[str]

**Example:**
```python
workflow_file_path = "workflow file path"

compute_create_workflow_resp: list[CommandResponse[Contracts_CreateWorkflowResponse]] = pxc.compute.create_workflow(workflow_file_path=workflow_file_path, print_message=True)
compute_create_workflow_final: Contracts_CreateWorkflowResponse = SDKBase.get_response_data(compute_create_workflow_resp)

if compute_create_workflow_final is not None:
    print(f"Success: {compute_create_workflow_final.Success}")
    print(f"WorkflowId: {compute_create_workflow_final.WorkflowId}")
    print(f"CreatedDate: {compute_create_workflow_final.CreatedDate}")
else:
    print(f"create_workflow failed: {compute_create_workflow_resp.Message}")
```

---

### compute.delete_workflow

Delete (soft delete) an existing workflow definition

**Signature:** `delete_workflow(workflow_id: str, print_message: bool)`

**Parameters:**
- `workflow_id` (str) *(required)*: Unique identifier for a specific workflow
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DeleteWorkflowResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `WorkflowId`: Optional[str]

**Example:**
```python
workflow_id = "550e8400-e29b-41d4-a716-446655440000"

compute_delete_workflow_resp: list[CommandResponse[Contracts_DeleteWorkflowResponse]] = pxc.compute.delete_workflow(workflow_id=workflow_id, print_message=True)
compute_delete_workflow_final: Contracts_DeleteWorkflowResponse = SDKBase.get_response_data(compute_delete_workflow_resp)

if compute_delete_workflow_final is not None:
    print(f"Success: {compute_delete_workflow_final.Success}")
    print(f"WorkflowId: {compute_delete_workflow_final.WorkflowId}")
else:
    print(f"delete_workflow failed: {compute_delete_workflow_resp.Message}")
```

---

### compute.enqueue_workflow

Enqueue an existing workflow for immediate execution

**Signature:** `enqueue_workflow(workflow_id: str, print_message: bool)`

**Parameters:**
- `workflow_id` (str) *(required)*: Unique identifier for a specific workflow
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_EnqueueWorkflowResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `ExecutionId`: Optional[str]
- `CreatedDate`: Optional[str]

**Example:**
```python
workflow_id = "550e8400-e29b-41d4-a716-446655440000"

compute_enqueue_workflow_resp: list[CommandResponse[Contracts_EnqueueWorkflowResponse]] = pxc.compute.enqueue_workflow(workflow_id=workflow_id, print_message=True)
compute_enqueue_workflow_final: Contracts_EnqueueWorkflowResponse = SDKBase.get_response_data(compute_enqueue_workflow_resp)

if compute_enqueue_workflow_final is not None:
    print(f"Success: {compute_enqueue_workflow_final.Success}")
    print(f"ExecutionId: {compute_enqueue_workflow_final.ExecutionId}")
    print(f"CreatedDate: {compute_enqueue_workflow_final.CreatedDate}")
else:
    print(f"enqueue_workflow failed: {compute_enqueue_workflow_resp.Message}")
```

---

### compute.list_workflows

List workflow definitions with optional filtering and sorting

**Signature:** `list_workflows(description: Optional[str], created_after: Optional[str], created_before: Optional[str], created_by_user_id: Optional[str], include_deleted: Optional[bool], sort_field: Optional[str], sort_direction: Optional[GraphQL_SortEnumType], print_message: bool)`

**Parameters:**
- `description` (Optional[str]) *(optional)*: Description text used for filtering or metadata (default: `None`)
- `created_after` (Optional[str]) *(optional)*: Filter items created at or after this UTC timestamp (default: `None`)
- `created_before` (Optional[str]) *(optional)*: Filter items created at or before this UTC timestamp (default: `None`)
- `created_by_user_id` (Optional[str]) *(optional)*: Filter by the user who created the resource (default: `None`)
- `include_deleted` (Optional[bool]) *(optional)*: Include soft-deleted entities when listing (default: `None`)
- `sort_field` (Optional[str]) *(optional)*: Field name to sort results by (default: `None`)
- `sort_direction` (Optional[GraphQL_SortEnumType]) *(optional)*: Direction to sort results (ASC or DESC) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListWorkflowsResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Workflows`: Optional[list[Compute_WorkflowInfo]]
  - `WorkflowId`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `ModifiedDate`: Optional[str]
  - `DeletedDate`: Optional[str]
  - `TenantId`: Optional[str]
  - `CreatedByUserId`: Optional[str]
  - `DeletedByUserId`: Optional[str]
  - `Description`: Optional[str]
  - `Demands`: Optional[list[dict[(Any, Any)]]]
  - `Executions`: Optional[list[Compute_ExecutionInfo]]
    - `ExecutionId`: Optional[str]
    - `WorkflowExecutionId`: Optional[str]
    - `Stages`: Optional[list[Compute_WorkflowStageInfo]]
      - `StageId`: Optional[str]
      - `Description`: Optional[str]
      - `Tasks`: Optional[list[dict[(Any, Any)]]]
      - `Demands`: Optional[list[dict[(Any, Any)]]]

**Example:**
```python
description = "Description"
created_after = "2025-01-01T00:00:00Z"
created_before = "2025-12-31T23:59:59Z"
created_by_user_id = "550e8400-e29b-41d4-a716-446655440000"
include_deleted = True
sort_field = "createdDate"
sort_direction = "ASC"

compute_list_workflows_resp: list[CommandResponse[Contracts_ListWorkflowsResponse]] = pxc.compute.list_workflows(
    description=description,
    created_after=created_after,
    created_before=created_before,
    created_by_user_id=created_by_user_id,
    include_deleted=include_deleted,
    sort_field=sort_field,
    sort_direction=sort_direction,
    print_message=True
)
compute_list_workflows_final: Contracts_ListWorkflowsResponse = SDKBase.get_response_data(compute_list_workflows_resp)

if compute_list_workflows_final is not None:
    print(f"Success: {compute_list_workflows_final.Success}")
    if compute_list_workflows_final.Workflows is not None:
        for item in compute_list_workflows_final.Workflows:
            print(f"WorkflowId: {item.WorkflowId}")
            print(f"CreatedDate: {item.CreatedDate}")
            print(f"ModifiedDate: {item.ModifiedDate}")
            print(f"DeletedDate: {item.DeletedDate}")
            # ... and 6 more properties
    else:
        print(f"No Workflows returned")
else:
    print(f"list_workflows failed: {compute_list_workflows_resp.Message}")
```

---

### compute.update_workflow

Update an existing workflow definition from a JSON file

**Signature:** `update_workflow(workflow_id: str, file: str, print_message: bool)`

**Parameters:**
- `workflow_id` (str) *(required)*: Unique identifier for a specific workflow
- `file` (str) *(required)*: file parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_UpdateWorkflowResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `WorkflowId`: Optional[str]
- `UpdatedDate`: Optional[str]

**Example:**
```python
workflow_id = "550e8400-e29b-41d4-a716-446655440000"
file = "data.csv"

compute_update_workflow_resp: list[CommandResponse[Contracts_UpdateWorkflowResponse]] = pxc.compute.update_workflow(workflow_id=workflow_id, file=file, print_message=True)
compute_update_workflow_final: Contracts_UpdateWorkflowResponse = SDKBase.get_response_data(compute_update_workflow_resp)

if compute_update_workflow_final is not None:
    print(f"Success: {compute_update_workflow_final.Success}")
    print(f"WorkflowId: {compute_update_workflow_final.WorkflowId}")
    print(f"UpdatedDate: {compute_update_workflow_final.UpdatedDate}")
else:
    print(f"update_workflow failed: {compute_update_workflow_resp.Message}")
```

---

### compute.list_tasks

List available tasks with inputs and metadata

**Signature:** `list_tasks(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListTasksResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Tasks`: Optional[list[Compute_TaskInfo]]
  - `CapabilityName`: Optional[str]
  - `DisplayName`: Optional[str]
  - `Description`: Optional[str]
  - `Category`: Optional[str]
  - `Inputs`: Optional[list[Compute_TaskInputInfo]]
    - `Name`: Optional[str]
    - `DisplayName`: Optional[str]
    - `Description`: Optional[str]

**Example:**
```python
compute_list_tasks_resp: list[CommandResponse[Contracts_ListTasksResponse]] = pxc.compute.list_tasks(print_message=True)
compute_list_tasks_final: Contracts_ListTasksResponse = SDKBase.get_response_data(compute_list_tasks_resp)

if compute_list_tasks_final is not None:
    print(f"Success: {compute_list_tasks_final.Success}")
    if compute_list_tasks_final.Tasks is not None:
        for item in compute_list_tasks_final.Tasks:
            print(f"CapabilityName: {item.CapabilityName}")
            print(f"DisplayName: {item.DisplayName}")
            print(f"Description: {item.Description}")
            print(f"Category: {item.Category}")
            # ... and 1 more properties
    else:
        print(f"No Tasks returned")
else:
    print(f"list_tasks failed: {compute_list_tasks_resp.Message}")
```

---

### compute.list_capabilities

List available compute capabilities (building blocks for tasks)

**Signature:** `list_capabilities(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListCapabilitiesResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Capabilities`: Optional[list[Compute_CapabilityInfo]]
  - `DisplayName`: Optional[str]
  - `CapabilityName`: Optional[str]
  - `Description`: Optional[str]
  - `Options`: Optional[list[Compute_CapabilityOption]]
    - `Value`: Optional[str]
    - `Description`: Optional[str]

**Example:**
```python
compute_list_capabilities_resp: list[CommandResponse[Contracts_ListCapabilitiesResponse]] = pxc.compute.list_capabilities(print_message=True)
compute_list_capabilities_final: Contracts_ListCapabilitiesResponse = SDKBase.get_response_data(compute_list_capabilities_resp)

if compute_list_capabilities_final is not None:
    print(f"Success: {compute_list_capabilities_final.Success}")
    if compute_list_capabilities_final.Capabilities is not None:
        for item in compute_list_capabilities_final.Capabilities:
            print(f"DisplayName: {item.DisplayName}")
            print(f"CapabilityName: {item.CapabilityName}")
            print(f"Description: {item.Description}")
            print(f"Options: {item.Options}")
    else:
        print(f"No Capabilities returned")
else:
    print(f"list_capabilities failed: {compute_list_capabilities_resp.Message}")
```

---

## Datahub

### datahub.delete

Delete files from Datahub

**Signature:** `delete(remote_glob_patterns: list[str], permanent: Optional[bool], confirm: Optional[bool], print_message: bool)`

**Parameters:**
- `remote_glob_patterns` (list[str]) *(required)*: Glob patterns to match remote files
- `permanent` (Optional[bool]) *(optional)*: permanent parameter (default: `None`)
- `confirm` (Optional[bool]) *(optional)*: Skip confirmation prompt for destructive operations (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeleteResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `QueuedForDeletion`: Optional[list[str]]

**Example:**
```python
remote_glob_patterns = ["folder/**/*.csv", "folder/**/*.parquet"]
permanent = "value"
confirm = True

datahub_delete_resp: list[CommandResponse[Contracts_DatahubDeleteResponse]] = pxc.datahub.delete(remote_glob_patterns=remote_glob_patterns, permanent=permanent, confirm=confirm, print_message=True)
datahub_delete_final: Contracts_DatahubDeleteResponse = SDKBase.get_response_data(datahub_delete_resp)

if datahub_delete_final is not None:
    print(f"Success: {datahub_delete_final.Success}")
    if datahub_delete_final.QueuedForDeletion is not None:
        for item in datahub_delete_final.QueuedForDeletion:
            print(f"Item: {item}")
    else:
        print(f"No QueuedForDeletion returned")
else:
    print(f"delete failed: {datahub_delete_resp.Message}")
```

---

### datahub.download

Download files from Datahub using glob patterns

**Signature:** `download(remote_glob_patterns: Optional[list[str]], output_directory: Optional[str], version: Optional[int], snapshot_date: Optional[str], manifest_file_path: Optional[str], verify_download: Optional[bool], create_metadata_file: Optional[bool], what_if_verification: Optional[bool], parallel_download: Optional[bool], max_parallel: Optional[int], include_deleted_files: Optional[bool], print_message: bool)`

**Parameters:**
- `remote_glob_patterns` (Optional[list[str]]) *(optional)*: Glob patterns to match remote files (default: `None`)
- `output_directory` (Optional[str]) *(optional)*: Local directory to save downloaded files (default: `None`)
- `version` (Optional[int]) *(optional)*: Version of the files to download (default: `None`)
- `snapshot_date` (Optional[str]) *(optional)*: Specific snapshot date to download files from (default: `None`)
- `manifest_file_path` (Optional[str]) *(optional)*: Path to manifest file for download operations (default: `None`)
- `verify_download` (Optional[bool]) *(optional)*: Verify downloaded files for integrity (default: `None`)
- `create_metadata_file` (Optional[bool]) *(optional)*: Create metadata file during download (default: `None`)
- `what_if_verification` (Optional[bool]) *(optional)*: Perform what-if verification without actual download (default: `None`)
- `parallel_download` (Optional[bool]) *(optional)*: Enable parallel downloading for better performance (default: `None`)
- `max_parallel` (Optional[int]) *(optional)*: Maximum number of parallel download threads (default: `None`)
- `include_deleted_files` (Optional[bool]) *(optional)*: include_deleted_files parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubCommandResponse`

**Response Structure:** 
- `DatahubCommandStatus`: Optional[Datahub_DatahubCommandStatus]
- `DatahubResourceResults`: Optional[list[Datahub_DatahubResourceResult]]
  - `RelativeFilePath`: Optional[str]
  - `RelativeToDirectoryOutputPath`: Optional[str]
  - `LocalFilePath`: Optional[str]
  - `FailureReason`: Optional[str]
  - `Success`: Optional[bool]
  - `Version`: Optional[int]
  - `IsFromConnector`: Optional[bool]
  - `SnapshotDateUtc`: Optional[str]

**Example:**
```python
remote_glob_patterns = ["folder/**/*.csv", "folder/**/*.parquet"]
output_directory = r"c:\output"
version = "1.0"
snapshot_date = "value"
manifest_file_path = r"c:\path\to\manifest.csv"
verify_download = True
create_metadata_file = True
what_if_verification = True
parallel_download = True
max_parallel = 4
include_deleted_files = True

datahub_download_resp: list[CommandResponse[Contracts_DatahubCommandResponse]] = pxc.datahub.download(
    remote_glob_patterns=remote_glob_patterns,
    output_directory=output_directory,
    version=version,
    snapshot_date=snapshot_date,
    manifest_file_path=manifest_file_path,
    verify_download=verify_download,
    create_metadata_file=create_metadata_file,
    what_if_verification=what_if_verification,
    parallel_download=parallel_download,
    max_parallel=max_parallel,
    include_deleted_files=include_deleted_files,
    print_message=True
)
datahub_download_final: Contracts_DatahubCommandResponse = SDKBase.get_response_data(datahub_download_resp)

if datahub_download_final is not None:
    print(f"DatahubCommandStatus: {datahub_download_final.DatahubCommandStatus}")
    if datahub_download_final.DatahubResourceResults is not None:
        for item in datahub_download_final.DatahubResourceResults:
            print(f"RelativeFilePath: {item.RelativeFilePath}")
            print(f"RelativeToDirectoryOutputPath: {item.RelativeToDirectoryOutputPath}")
            print(f"LocalFilePath: {item.LocalFilePath}")
            print(f"FailureReason: {item.FailureReason}")
            # ... and 4 more properties
    else:
        print(f"No DatahubResourceResults returned")
else:
    print(f"download failed: {datahub_download_resp.Message}")
```

---

### datahub.query

Executes SQL queries against Datahub resource

**Signature:** `query(sql: str, multiple_relative_path: Optional[list[str]], relative_path: Optional[str], print_message: bool)`

**Parameters:**
- `sql` (str) *(required)*: SQL query to execute
- `multiple_relative_path` (Optional[list[str]]) *(optional)*: multiple_relative_path parameter (default: `None`)
- `relative_path` (Optional[str]) *(optional)*: relative_path parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubQueryResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Results`: Optional[list[dict[(str, str)]]]

**Example:**
```python
sql = "select * from fullkeyinfo"
multiple_relative_path = "value"
relative_path = "value"

datahub_query_resp: list[CommandResponse[Contracts_DatahubQueryResponse]] = pxc.datahub.query(sql=sql, multiple_relative_path=multiple_relative_path, relative_path=relative_path, print_message=True)
datahub_query_final: Contracts_DatahubQueryResponse = SDKBase.get_response_data(datahub_query_resp)

if datahub_query_final is not None:
    print(f"Success: {datahub_query_final.Success}")
    if datahub_query_final.Results is not None:
        for item in datahub_query_final.Results:
            print(f"Item: {item}")
    else:
        print(f"No Results returned")
else:
    print(f"query failed: {datahub_query_resp.Message}")
```

---

### datahub.revert

Revert files to a previous version

**Signature:** `revert(file_revert_path: str, version: Optional[int], snapshot_date: Optional[str], verify_download: Optional[bool], print_message: bool)`

**Parameters:**
- `file_revert_path` (str) *(required)*: file_revert_path parameter
- `version` (Optional[int]) *(optional)*: Version of the files to download (default: `None`)
- `snapshot_date` (Optional[str]) *(optional)*: Specific snapshot date to download files from (default: `None`)
- `verify_download` (Optional[bool]) *(optional)*: Verify downloaded files for integrity (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubCommandResponse`

**Response Structure:** 
- `DatahubCommandStatus`: Optional[Datahub_DatahubCommandStatus]
- `DatahubResourceResults`: Optional[list[Datahub_DatahubResourceResult]]
  - `RelativeFilePath`: Optional[str]
  - `RelativeToDirectoryOutputPath`: Optional[str]
  - `LocalFilePath`: Optional[str]
  - `FailureReason`: Optional[str]
  - `Success`: Optional[bool]
  - `Version`: Optional[int]
  - `IsFromConnector`: Optional[bool]
  - `SnapshotDateUtc`: Optional[str]

**Example:**
```python
file_revert_path = r"/path/folder/file.csv"
version = "1.0"
snapshot_date = "value"
verify_download = True

datahub_revert_resp: list[CommandResponse[Contracts_DatahubCommandResponse]] = pxc.datahub.revert(
    file_revert_path=file_revert_path,
    version=version,
    snapshot_date=snapshot_date,
    verify_download=verify_download,
    print_message=True
)
datahub_revert_final: Contracts_DatahubCommandResponse = SDKBase.get_response_data(datahub_revert_resp)

if datahub_revert_final is not None:
    print(f"DatahubCommandStatus: {datahub_revert_final.DatahubCommandStatus}")
    if datahub_revert_final.DatahubResourceResults is not None:
        for item in datahub_revert_final.DatahubResourceResults:
            print(f"RelativeFilePath: {item.RelativeFilePath}")
            print(f"RelativeToDirectoryOutputPath: {item.RelativeToDirectoryOutputPath}")
            print(f"LocalFilePath: {item.LocalFilePath}")
            print(f"FailureReason: {item.FailureReason}")
            # ... and 4 more properties
    else:
        print(f"No DatahubResourceResults returned")
else:
    print(f"revert failed: {datahub_revert_resp.Message}")
```

---

### datahub.search

Search for files in Datahub

**Signature:** `search(glob_patterns: Optional[list[str]], include_deleted_files: Optional[bool], include_tags: Optional[bool], tag_filter: Optional[str], tag_match_mode: Optional[str], print_message: bool)`

**Parameters:**
- `glob_patterns` (Optional[list[str]]) *(optional)*: glob_patterns parameter (default: `None`)
- `include_deleted_files` (Optional[bool]) *(optional)*: include_deleted_files parameter (default: `None`)
- `include_tags` (Optional[bool]) *(optional)*: include_tags parameter (default: `None`)
- `tag_filter` (Optional[str]) *(optional)*: tag_filter parameter (default: `None`)
- `tag_match_mode` (Optional[str]) *(optional)*: tag_match_mode parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubSearchResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `DatahubSearchResults`: Optional[list[Datahub_DatahubResourceInfo]]
  - `RelativePath`: Optional[str]
  - `CreatedAtUtc`: Optional[str]
  - `LastModifiedAtUtc`: Optional[str]
  - `IsDeleted`: Optional[bool]
  - `IsSymlink`: Optional[bool]
  - `IsVersioned`: Optional[bool]
  - `IsFromConnector`: Optional[bool]
  - `FileSize`: Optional[int]
  - `DeletedAtUtc`: Optional[str]
  - `LatestServerVersion`: Optional[int]
  - `Versions`: Optional[list[Datahub_DatahubVersionInfo]]
    - `CreatedAtUtc`: Optional[str]
    - `Version`: Optional[int]
    - `IsDeleted`: Optional[bool]
    - `EndedAtUtc`: Optional[str]
    - `FileSize`: Optional[int]
  - `TagNames`: Optional[list[str]]

**Example:**
```python
glob_patterns = ["folder/**/*.csv", "folder/**/*.parquet"]
include_deleted_files = True
include_tags = "value"
tag_filter = "value"
tag_match_mode = "value"

datahub_search_resp: list[CommandResponse[Contracts_DatahubSearchResponse]] = pxc.datahub.search(
    glob_patterns=glob_patterns,
    include_deleted_files=include_deleted_files,
    include_tags=include_tags,
    tag_filter=tag_filter,
    tag_match_mode=tag_match_mode,
    print_message=True
)
datahub_search_final: Contracts_DatahubSearchResponse = SDKBase.get_response_data(datahub_search_resp)

if datahub_search_final is not None:
    print(f"Success: {datahub_search_final.Success}")
    if datahub_search_final.DatahubSearchResults is not None:
        for item in datahub_search_final.DatahubSearchResults:
            print(f"RelativePath: {item.RelativePath}")
            print(f"CreatedAtUtc: {item.CreatedAtUtc}")
            print(f"LastModifiedAtUtc: {item.LastModifiedAtUtc}")
            print(f"IsDeleted: {item.IsDeleted}")
            # ... and 8 more properties
    else:
        print(f"No DatahubSearchResults returned")
else:
    print(f"search failed: {datahub_search_resp.Message}")
```

---

### datahub.un_delete

Restore previously deleted files

**Signature:** `un_delete(glob_patterns: list[str], print_message: bool)`

**Parameters:**
- `glob_patterns` (list[str]) *(required)*: glob_patterns parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubUnDeleteResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `QueuedForUndeletion`: Optional[list[str]]

**Example:**
```python
glob_patterns = ["folder/**/*.csv", "folder/**/*.parquet"]

datahub_un_delete_resp: list[CommandResponse[Contracts_DatahubUnDeleteResponse]] = pxc.datahub.un_delete(glob_patterns=glob_patterns, print_message=True)
datahub_un_delete_final: Contracts_DatahubUnDeleteResponse = SDKBase.get_response_data(datahub_un_delete_resp)

if datahub_un_delete_final is not None:
    print(f"Success: {datahub_un_delete_final.Success}")
    if datahub_un_delete_final.QueuedForUndeletion is not None:
        for item in datahub_un_delete_final.QueuedForUndeletion:
            print(f"Item: {item}")
    else:
        print(f"No QueuedForUndeletion returned")
else:
    print(f"un_delete failed: {datahub_un_delete_resp.Message}")
```

---

### datahub.upload

Upload files to Datahub

**Signature:** `upload(local_folder: Optional[str], remote_folder: Optional[str], glob_patterns: Optional[list[str]], is_versioned: Optional[bool], parallel_upload: Optional[bool], max_parallel: Optional[int], manifest_file_path: Optional[str], print_message: bool)`

**Parameters:**
- `local_folder` (Optional[str]) *(optional)*: local_folder parameter (default: `None`)
- `remote_folder` (Optional[str]) *(optional)*: remote_folder parameter (default: `None`)
- `glob_patterns` (Optional[list[str]]) *(optional)*: glob_patterns parameter (default: `None`)
- `is_versioned` (Optional[bool]) *(optional)*: is_versioned parameter (default: `None`)
- `parallel_upload` (Optional[bool]) *(optional)*: parallel_upload parameter (default: `None`)
- `max_parallel` (Optional[int]) *(optional)*: Maximum number of parallel download threads (default: `None`)
- `manifest_file_path` (Optional[str]) *(optional)*: Path to manifest file for download operations (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubCommandResponse`

**Response Structure:** 
- `DatahubCommandStatus`: Optional[Datahub_DatahubCommandStatus]
- `DatahubResourceResults`: Optional[list[Datahub_DatahubResourceResult]]
  - `RelativeFilePath`: Optional[str]
  - `RelativeToDirectoryOutputPath`: Optional[str]
  - `LocalFilePath`: Optional[str]
  - `FailureReason`: Optional[str]
  - `Success`: Optional[bool]
  - `Version`: Optional[int]
  - `IsFromConnector`: Optional[bool]
  - `SnapshotDateUtc`: Optional[str]

**Example:**
```python
local_folder = r"c:\local\folder"
remote_folder = "remote/folder"
glob_patterns = ["folder/**/*.csv", "folder/**/*.parquet"]
is_versioned = True
parallel_upload = "value"
max_parallel = 4
manifest_file_path = r"c:\path\to\manifest.csv"

datahub_upload_resp: list[CommandResponse[Contracts_DatahubCommandResponse]] = pxc.datahub.upload(
    local_folder=local_folder,
    remote_folder=remote_folder,
    glob_patterns=glob_patterns,
    is_versioned=is_versioned,
    parallel_upload=parallel_upload,
    max_parallel=max_parallel,
    manifest_file_path=manifest_file_path,
    print_message=True
)
datahub_upload_final: Contracts_DatahubCommandResponse = SDKBase.get_response_data(datahub_upload_resp)

if datahub_upload_final is not None:
    print(f"DatahubCommandStatus: {datahub_upload_final.DatahubCommandStatus}")
    if datahub_upload_final.DatahubResourceResults is not None:
        for item in datahub_upload_final.DatahubResourceResults:
            print(f"RelativeFilePath: {item.RelativeFilePath}")
            print(f"RelativeToDirectoryOutputPath: {item.RelativeToDirectoryOutputPath}")
            print(f"LocalFilePath: {item.LocalFilePath}")
            print(f"FailureReason: {item.FailureReason}")
            # ... and 4 more properties
    else:
        print(f"No DatahubResourceResults returned")
else:
    print(f"upload failed: {datahub_upload_resp.Message}")
```

---

### datahub.create_tag

Create a new tag in Datahub for organizing and categorizing resources

**Signature:** `create_tag(name: str, description: Optional[str], metadata: Optional[str], print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `description` (Optional[str]) *(optional)*: Description text used for filtering or metadata (default: `None`)
- `metadata` (Optional[str]) *(optional)*: metadata parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Tag`: Optional[Datahub_DatahubTagInfo]
  - `TagId`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `IsSystemGenerated`: Optional[bool]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `Metadata`: Optional[dict[(str, str)]]

**Example:**
```python
name = "My Name"
description = "Description"
metadata = "value"

datahub_create_tag_resp: list[CommandResponse[Contracts_DatahubTagResponse]] = pxc.datahub.create_tag(name=name, description=description, metadata=metadata, print_message=True)
datahub_create_tag_final: Contracts_DatahubTagResponse = SDKBase.get_response_data(datahub_create_tag_resp)

if datahub_create_tag_final is not None:
    print(f"Success: {datahub_create_tag_final.Success}")
    print(f"Tag: {datahub_create_tag_final.Tag}")
else:
    print(f"create_tag failed: {datahub_create_tag_resp.Message}")
```

---

### datahub.delete_tag

Delete a tag from Datahub

**Signature:** `delete_tag(name: str, hard_delete: Optional[bool], confirm: Optional[bool], print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `hard_delete` (Optional[bool]) *(optional)*: hard_delete parameter (default: `None`)
- `confirm` (Optional[bool]) *(optional)*: Skip confirmation prompt for destructive operations (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagDeleteResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
name = "My Name"
hard_delete = "value"
confirm = True

datahub_delete_tag_resp: list[CommandResponse[Contracts_DatahubTagDeleteResponse]] = pxc.datahub.delete_tag(name=name, hard_delete=hard_delete, confirm=confirm, print_message=True)
datahub_delete_tag_final: Contracts_DatahubTagDeleteResponse = SDKBase.get_response_data(datahub_delete_tag_resp)

if datahub_delete_tag_final is not None:
    print(f"Success: {datahub_delete_tag_final.Success}")
else:
    print(f"delete_tag failed: {datahub_delete_tag_resp.Message}")
```

---

### datahub.list_tags

List all tags available in Datahub

**Signature:** `list_tags(active_only: Optional[bool], include_system: Optional[bool], print_message: bool)`

**Parameters:**
- `active_only` (Optional[bool]) *(optional)*: Filter to show only active connectors (optional flag) (default: `None`)
- `include_system` (Optional[bool]) *(optional)*: include_system parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagListResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Tags`: Optional[list[Datahub_DatahubTagInfo]]
  - `TagId`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `IsSystemGenerated`: Optional[bool]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `Metadata`: Optional[dict[(str, str)]]

**Example:**
```python
active_only = "value"
include_system = "value"

datahub_list_tags_resp: list[CommandResponse[Contracts_DatahubTagListResponse]] = pxc.datahub.list_tags(active_only=active_only, include_system=include_system, print_message=True)
datahub_list_tags_final: Contracts_DatahubTagListResponse = SDKBase.get_response_data(datahub_list_tags_resp)

if datahub_list_tags_final is not None:
    print(f"Success: {datahub_list_tags_final.Success}")
    if datahub_list_tags_final.Tags is not None:
        for item in datahub_list_tags_final.Tags:
            print(f"TagId: {item.TagId}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"IsSystemGenerated: {item.IsSystemGenerated}")
            # ... and 4 more properties
    else:
        print(f"No Tags returned")
else:
    print(f"list_tags failed: {datahub_list_tags_resp.Message}")
```

---

### datahub.modify_tag

Attach or remove tags from a Datahub resource

**Signature:** `modify_tag(relative_path: str, attach_tags: Optional[str], remove_tags: Optional[str], print_message: bool)`

**Parameters:**
- `relative_path` (str) *(required)*: relative_path parameter
- `attach_tags` (Optional[str]) *(optional)*: attach_tags parameter (default: `None`)
- `remove_tags` (Optional[str]) *(optional)*: remove_tags parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagModifyResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `RelativePath`: Optional[str]
- `AssignedTags`: Optional[list[Datahub_DatahubTagInfo]]
  - `TagId`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `IsSystemGenerated`: Optional[bool]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `Metadata`: Optional[dict[(str, str)]]

**Example:**
```python
relative_path = "relative path"
attach_tags = "value"
remove_tags = "value"

datahub_modify_tag_resp: list[CommandResponse[Contracts_DatahubTagModifyResponse]] = pxc.datahub.modify_tag(relative_path=relative_path, attach_tags=attach_tags, remove_tags=remove_tags, print_message=True)
datahub_modify_tag_final: Contracts_DatahubTagModifyResponse = SDKBase.get_response_data(datahub_modify_tag_resp)

if datahub_modify_tag_final is not None:
    print(f"Success: {datahub_modify_tag_final.Success}")
    print(f"RelativePath: {datahub_modify_tag_final.RelativePath}")
    if datahub_modify_tag_final.AssignedTags is not None:
        for item in datahub_modify_tag_final.AssignedTags:
            print(f"TagId: {item.TagId}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"IsSystemGenerated: {item.IsSystemGenerated}")
            # ... and 4 more properties
    else:
        print(f"No AssignedTags returned")
else:
    print(f"modify_tag failed: {datahub_modify_tag_resp.Message}")
```

---

### datahub.search_tags

Search for tags by name filter

**Signature:** `search_tags(filter: str, print_message: bool)`

**Parameters:**
- `filter` (str) *(required)*: filter parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagListResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Tags`: Optional[list[Datahub_DatahubTagInfo]]
  - `TagId`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `IsSystemGenerated`: Optional[bool]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `Metadata`: Optional[dict[(str, str)]]

**Example:**
```python
filter = "filter"

datahub_search_tags_resp: list[CommandResponse[Contracts_DatahubTagListResponse]] = pxc.datahub.search_tags(filter=filter, print_message=True)
datahub_search_tags_final: Contracts_DatahubTagListResponse = SDKBase.get_response_data(datahub_search_tags_resp)

if datahub_search_tags_final is not None:
    print(f"Success: {datahub_search_tags_final.Success}")
    if datahub_search_tags_final.Tags is not None:
        for item in datahub_search_tags_final.Tags:
            print(f"TagId: {item.TagId}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"IsSystemGenerated: {item.IsSystemGenerated}")
            # ... and 4 more properties
    else:
        print(f"No Tags returned")
else:
    print(f"search_tags failed: {datahub_search_tags_resp.Message}")
```

---

### datahub.update_tag

Update an existing tag's properties

**Signature:** `update_tag(name: str, new_name: str, print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `new_name` (str) *(required)*: new_name parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubTagResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Tag`: Optional[Datahub_DatahubTagInfo]
  - `TagId`: Optional[str]
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `IsSystemGenerated`: Optional[bool]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `Metadata`: Optional[dict[(str, str)]]

**Example:**
```python
name = "My Name"
new_name = "new name"

datahub_update_tag_resp: list[CommandResponse[Contracts_DatahubTagResponse]] = pxc.datahub.update_tag(name=name, new_name=new_name, print_message=True)
datahub_update_tag_final: Contracts_DatahubTagResponse = SDKBase.get_response_data(datahub_update_tag_resp)

if datahub_update_tag_final is not None:
    print(f"Success: {datahub_update_tag_final.Success}")
    print(f"Tag: {datahub_update_tag_final.Tag}")
else:
    print(f"update_tag failed: {datahub_update_tag_resp.Message}")
```

---

### datahub.create_local_symlink

Create a local symbolic link to Datahub files

**Signature:** `create_local_symlink(display_name: str, target_remote_path: str, symlink_path: str, symlink_type: Datahub_DatahubSymlinkType, print_message: bool)`

**Parameters:**
- `display_name` (str) *(required)*: display_name parameter
- `target_remote_path` (str) *(required)*: target_remote_path parameter
- `symlink_path` (str) *(required)*: symlink_path parameter
- `symlink_type` (Datahub_DatahubSymlinkType) *(required)*: symlink_type parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubSymlinkResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
display_name = "My Display Name"
target_remote_path = "remote/target/path"
symlink_path = r"path/folder"
symlink_type = "Local"

datahub_create_local_symlink_resp: list[CommandResponse[Contracts_DatahubSymlinkResponse]] = pxc.datahub.create_local_symlink(
    display_name=display_name,
    target_remote_path=target_remote_path,
    symlink_path=symlink_path,
    symlink_type=symlink_type,
    print_message=True
)
datahub_create_local_symlink_final: Contracts_DatahubSymlinkResponse = SDKBase.get_response_data(datahub_create_local_symlink_resp)

if datahub_create_local_symlink_final is not None:
    print(f"Success: {datahub_create_local_symlink_final.Success}")
else:
    print(f"create_local_symlink failed: {datahub_create_local_symlink_resp.Message}")
```

---

### datahub.create_symlink

Create a symbolic link to files in another tenant

**Signature:** `create_symlink(display_name: str, target_tenant_id: str, target_remote_path: str, symlink_path: str, symlink_type: Datahub_DatahubSymlinkType, print_message: bool)`

**Parameters:**
- `display_name` (str) *(required)*: display_name parameter
- `target_tenant_id` (str) *(required)*: target_tenant_id parameter
- `target_remote_path` (str) *(required)*: target_remote_path parameter
- `symlink_path` (str) *(required)*: symlink_path parameter
- `symlink_type` (Datahub_DatahubSymlinkType) *(required)*: symlink_type parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubSymlinkResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
display_name = "My Display Name"
target_tenant_id = "550e8400-e29b-41d4-a716-446655440000"
target_remote_path = "remote/target/path"
symlink_path = r"path/folder"
symlink_type = "Local"

datahub_create_symlink_resp: list[CommandResponse[Contracts_DatahubSymlinkResponse]] = pxc.datahub.create_symlink(
    display_name=display_name,
    target_tenant_id=target_tenant_id,
    target_remote_path=target_remote_path,
    symlink_path=symlink_path,
    symlink_type=symlink_type,
    print_message=True
)
datahub_create_symlink_final: Contracts_DatahubSymlinkResponse = SDKBase.get_response_data(datahub_create_symlink_resp)

if datahub_create_symlink_final is not None:
    print(f"Success: {datahub_create_symlink_final.Success}")
else:
    print(f"create_symlink failed: {datahub_create_symlink_resp.Message}")
```

---

### datahub.delete_symlink

Delete a symbolic link

**Signature:** `delete_symlink(symlink_path: str, print_message: bool)`

**Parameters:**
- `symlink_path` (str) *(required)*: symlink_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeleteSymlinkResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
symlink_path = r"path/folder"

datahub_delete_symlink_resp: list[CommandResponse[Contracts_DatahubDeleteSymlinkResponse]] = pxc.datahub.delete_symlink(symlink_path=symlink_path, print_message=True)
datahub_delete_symlink_final: Contracts_DatahubDeleteSymlinkResponse = SDKBase.get_response_data(datahub_delete_symlink_resp)

if datahub_delete_symlink_final is not None:
    print(f"Success: {datahub_delete_symlink_final.Success}")
else:
    print(f"delete_symlink failed: {datahub_delete_symlink_resp.Message}")
```

---

### datahub.list_symlinks

List all symbolic links

**Signature:** `list_symlinks(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubListSymlinksResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Symlinks`: Optional[list[Datahub_DatahubSymlinkInfo]]
  - `DisplayName`: Optional[str]
  - `SymlinkId`: Optional[str]
  - `Type`: Optional[Datahub_DatahubSymlinkType]
  - `TargetTenantId`: Optional[str]
  - `RemotePath`: Optional[str]
  - `SymlinkPath`: Optional[str]

**Example:**
```python
datahub_list_symlinks_resp: list[CommandResponse[Contracts_DatahubListSymlinksResponse]] = pxc.datahub.list_symlinks(print_message=True)
datahub_list_symlinks_final: Contracts_DatahubListSymlinksResponse = SDKBase.get_response_data(datahub_list_symlinks_resp)

if datahub_list_symlinks_final is not None:
    print(f"Success: {datahub_list_symlinks_final.Success}")
    if datahub_list_symlinks_final.Symlinks is not None:
        for item in datahub_list_symlinks_final.Symlinks:
            print(f"DisplayName: {item.DisplayName}")
            print(f"SymlinkId: {item.SymlinkId}")
            print(f"Type: {item.Type}")
            print(f"TargetTenantId: {item.TargetTenantId}")
            # ... and 2 more properties
    else:
        print(f"No Symlinks returned")
else:
    print(f"list_symlinks failed: {datahub_list_symlinks_resp.Message}")
```

---

### datahub.create_share

Create a new file share

**Signature:** `create_share(display_name: str, remote_path: str, permissions: Optional[list[str]], permissions_file_path: Optional[str], print_message: bool)`

**Parameters:**
- `display_name` (str) *(required)*: display_name parameter
- `remote_path` (str) *(required)*: remote_path parameter
- `permissions` (Optional[list[str]]) *(optional)*: permissions parameter (default: `None`)
- `permissions_file_path` (Optional[str]) *(optional)*: permissions_file_path parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubShareResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
display_name = "My Display Name"
remote_path = "remote/path/*.*"
permissions = ["read", "write"]
permissions_file_path = r"c:\path\to\permissions.txt"

datahub_create_share_resp: list[CommandResponse[Contracts_DatahubShareResponse]] = pxc.datahub.create_share(
    display_name=display_name,
    remote_path=remote_path,
    permissions=permissions,
    permissions_file_path=permissions_file_path,
    print_message=True
)
datahub_create_share_final: Contracts_DatahubShareResponse = SDKBase.get_response_data(datahub_create_share_resp)

if datahub_create_share_final is not None:
    print(f"Success: {datahub_create_share_final.Success}")
else:
    print(f"create_share failed: {datahub_create_share_resp.Message}")
```

---

### datahub.delete_share

Delete a file share

**Signature:** `delete_share(share_id: str, print_message: bool)`

**Parameters:**
- `share_id` (str) *(required)*: share_id parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeleteShareResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
share_id = "share id"

datahub_delete_share_resp: list[CommandResponse[Contracts_DatahubDeleteShareResponse]] = pxc.datahub.delete_share(share_id=share_id, print_message=True)
datahub_delete_share_final: Contracts_DatahubDeleteShareResponse = SDKBase.get_response_data(datahub_delete_share_resp)

if datahub_delete_share_final is not None:
    print(f"Success: {datahub_delete_share_final.Success}")
else:
    print(f"delete_share failed: {datahub_delete_share_resp.Message}")
```

---

### datahub.list_shares

List all file shares

**Signature:** `list_shares(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubListSharesResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Shares`: Optional[list[Datahub_DatahubShareInfo]]
  - `ShareId`: Optional[str]
  - `Name`: Optional[str]
  - `RelativePath`: Optional[str]
  - `Permissions`: Optional[list[Datahub_DatahubSharePermissionInfo]]
    - `PermissionId`: Optional[str]
    - `AllowedScope`: Optional[str]
    - `TenantId`: Optional[str]
    - `UserId`: Optional[str]

**Example:**
```python
datahub_list_shares_resp: list[CommandResponse[Contracts_DatahubListSharesResponse]] = pxc.datahub.list_shares(print_message=True)
datahub_list_shares_final: Contracts_DatahubListSharesResponse = SDKBase.get_response_data(datahub_list_shares_resp)

if datahub_list_shares_final is not None:
    print(f"Success: {datahub_list_shares_final.Success}")
    if datahub_list_shares_final.Shares is not None:
        for item in datahub_list_shares_final.Shares:
            print(f"ShareId: {item.ShareId}")
            print(f"Name: {item.Name}")
            print(f"RelativePath: {item.RelativePath}")
            print(f"Permissions: {item.Permissions}")
    else:
        print(f"No Shares returned")
else:
    print(f"list_shares failed: {datahub_list_shares_resp.Message}")
```

---

### datahub.add_or_update_permission

Add or update file permissions

**Signature:** `add_or_update_permission(remote_path: str, type: Datahub_PermissionType, user_or_role_id: str, read: bool, write: bool, inherit_parent_permissions: Optional[bool], print_message: bool)`

**Parameters:**
- `remote_path` (str) *(required)*: remote_path parameter
- `type` (Datahub_PermissionType) *(required)*: type parameter
- `user_or_role_id` (str) *(required)*: user_or_role_id parameter
- `read` (bool) *(required)*: read parameter
- `write` (bool) *(required)*: write parameter
- `inherit_parent_permissions` (Optional[bool]) *(optional)*: inherit_parent_permissions parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubAddOrUpdatePermissionResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
remote_path = "remote/path/*.*"
type = "Standard"
user_or_role_id = "user or role id"
read = True
write = True
inherit_parent_permissions = True

datahub_add_or_update_permission_resp: list[CommandResponse[Contracts_DatahubAddOrUpdatePermissionResponse]] = pxc.datahub.add_or_update_permission(
    remote_path=remote_path,
    type=type,
    user_or_role_id=user_or_role_id,
    read=read,
    write=write,
    inherit_parent_permissions=inherit_parent_permissions,
    print_message=True
)
datahub_add_or_update_permission_final: Contracts_DatahubAddOrUpdatePermissionResponse = SDKBase.get_response_data(datahub_add_or_update_permission_resp)

if datahub_add_or_update_permission_final is not None:
    print(f"success: {datahub_add_or_update_permission_final.success}")
else:
    print(f"add_or_update_permission failed: {datahub_add_or_update_permission_resp.Message}")
```

---

### datahub.delete_permission

Delete file permissions

**Signature:** `delete_permission(remote_path: str, roles: list[str], user_ids: list[str], print_message: bool)`

**Parameters:**
- `remote_path` (str) *(required)*: remote_path parameter
- `roles` (list[str]) *(required)*: roles parameter
- `user_ids` (list[str]) *(required)*: user_ids parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeletePermissionResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
remote_path = "remote/path/*.*"
roles = ["admin", "user"]
user_ids = ["user1", "user2"]

datahub_delete_permission_resp: list[CommandResponse[Contracts_DatahubDeletePermissionResponse]] = pxc.datahub.delete_permission(remote_path=remote_path, roles=roles, user_ids=user_ids, print_message=True)
datahub_delete_permission_final: Contracts_DatahubDeletePermissionResponse = SDKBase.get_response_data(datahub_delete_permission_resp)

if datahub_delete_permission_final is not None:
    print(f"success: {datahub_delete_permission_final.success}")
else:
    print(f"delete_permission failed: {datahub_delete_permission_resp.Message}")
```

---

### datahub.delete_permission_rule

Delete a permission rule

**Signature:** `delete_permission_rule(remote_path: str, print_message: bool)`

**Parameters:**
- `remote_path` (str) *(required)*: remote_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeleteRuleResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
remote_path = "remote/path/*.*"

datahub_delete_permission_rule_resp: list[CommandResponse[Contracts_DatahubDeleteRuleResponse]] = pxc.datahub.delete_permission_rule(remote_path=remote_path, print_message=True)
datahub_delete_permission_rule_final: Contracts_DatahubDeleteRuleResponse = SDKBase.get_response_data(datahub_delete_permission_rule_resp)

if datahub_delete_permission_rule_final is not None:
    print(f"success: {datahub_delete_permission_rule_final.success}")
else:
    print(f"delete_permission_rule failed: {datahub_delete_permission_rule_resp.Message}")
```

---

### datahub.list_permissions_by_path

List permissions for a specific file or folder path

**Signature:** `list_permissions_by_path(remote_path: str, include_inherited: Optional[bool], print_message: bool)`

**Parameters:**
- `remote_path` (str) *(required)*: remote_path parameter
- `include_inherited` (Optional[bool]) *(optional)*: include_inherited parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubListPermissionsByPathResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Data`: Optional[Datahub_DatahubListPermissionsByPathInfo]
  - `RelativePath`: Optional[str]
  - `OwnerId`: Optional[str]
  - `InheritParent`: Optional[bool]
  - `IsInherited`: Optional[bool]
  - `UserPermissions`: Optional[list[Datahub_DatahubUserPermissionInfo]]
    - `UserId`: Optional[str]
    - `Read`: Optional[bool]
    - `Write`: Optional[bool]
  - `RolePermissions`: Optional[list[Datahub_DatahubRolePermissionInfo]]
    - `RoleName`: Optional[str]
    - `Read`: Optional[bool]
    - `Write`: Optional[bool]

**Example:**
```python
remote_path = "remote/path/*.*"
include_inherited = "value"

datahub_list_permissions_by_path_resp: list[CommandResponse[Contracts_DatahubListPermissionsByPathResponse]] = pxc.datahub.list_permissions_by_path(remote_path=remote_path, include_inherited=include_inherited, print_message=True)
datahub_list_permissions_by_path_final: Contracts_DatahubListPermissionsByPathResponse = SDKBase.get_response_data(datahub_list_permissions_by_path_resp)

if datahub_list_permissions_by_path_final is not None:
    print(f"Success: {datahub_list_permissions_by_path_final.Success}")
    print(f"Data: {datahub_list_permissions_by_path_final.Data}")
else:
    print(f"list_permissions_by_path failed: {datahub_list_permissions_by_path_resp.Message}")
```

---

### datahub.list_permissions

List all file permissions

**Signature:** `list_permissions(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubAclListResponse`

**Response Structure:** 
- `success`: Optional[bool]
- `acls`: Optional[list[Datahub_DatahubAclInfo]]
  - `Id`: Optional[str]
  - `InheritParent`: Optional[bool]
  - `RelativePath`: Optional[str]
  - `Permissions`: Optional[Datahub_UserRolePermissionInfo]
    - `Roles`: Optional[list[Datahub_DatahubAclPermissionInfo]]
      - `Id`: Optional[str]
      - `Read`: Optional[bool]
      - `Write`: Optional[bool]

**Example:**
```python
datahub_list_permissions_resp: list[CommandResponse[Contracts_DatahubAclListResponse]] = pxc.datahub.list_permissions(print_message=True)
datahub_list_permissions_final: Contracts_DatahubAclListResponse = SDKBase.get_response_data(datahub_list_permissions_resp)

if datahub_list_permissions_final is not None:
    print(f"success: {datahub_list_permissions_final.success}")
    if datahub_list_permissions_final.acls is not None:
        for item in datahub_list_permissions_final.acls:
            print(f"Id: {item.Id}")
            print(f"InheritParent: {item.InheritParent}")
            print(f"RelativePath: {item.RelativePath}")
            print(f"Permissions: {item.Permissions}")
    else:
        print(f"No acls returned")
else:
    print(f"list_permissions failed: {datahub_list_permissions_resp.Message}")
```

---

### datahub.check_connector_feature_status

Check if the connector feature is enabled for the current tenant

**Signature:** `check_connector_feature_status(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubConnectorFeatureStatusResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `IsEnabled`: Optional[bool]
- `Status`: Optional[str]
- `CheckedAtUtc`: Optional[str]

**Example:**
```python
datahub_check_connector_feature_status_resp: list[CommandResponse[Contracts_DatahubConnectorFeatureStatusResponse]] = pxc.datahub.check_connector_feature_status(print_message=True)
datahub_check_connector_feature_status_final: Contracts_DatahubConnectorFeatureStatusResponse = SDKBase.get_response_data(datahub_check_connector_feature_status_resp)

if datahub_check_connector_feature_status_final is not None:
    print(f"Success: {datahub_check_connector_feature_status_final.Success}")
    print(f"IsEnabled: {datahub_check_connector_feature_status_final.IsEnabled}")
    print(f"Status: {datahub_check_connector_feature_status_final.Status}")
    print(f"CheckedAtUtc: {datahub_check_connector_feature_status_final.CheckedAtUtc}")
else:
    print(f"check_connector_feature_status failed: {datahub_check_connector_feature_status_resp.Message}")
```

---

### datahub.connector_feature

Activate or deactivate the connector feature for the tenant

**Signature:** `connector_feature(activate: bool, print_message: bool)`

**Parameters:**
- `activate` (bool) *(required)*: activate parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubConnectorFeatureResponse`

**Response Structure:** 
- `success`: Optional[bool]
- `isActivated`: Optional[bool]

**Example:**
```python
activate = True

datahub_connector_feature_resp: list[CommandResponse[Contracts_DatahubConnectorFeatureResponse]] = pxc.datahub.connector_feature(activate=activate, print_message=True)
datahub_connector_feature_final: Contracts_DatahubConnectorFeatureResponse = SDKBase.get_response_data(datahub_connector_feature_resp)

if datahub_connector_feature_final is not None:
    print(f"success: {datahub_connector_feature_final.success}")
    print(f"isActivated: {datahub_connector_feature_final.isActivated}")
else:
    print(f"connector_feature failed: {datahub_connector_feature_resp.Message}")
```

---

### datahub.create_connector

Create a new connector (external storage) in Datahub

**Signature:** `create_connector(name: str, connector_type: str, auth_type: str, service_uri: Optional[str], connection_string: Optional[str], account_name: Optional[str], account_key: Optional[str], sas_token: Optional[str], container_name: Optional[str], s3_access_key: Optional[str], s3_secret_key: Optional[str], region: Optional[str], bucket_name: Optional[str], session_token: Optional[str], role_arn: Optional[str], session_name: Optional[str], service_endpoint_url: Optional[str], repository: Optional[str], branch: Optional[str], personal_access_token: Optional[str], owner: Optional[str], base_url: Optional[str], organization_url: Optional[str], project: Optional[str], print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `connector_type` (str) *(required)*: Type of connector (AzureBlob, AmazonS3, GitHub, AzureRepos)
- `auth_type` (str) *(required)*: Authentication type (ConnectionString, Token, SharedKey, AccountCreds, AssumeRole, Pat).
- `service_uri` (Optional[str]) *(optional)*: Service URI for Azure Blob storage (default: `None`)
- `connection_string` (Optional[str]) *(optional)*: Connection string for Azure Blob storage (default: `None`)
- `account_name` (Optional[str]) *(optional)*: Account name for Azure storage service (default: `None`)
- `account_key` (Optional[str]) *(optional)*: Account key for Azure storage service (default: `None`)
- `sas_token` (Optional[str]) *(optional)*: SAS token for Azure storage service (default: `None`)
- `container_name` (Optional[str]) *(optional)*: Container name in Azure Blob storage (default: `None`)
- `s3_access_key` (Optional[str]) *(optional)*: AWS Access Key ID for S3 authentication (default: `None`)
- `s3_secret_key` (Optional[str]) *(optional)*: AWS Secret Access Key for S3 authentication (default: `None`)
- `region` (Optional[str]) *(optional)*: AWS region for S3 bucket (e.g., us-east-1, eu-west-1) (default: `None`)
- `bucket_name` (Optional[str]) *(optional)*: S3 bucket name (default: `None`)
- `session_token` (Optional[str]) *(optional)*: AWS session token for temporary credentials (default: `None`)
- `role_arn` (Optional[str]) *(optional)*: ARN of the IAM role to assume for cross-account access (default: `None`)
- `session_name` (Optional[str]) *(optional)*: Session name for AssumeRole operations (default: `None`)
- `service_endpoint_url` (Optional[str]) *(optional)*: service_endpoint_url parameter (default: `None`)
- `repository` (Optional[str]) *(optional)*: Repository name to connect to (required for GitHub and AzureRepos connectors) (default: `None`)
- `branch` (Optional[str]) *(optional)*: Branch name to sync from (e.g., 'main', 'master'). Required for GitHub and AzureRepos connectors (default: `None`)
- `personal_access_token` (Optional[str]) *(optional)*: personal_access_token parameter (default: `None`)
- `owner` (Optional[str]) *(optional)*: GitHub owner (organization name or username). Required for GitHub connectors (default: `None`)
- `base_url` (Optional[str]) *(optional)*: Custom base URL for GitHub Enterprise Server. Optional, leave empty for github.com (default: `None`)
- `organization_url` (Optional[str]) *(optional)*: Azure DevOps organization URL. Required for AzureRepos connectors (e.g., https://dev.azure.com/my-org) (default: `None`)
- `project` (Optional[str]) *(optional)*: Azure DevOps project name containing the repository. Required for AzureRepos connectors (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubAddConnectorResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
name = "My Name"
connector_type = "connector type"
auth_type = "auth type"
service_uri = "value"
connection_string = "value"
account_name = "value"
account_key = "value"
sas_token = "value"
container_name = "value"
s3_access_key = "value"
s3_secret_key = "value"
region = "value"
bucket_name = "value"
session_token = "value"
role_arn = "value"
session_name = "value"
service_endpoint_url = "value"
repository = "my-repository"
branch = "main"
personal_access_token = "value"
owner = "my-org"
base_url = "https://github.mycompany.com"
organization_url = "https://dev.azure.com/my-organization"
project = "MyProject"

datahub_create_connector_resp: list[CommandResponse[Contracts_DatahubAddConnectorResponse]] = pxc.datahub.create_connector(
    name=name,
    connector_type=connector_type,
    auth_type=auth_type,
    service_uri=service_uri,
    connection_string=connection_string,
    account_name=account_name,
    account_key=account_key,
    sas_token=sas_token,
    container_name=container_name,
    s3_access_key=s3_access_key,
    s3_secret_key=s3_secret_key,
    region=region,
    bucket_name=bucket_name,
    session_token=session_token,
    role_arn=role_arn,
    session_name=session_name,
    service_endpoint_url=service_endpoint_url,
    repository=repository,
    branch=branch,
    personal_access_token=personal_access_token,
    owner=owner,
    base_url=base_url,
    organization_url=organization_url,
    project=project,
    print_message=True
)
datahub_create_connector_final: Contracts_DatahubAddConnectorResponse = SDKBase.get_response_data(datahub_create_connector_resp)

if datahub_create_connector_final is not None:
    print(f"success: {datahub_create_connector_final.success}")
else:
    print(f"create_connector failed: {datahub_create_connector_resp.Message}")
```

---

### datahub.delete_connector

Delete a connector from Datahub

**Signature:** `delete_connector(name: str, print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubDeleteConnectorResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
name = "My Name"

datahub_delete_connector_resp: list[CommandResponse[Contracts_DatahubDeleteConnectorResponse]] = pxc.datahub.delete_connector(name=name, print_message=True)
datahub_delete_connector_final: Contracts_DatahubDeleteConnectorResponse = SDKBase.get_response_data(datahub_delete_connector_resp)

if datahub_delete_connector_final is not None:
    print(f"success: {datahub_delete_connector_final.success}")
else:
    print(f"delete_connector failed: {datahub_delete_connector_resp.Message}")
```

---

### datahub.list_connectors

List all connectors in Datahub with optional filtering for active connectors only

**Signature:** `list_connectors(active_only: Optional[bool], print_message: bool)`

**Parameters:**
- `active_only` (Optional[bool]) *(optional)*: Filter to show only active connectors (optional flag) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubListConnectorsResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Connectors`: Optional[list[Datahub_DatahubConnectorSummary]]
  - `ConnectorId`: Optional[str]
  - `Name`: Optional[str]
  - `ConnectorType`: Optional[Datahub_DatahubConnectorType]
  - `AuthType`: Optional[Datahub_DatahubConnectorAuthenticationType]
  - `ContainerName`: Optional[str]
  - `RelativePath`: Optional[str]
  - `IsActive`: Optional[bool]
  - `CreatedAtUtc`: Optional[str]
  - `LastModifiedAtUtc`: Optional[str]

**Example:**
```python
active_only = "value"

datahub_list_connectors_resp: list[CommandResponse[Contracts_DatahubListConnectorsResponse]] = pxc.datahub.list_connectors(active_only=active_only, print_message=True)
datahub_list_connectors_final: Contracts_DatahubListConnectorsResponse = SDKBase.get_response_data(datahub_list_connectors_resp)

if datahub_list_connectors_final is not None:
    print(f"Success: {datahub_list_connectors_final.Success}")
    if datahub_list_connectors_final.Connectors is not None:
        for item in datahub_list_connectors_final.Connectors:
            print(f"ConnectorId: {item.ConnectorId}")
            print(f"Name: {item.Name}")
            print(f"ConnectorType: {item.ConnectorType}")
            print(f"AuthType: {item.AuthType}")
            # ... and 5 more properties
    else:
        print(f"No Connectors returned")
else:
    print(f"list_connectors failed: {datahub_list_connectors_resp.Message}")
```

---

### datahub.refresh_connector

Refresh an existing connector in Datahub to re-validate authentication

**Signature:** `refresh_connector(connector_id: Optional[str], connector_name: Optional[str], connector_path: Optional[str], print_message: bool)`

**Parameters:**
- `connector_id` (Optional[str]) *(optional)*: connector_id parameter (default: `None`)
- `connector_name` (Optional[str]) *(optional)*: connector_name parameter (default: `None`)
- `connector_path` (Optional[str]) *(optional)*: connector_path parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubRefreshConnectorResponse`

**Response Structure:** 
- `Success`: Optional[bool]

**Example:**
```python
connector_id = "550e8400-e29b-41d4-a716-446655440000"
connector_name = "value"
connector_path = "value"

datahub_refresh_connector_resp: list[CommandResponse[Contracts_DatahubRefreshConnectorResponse]] = pxc.datahub.refresh_connector(connector_id=connector_id, connector_name=connector_name, connector_path=connector_path, print_message=True)
datahub_refresh_connector_final: Contracts_DatahubRefreshConnectorResponse = SDKBase.get_response_data(datahub_refresh_connector_resp)

if datahub_refresh_connector_final is not None:
    print(f"Success: {datahub_refresh_connector_final.Success}")
else:
    print(f"refresh_connector failed: {datahub_refresh_connector_resp.Message}")
```

---

### datahub.update_connector

Update an existing connector in Datahub

**Signature:** `update_connector(name: str, connector_type: Optional[str], auth_type: Optional[str], service_uri: Optional[str], connection_string: Optional[str], account_name: Optional[str], account_key: Optional[str], sas_token: Optional[str], container_name: Optional[str], s3_access_key: Optional[str], s3_secret_key: Optional[str], region: Optional[str], bucket_name: Optional[str], session_token: Optional[str], role_arn: Optional[str], session_name: Optional[str], service_endpoint_url: Optional[str], repository: Optional[str], branch: Optional[str], personal_access_token: Optional[str], owner: Optional[str], base_url: Optional[str], organization_url: Optional[str], project: Optional[str], print_message: bool)`

**Parameters:**
- `name` (str) *(required)*: Name or identifier for the resource
- `connector_type` (Optional[str]) *(optional)*: Type of connector (AzureBlob, AmazonS3, GitHub, AzureRepos) (default: `None`)
- `auth_type` (Optional[str]) *(optional)*: Authentication type (ConnectionString, Token, SharedKey, AccountCreds, AssumeRole, Pat). (default: `None`)
- `service_uri` (Optional[str]) *(optional)*: Service URI for Azure Blob storage (default: `None`)
- `connection_string` (Optional[str]) *(optional)*: Connection string for Azure Blob storage (default: `None`)
- `account_name` (Optional[str]) *(optional)*: Account name for Azure storage service (default: `None`)
- `account_key` (Optional[str]) *(optional)*: Account key for Azure storage service (default: `None`)
- `sas_token` (Optional[str]) *(optional)*: SAS token for Azure storage service (default: `None`)
- `container_name` (Optional[str]) *(optional)*: Container name in Azure Blob storage (default: `None`)
- `s3_access_key` (Optional[str]) *(optional)*: AWS Access Key ID for S3 authentication (default: `None`)
- `s3_secret_key` (Optional[str]) *(optional)*: AWS Secret Access Key for S3 authentication (default: `None`)
- `region` (Optional[str]) *(optional)*: AWS region for S3 bucket (e.g., us-east-1, eu-west-1) (default: `None`)
- `bucket_name` (Optional[str]) *(optional)*: S3 bucket name (default: `None`)
- `session_token` (Optional[str]) *(optional)*: AWS session token for temporary credentials (default: `None`)
- `role_arn` (Optional[str]) *(optional)*: ARN of the IAM role to assume for cross-account access (default: `None`)
- `session_name` (Optional[str]) *(optional)*: Session name for AssumeRole operations (default: `None`)
- `service_endpoint_url` (Optional[str]) *(optional)*: service_endpoint_url parameter (default: `None`)
- `repository` (Optional[str]) *(optional)*: Repository name to connect to (required for GitHub and AzureRepos connectors) (default: `None`)
- `branch` (Optional[str]) *(optional)*: Branch name to sync from (e.g., 'main', 'master'). Required for GitHub and AzureRepos connectors (default: `None`)
- `personal_access_token` (Optional[str]) *(optional)*: personal_access_token parameter (default: `None`)
- `owner` (Optional[str]) *(optional)*: GitHub owner (organization name or username). Required for GitHub connectors (default: `None`)
- `base_url` (Optional[str]) *(optional)*: Custom base URL for GitHub Enterprise Server. Optional, leave empty for github.com (default: `None`)
- `organization_url` (Optional[str]) *(optional)*: Azure DevOps organization URL. Required for AzureRepos connectors (e.g., https://dev.azure.com/my-org) (default: `None`)
- `project` (Optional[str]) *(optional)*: Azure DevOps project name containing the repository. Required for AzureRepos connectors (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DatahubUpdateConnectorResponse`

**Response Structure:** 
- `success`: Optional[bool]

**Example:**
```python
name = "My Name"
connector_type = "value"
auth_type = "value"
service_uri = "value"
connection_string = "value"
account_name = "value"
account_key = "value"
sas_token = "value"
container_name = "value"
s3_access_key = "value"
s3_secret_key = "value"
region = "value"
bucket_name = "value"
session_token = "value"
role_arn = "value"
session_name = "value"
service_endpoint_url = "value"
repository = "my-repository"
branch = "main"
personal_access_token = "value"
owner = "my-org"
base_url = "https://github.mycompany.com"
organization_url = "https://dev.azure.com/my-organization"
project = "MyProject"

datahub_update_connector_resp: list[CommandResponse[Contracts_DatahubUpdateConnectorResponse]] = pxc.datahub.update_connector(
    name=name,
    connector_type=connector_type,
    auth_type=auth_type,
    service_uri=service_uri,
    connection_string=connection_string,
    account_name=account_name,
    account_key=account_key,
    sas_token=sas_token,
    container_name=container_name,
    s3_access_key=s3_access_key,
    s3_secret_key=s3_secret_key,
    region=region,
    bucket_name=bucket_name,
    session_token=session_token,
    role_arn=role_arn,
    session_name=session_name,
    service_endpoint_url=service_endpoint_url,
    repository=repository,
    branch=branch,
    personal_access_token=personal_access_token,
    owner=owner,
    base_url=base_url,
    organization_url=organization_url,
    project=project,
    print_message=True
)
datahub_update_connector_final: Contracts_DatahubUpdateConnectorResponse = SDKBase.get_response_data(datahub_update_connector_resp)

if datahub_update_connector_final is not None:
    print(f"success: {datahub_update_connector_final.success}")
else:
    print(f"update_connector failed: {datahub_update_connector_resp.Message}")
```

---

## Inputdata

### inputdata.convert_database_to_xml

Convert study database to XML format

**Signature:** `convert_database_to_xml(db_file_path: str, xml_file_path: str, study_id: str, print_message: bool)`

**Parameters:**
- `db_file_path` (str) *(required)*: db_file_path parameter
- `xml_file_path` (str) *(required)*: xml_file_path parameter
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ConvertDatabaseToXmlResponse`

**Response Structure:** None


**Example:**
```python
db_file_path = r"c:\path\to\database.db"
xml_file_path = r"c:\path\to\data.xml"
study_id = "550e8400-e29b-41d4-a716-446655440000"

inputdata_convert_database_to_xml_resp: list[CommandResponse[Contracts_ConvertDatabaseToXmlResponse]] = pxc.inputdata.convert_database_to_xml(db_file_path=db_file_path, xml_file_path=xml_file_path, study_id=study_id, print_message=True)
inputdata_convert_database_to_xml_final: Contracts_ConvertDatabaseToXmlResponse = SDKBase.get_response_data(inputdata_convert_database_to_xml_resp)

if inputdata_convert_database_to_xml_final is not None:
    print(inputdata_convert_database_to_xml_final)
else:
    print(f"convert_database_to_xml failed: {inputdata_convert_database_to_xml_resp.Message}")
```

---

### inputdata.convert_xml_to_database

Convert XML study data to database format

**Signature:** `convert_xml_to_database(xml_file_path: str, db_file_path: str, study_id: str, print_message: bool)`

**Parameters:**
- `xml_file_path` (str) *(required)*: xml_file_path parameter
- `db_file_path` (str) *(required)*: db_file_path parameter
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ConvertXmlToDatabaseResponse`

**Response Structure:** None


**Example:**
```python
xml_file_path = r"c:\path\to\data.xml"
db_file_path = r"c:\path\to\database.db"
study_id = "550e8400-e29b-41d4-a716-446655440000"

inputdata_convert_xml_to_database_resp: list[CommandResponse[Contracts_ConvertXmlToDatabaseResponse]] = pxc.inputdata.convert_xml_to_database(xml_file_path=xml_file_path, db_file_path=db_file_path, study_id=study_id, print_message=True)
inputdata_convert_xml_to_database_final: Contracts_ConvertXmlToDatabaseResponse = SDKBase.get_response_data(inputdata_convert_xml_to_database_resp)

if inputdata_convert_xml_to_database_final is not None:
    print(inputdata_convert_xml_to_database_final)
else:
    print(f"convert_xml_to_database failed: {inputdata_convert_xml_to_database_resp.Message}")
```

---

### inputdata.export_plexos_files

Exports PLEXOS data from a SQLite database to PLEXOS System XML, Excel, or CIM format

**Signature:** `export_plexos_files(input_sqlite_db_path: str, output_file_path: str, print_message: bool)`

**Parameters:**
- `input_sqlite_db_path` (str) *(required)*: input_sqlite_db_path parameter
- `output_file_path` (str) *(required)*: output_file_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PlexosExportResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `OutputFilePath`: Optional[str]
- `ErrorMessage`: Optional[str]
- `ObjectsExported`: Optional[int]
- `MembershipsExported`: Optional[int]
- `PropertiesExported`: Optional[int]
- `DataRecordsExported`: Optional[int]
- `TotalCountExported`: Optional[int]
- `ProcessingTimeMs`: Optional[float]

**Example:**
```python
input_sqlite_db_path = "input sqlite db path"
output_file_path = "output file path"

inputdata_export_plexos_files_resp: list[CommandResponse[Contracts_PlexosExportResponse]] = pxc.inputdata.export_plexos_files(input_sqlite_db_path=input_sqlite_db_path, output_file_path=output_file_path, print_message=True)
inputdata_export_plexos_files_final: Contracts_PlexosExportResponse = SDKBase.get_response_data(inputdata_export_plexos_files_resp)

if inputdata_export_plexos_files_final is not None:
    print(f"Success: {inputdata_export_plexos_files_final.Success}")
    print(f"OutputFilePath: {inputdata_export_plexos_files_final.OutputFilePath}")
    print(f"ErrorMessage: {inputdata_export_plexos_files_final.ErrorMessage}")
    print(f"ObjectsExported: {inputdata_export_plexos_files_final.ObjectsExported}")
    print(f"MembershipsExported: {inputdata_export_plexos_files_final.MembershipsExported}")
    print(f"PropertiesExported: {inputdata_export_plexos_files_final.PropertiesExported}")
    print(f"DataRecordsExported: {inputdata_export_plexos_files_final.DataRecordsExported}")
    print(f"TotalCountExported: {inputdata_export_plexos_files_final.TotalCountExported}")
    print(f"ProcessingTimeMs: {inputdata_export_plexos_files_final.ProcessingTimeMs}")
else:
    print(f"export_plexos_files failed: {inputdata_export_plexos_files_resp.Message}")
```

---

### inputdata.import_plexos_files

Imports power and input data from desired files into a new or existing study DB with configurable import options

**Signature:** `import_plexos_files(input_folder_path: str, import_options_config_file: Optional[str], output_folder_path: Optional[str], output_d_bpath: Optional[str], print_message: bool)`

**Parameters:**
- `input_folder_path` (str) *(required)*: Path to the folder containing PLEXOS raw files to import
- `import_options_config_file` (Optional[str]) *(optional)*: Path to the import configuration JSON file (optional, uses default if not provided) (default: `None`)
- `output_folder_path` (Optional[str]) *(optional)*: output_folder_path parameter (default: `None`)
- `output_d_bpath` (Optional[str]) *(optional)*: Complete path to the output SQLite database file (e.g., c:\path\to\output.db) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PlexosImportResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `OutputDbPath`: Optional[str]
- `ErrorMessage`: Optional[str]
- `AttemptedRecords`: Optional[int]
- `ImportedRecords`: Optional[int]
- `DuplicatedRecords`: Optional[int]
- `FailedRecords`: Optional[int]

**Example:**
```python
input_folder_path = r"c:\path\to\raw_files"
import_options_config_file = r"c:\path\to\config.json"
output_folder_path = r"c:\path\to\output"
output_d_bpath = r"c:\path\to\output\database.db"

inputdata_import_plexos_files_resp: list[CommandResponse[Contracts_PlexosImportResponse]] = pxc.inputdata.import_plexos_files(
    input_folder_path=input_folder_path,
    import_options_config_file=import_options_config_file,
    output_folder_path=output_folder_path,
    output_d_bpath=output_d_bpath,
    print_message=True
)
inputdata_import_plexos_files_final: Contracts_PlexosImportResponse = SDKBase.get_response_data(inputdata_import_plexos_files_resp)

if inputdata_import_plexos_files_final is not None:
    print(f"Success: {inputdata_import_plexos_files_final.Success}")
    print(f"OutputDbPath: {inputdata_import_plexos_files_final.OutputDbPath}")
    print(f"ErrorMessage: {inputdata_import_plexos_files_final.ErrorMessage}")
    print(f"AttemptedRecords: {inputdata_import_plexos_files_final.AttemptedRecords}")
    print(f"ImportedRecords: {inputdata_import_plexos_files_final.ImportedRecords}")
    print(f"DuplicatedRecords: {inputdata_import_plexos_files_final.DuplicatedRecords}")
    print(f"FailedRecords: {inputdata_import_plexos_files_final.FailedRecords}")
else:
    print(f"import_plexos_files failed: {inputdata_import_plexos_files_resp.Message}")
```

---

### inputdata.plexos_generate_config

Generate a default import configuration file template

**Signature:** `plexos_generate_config(output_folder_path: str, print_message: bool)`

**Parameters:**
- `output_folder_path` (str) *(required)*: output_folder_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PlexosGenerateConfigResponse`

**Response Structure:** None


**Example:**
```python
output_folder_path = r"c:\path\to\output"

inputdata_plexos_generate_config_resp: list[CommandResponse[Contracts_PlexosGenerateConfigResponse]] = pxc.inputdata.plexos_generate_config(output_folder_path=output_folder_path, print_message=True)
inputdata_plexos_generate_config_final: Contracts_PlexosGenerateConfigResponse = SDKBase.get_response_data(inputdata_plexos_generate_config_resp)

if inputdata_plexos_generate_config_final is not None:
    print(inputdata_plexos_generate_config_final)
else:
    print(f"plexos_generate_config failed: {inputdata_plexos_generate_config_resp.Message}")
```

---

## Log

### log.parse_log

Parse and analyze simulation log files

**Signature:** `parse_log(log_file_path: str, system_object_name: Optional[str], user_locale: Optional[str], print_message: bool)`

**Parameters:**
- `log_file_path` (str) *(required)*: log_file_path parameter
- `system_object_name` (Optional[str]) *(optional)*: system_object_name parameter (default: `None`)
- `user_locale` (Optional[str]) *(optional)*: user_locale parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ParseLogResponse`

**Response Structure:** 
- `LogStepDataList`: Optional[list[Simulation_LogStepDataDto]]
  - `Phase`: Optional[str]
  - `Step`: Optional[int]
  - `Steps`: Optional[int]
  - `FromDate`: Optional[str]
  - `ToDate`: Optional[str]
  - `Memory`: Optional[float]
  - `Load`: Optional[float]
  - `Generation`: Optional[float]
  - `NetExport`: Optional[float]
  - `GenCost`: Optional[float]
  - `LoadCost`: Optional[float]
  - `Unserved`: Optional[float]
  - `Price`: Optional[float]
  - `GasDemand`: Optional[float]
  - `GasSupply`: Optional[float]
  - `GasNetExchange`: Optional[float]
  - `GasDemandCost`: Optional[float]
  - `GasPrice`: Optional[float]
  - `GasExcess`: Optional[float]
  - `GasShortage`: Optional[float]

**Example:**
```python
log_file_path = r"c:\path\to\PLEXOS_log.txt"
system_object_name = "System"
user_locale = "en-US"

log_parse_log_resp: list[CommandResponse[Contracts_ParseLogResponse]] = pxc.log.parse_log(log_file_path=log_file_path, system_object_name=system_object_name, user_locale=user_locale, print_message=True)
log_parse_log_final: Contracts_ParseLogResponse = SDKBase.get_response_data(log_parse_log_resp)

if log_parse_log_final is not None:
    if log_parse_log_final.LogStepDataList is not None:
        for item in log_parse_log_final.LogStepDataList:
            print(f"Phase: {item.Phase}")
            print(f"Step: {item.Step}")
            print(f"Steps: {item.Steps}")
            print(f"FromDate: {item.FromDate}")
            # ... and 16 more properties
    else:
        print(f"No LogStepDataList returned")
else:
    print(f"parse_log failed: {log_parse_log_resp.Message}")
```

---

## Secrets

### secrets.create_secret

Create a new secret with secure value handling

**Signature:** `create_secret(name: Optional[str], value: Optional[str], value_from_stdin: Optional[bool], value_from_file: Optional[str], print_message: bool)`

**Parameters:**
- `name` (Optional[str]) *(optional)*: Name or identifier for the resource (default: `None`)
- `value` (Optional[str]) *(optional)*: Value to be stored or updated (default: `None`)
- `value_from_stdin` (Optional[bool]) *(optional)*: Read secret value from standard input (secure) (default: `None`)
- `value_from_file` (Optional[str]) *(optional)*: File path to read secret value from (most secure) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CreateSecretResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `SecretName`: Optional[str]
- `SecretId`: Optional[str]

**Example:**
```python
name = "My Name"
value = "example_value"
value_from_stdin = True
value_from_file = r"c:\path\to\secret.txt"

secrets_create_secret_resp: list[CommandResponse[Contracts_CreateSecretResponse]] = pxc.secrets.create_secret(
    name=name,
    value=value,
    value_from_stdin=value_from_stdin,
    value_from_file=value_from_file,
    print_message=True
)
secrets_create_secret_final: Contracts_CreateSecretResponse = SDKBase.get_response_data(secrets_create_secret_resp)

if secrets_create_secret_final is not None:
    print(f"Success: {secrets_create_secret_final.Success}")
    print(f"SecretName: {secrets_create_secret_final.SecretName}")
    print(f"SecretId: {secrets_create_secret_final.SecretId}")
else:
    print(f"create_secret failed: {secrets_create_secret_resp.Message}")
```

---

### secrets.delete_secret

Delete a secret permanently

**Signature:** `delete_secret(secret_id: Optional[str], confirm: Optional[bool], print_message: bool)`

**Parameters:**
- `secret_id` (Optional[str]) *(optional)*: Unique identifier for a specific secret (default: `None`)
- `confirm` (Optional[bool]) *(optional)*: Skip confirmation prompt for destructive operations (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DeleteSecretResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `SecretName`: Optional[str]
- `SecretId`: Optional[str]

**Example:**
```python
secret_id = "550e8400-e29b-41d4-a716-446655440000"
confirm = True

secrets_delete_secret_resp: list[CommandResponse[Contracts_DeleteSecretResponse]] = pxc.secrets.delete_secret(secret_id=secret_id, confirm=confirm, print_message=True)
secrets_delete_secret_final: Contracts_DeleteSecretResponse = SDKBase.get_response_data(secrets_delete_secret_resp)

if secrets_delete_secret_final is not None:
    print(f"Success: {secrets_delete_secret_final.Success}")
    print(f"SecretName: {secrets_delete_secret_final.SecretName}")
    print(f"SecretId: {secrets_delete_secret_final.SecretId}")
else:
    print(f"delete_secret failed: {secrets_delete_secret_resp.Message}")
```

---

### secrets.list_secrets

List all secrets metadata (values are never exposed)

**Signature:** `list_secrets(order_by: Optional[str], descending: Optional[bool], print_message: bool)`

**Parameters:**
- `order_by` (Optional[str]) *(optional)*: Field to order results by (default: `None`)
- `descending` (Optional[bool]) *(optional)*: Order results in descending order (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSecretsResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Secrets`: Optional[list[Secrets_SecretInfo]]
  - `SecretId`: Optional[str]
  - `Name`: Optional[str]
  - `CreatedAtUtc`: Optional[str]
  - `LastModifiedAtUtc`: Optional[str]

**Example:**
```python
order_by = "CreatedAt"
descending = True

secrets_list_secrets_resp: list[CommandResponse[Contracts_ListSecretsResponse]] = pxc.secrets.list_secrets(order_by=order_by, descending=descending, print_message=True)
secrets_list_secrets_final: Contracts_ListSecretsResponse = SDKBase.get_response_data(secrets_list_secrets_resp)

if secrets_list_secrets_final is not None:
    print(f"Success: {secrets_list_secrets_final.Success}")
    if secrets_list_secrets_final.Secrets is not None:
        for item in secrets_list_secrets_final.Secrets:
            print(f"SecretId: {item.SecretId}")
            print(f"Name: {item.Name}")
            print(f"CreatedAtUtc: {item.CreatedAtUtc}")
            print(f"LastModifiedAtUtc: {item.LastModifiedAtUtc}")
    else:
        print(f"No Secrets returned")
else:
    print(f"list_secrets failed: {secrets_list_secrets_resp.Message}")
```

---

### secrets.update_secret

Update an existing secret's value securely

**Signature:** `update_secret(secret_id: Optional[str], value: Optional[str], value_from_stdin: Optional[bool], value_from_file: Optional[str], print_message: bool)`

**Parameters:**
- `secret_id` (Optional[str]) *(optional)*: Unique identifier for a specific secret (default: `None`)
- `value` (Optional[str]) *(optional)*: Value to be stored or updated (default: `None`)
- `value_from_stdin` (Optional[bool]) *(optional)*: Read secret value from standard input (secure) (default: `None`)
- `value_from_file` (Optional[str]) *(optional)*: File path to read secret value from (most secure) (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_UpdateSecretResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `SecretName`: Optional[str]
- `SecretId`: Optional[str]

**Example:**
```python
secret_id = "550e8400-e29b-41d4-a716-446655440000"
value = "example_value"
value_from_stdin = True
value_from_file = r"c:\path\to\secret.txt"

secrets_update_secret_resp: list[CommandResponse[Contracts_UpdateSecretResponse]] = pxc.secrets.update_secret(
    secret_id=secret_id,
    value=value,
    value_from_stdin=value_from_stdin,
    value_from_file=value_from_file,
    print_message=True
)
secrets_update_secret_final: Contracts_UpdateSecretResponse = SDKBase.get_response_data(secrets_update_secret_resp)

if secrets_update_secret_final is not None:
    print(f"Success: {secrets_update_secret_final.Success}")
    print(f"SecretName: {secrets_update_secret_final.SecretName}")
    print(f"SecretId: {secrets_update_secret_final.SecretId}")
else:
    print(f"update_secret failed: {secrets_update_secret_resp.Message}")
```

---

## Simulation

### simulation.build_simulation_request_from_id

Build a simulation request from an existing simulation ID - use enqueue_simulation for new simulations

**Signature:** `build_simulation_request_from_id(simulation_id: str, output_directory: str, file_name: str, overwrite: bool, study_id: Optional[str], changeset_id: Optional[str], model_name: Optional[str], requested_cpu_cores: Optional[int], requested_memory: Optional[float], print_message: bool)`

**Parameters:**
- `simulation_id` (str) *(required)*: Unique identifier for a specific simulation
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `file_name` (str) *(required)*: file_name parameter
- `overwrite` (bool) *(required)*: overwrite parameter
- `study_id` (Optional[str]) *(optional)*: Unique identifier for a specific study (default: `None`)
- `changeset_id` (Optional[str]) *(optional)*: Unique identifier for a specific changeset (default: `None`)
- `model_name` (Optional[str]) *(optional)*: model_name parameter (default: `None`)
- `requested_cpu_cores` (Optional[int]) *(optional)*: requested_cpu_cores parameter (default: `None`)
- `requested_memory` (Optional[float]) *(optional)*: requested_memory parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_BuildSimulationRequestFromIdResponse`

**Response Structure:** 
- `SimulationContract`: Optional[Simulation_EnqueueSimulationRequest]
  - `StudyId`: Optional[str]
  - `ChangeSetId`: Optional[str]
  - `Models`: Optional[list[str]]
  - `SimulationOptions`: Optional[Simulation_SimulationOption]
    - `Locale`: Optional[int]
    - `SimulationTasks`: Optional[list[Simulation_TaskDefinition]]
      - `Name`: Optional[str]
      - `Files`: Optional[list[Simulation_FileVersion]]
        - `Path`: Optional[str]
        - `Version`: Optional[int]
        - `SnapshotDate`: Optional[str]
      - `TaskType`: Optional[Simulation_TaskDefinitionTypeEnum]
      - `ContinueOnError`: Optional[bool]
      - `ExecutionOrder`: Optional[int]
      - `AppliesTo`: Optional[list[Simulation_AppliesToEnum]]
    - `MaxRetries`: Optional[int]
    - `EnableRealTimeLog`: Optional[bool]
    - `IsModelDistributionRun`: Optional[bool]
    - `SimulationRunType`: Optional[Simulation_SimulationRunType]
  - `ParallelizationOptions`: Optional[Simulation_ParallelizationOption]
    - `InstanceCount`: Optional[int]
  - `SimulationData`: Optional[list[Simulation_SimulationDataUri]]
    - `Uri`: Optional[str]
    - `Type`: Optional[Simulation_SimulationDataType]
  - `SimulationEngine`: Optional[Simulation_SimulationEngine]
    - `EngineId`: Optional[str]
    - `Version`: Optional[str]
    - `OperatingSystem`: Optional[Simulation_OperatingSystemEnum]
  - `Tags`: Optional[dict[(str, str)]]
  - `Source`: Optional[str]
  - `Priority`: Optional[int]
  - `RequestedCpuCores`: Optional[int]
  - `MinimumMemoryInGb`: Optional[float]
  - `SimulationType`: Optional[Simulation_SimulationTypeEnum]
- `fileOutput`: Optional[str]

**Example:**
```python
simulation_id = "550e8400-e29b-41d4-a716-446655440000"
output_directory = r"c:\output"
file_name = "output.txt"
overwrite = True
study_id = None
changeset_id = None
model_name = "MyModel"
requested_cpu_cores = 4
requested_memory = "value"

simulation_build_simulation_request_from_id_resp: list[CommandResponse[Contracts_BuildSimulationRequestFromIdResponse]] = pxc.simulation.build_simulation_request_from_id(
    simulation_id=simulation_id,
    output_directory=output_directory,
    file_name=file_name,
    overwrite=overwrite,
    study_id=study_id,
    changeset_id=changeset_id,
    model_name=model_name,
    requested_cpu_cores=requested_cpu_cores,
    requested_memory=requested_memory,
    print_message=True
)
simulation_build_simulation_request_from_id_final: Contracts_BuildSimulationRequestFromIdResponse = SDKBase.get_response_data(simulation_build_simulation_request_from_id_resp)

if simulation_build_simulation_request_from_id_final is not None:
    print(f"SimulationContract: {simulation_build_simulation_request_from_id_final.SimulationContract}")
    print(f"fileOutput: {simulation_build_simulation_request_from_id_final.fileOutput}")
else:
    print(f"build_simulation_request_from_id failed: {simulation_build_simulation_request_from_id_resp.Message}")
```

---

### simulation.cancel_simulation

Cancel a running simulation

**Signature:** `cancel_simulation(simulation_id: str, print_message: bool)`

**Parameters:**
- `simulation_id` (str) *(required)*: Unique identifier for a specific simulation
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CancelSimulationResponse`

**Response Structure:** 
- `SimulationId`: Optional[str]
- `SimulationCancellationStatus`: Optional[Simulation_SimulationCancellationStatusEnum]

**Example:**
```python
simulation_id = "550e8400-e29b-41d4-a716-446655440000"

simulation_cancel_simulation_resp: list[CommandResponse[Contracts_CancelSimulationResponse]] = pxc.simulation.cancel_simulation(simulation_id=simulation_id, print_message=True)
simulation_cancel_simulation_final: Contracts_CancelSimulationResponse = SDKBase.get_response_data(simulation_cancel_simulation_resp)

if simulation_cancel_simulation_final is not None:
    print(f"SimulationId: {simulation_cancel_simulation_final.SimulationId}")
    print(f"SimulationCancellationStatus: {simulation_cancel_simulation_final.SimulationCancellationStatus}")
else:
    print(f"cancel_simulation failed: {simulation_cancel_simulation_resp.Message}")
```

---

### simulation.check_simulation_progress

Check the progress of a specific simulation. Returns current status, phase, progress value, and messages.

**Signature:** `check_simulation_progress(simulation_id: str, print_message: bool)`

**Parameters:**
- `simulation_id` (str) *(required)*: Unique identifier for a specific simulation
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CheckSimulationProgressResponse`

**Response Structure:** 
- `SimulationId`: Optional[str]
- `StudyId`: Optional[str]
- `Status`: Optional[str]
- `Phase`: Optional[str]
- `Value`: Optional[float]
- `ModelName`: Optional[str]
- `ModelIndex`: Optional[int]
- `ModelCount`: Optional[int]
- `Message`: Optional[str]
- `LastUpdateDate`: Optional[str]

**Example:**
```python
simulation_id = "550e8400-e29b-41d4-a716-446655440000"

simulation_check_simulation_progress_resp: list[CommandResponse[Contracts_CheckSimulationProgressResponse]] = pxc.simulation.check_simulation_progress(simulation_id=simulation_id, print_message=True)
simulation_check_simulation_progress_final: Contracts_CheckSimulationProgressResponse = SDKBase.get_response_data(simulation_check_simulation_progress_resp)

if simulation_check_simulation_progress_final is not None:
    print(f"SimulationId: {simulation_check_simulation_progress_final.SimulationId}")
    print(f"StudyId: {simulation_check_simulation_progress_final.StudyId}")
    print(f"Status: {simulation_check_simulation_progress_final.Status}")
    print(f"Phase: {simulation_check_simulation_progress_final.Phase}")
    print(f"Value: {simulation_check_simulation_progress_final.Value}")
    print(f"ModelName: {simulation_check_simulation_progress_final.ModelName}")
    print(f"ModelIndex: {simulation_check_simulation_progress_final.ModelIndex}")
    print(f"ModelCount: {simulation_check_simulation_progress_final.ModelCount}")
    print(f"Message: {simulation_check_simulation_progress_final.Message}")
    print(f"LastUpdateDate: {simulation_check_simulation_progress_final.LastUpdateDate}")
else:
    print(f"check_simulation_progress failed: {simulation_check_simulation_progress_resp.Message}")
```

---

### simulation.list_simulations

List simulations by Id parameters or with optional filtering. Returns simulation records with primary Id, current status, ExecutionId, and ModelIdentifiers when completed.

**Signature:** `list_simulations(simulation_id: Optional[str], study_id: Optional[str], execution_id: Optional[str], changeset_id: Optional[str], order_by: Optional[str], descending: Optional[bool], top: Optional[int], skip: Optional[int], raw: Optional[str], print_message: bool)`

**Parameters:**
- `simulation_id` (Optional[str]) *(optional)*: Unique identifier for a specific simulation (default: `None`)
- `study_id` (Optional[str]) *(optional)*: Unique identifier for a specific study (default: `None`)
- `execution_id` (Optional[str]) *(optional)*: Unique identifier for a specific execution (default: `None`)
- `changeset_id` (Optional[str]) *(optional)*: Unique identifier for a specific changeset (default: `None`)
- `order_by` (Optional[str]) *(optional)*: Field to order results by (default: `None`)
- `descending` (Optional[bool]) *(optional)*: Order results in descending order (default: `None`)
- `top` (Optional[int]) *(optional)*: Maximum number of results to return (default: `None`)
- `skip` (Optional[int]) *(optional)*: Number of results to skip (default: `None`)
- `raw` (Optional[str]) *(optional)*: Raw OData query string for advanced queries (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSimulationResponse`

**Response Structure:** 
- `SimulationRecords`: Optional[list[Contracts_Simulation]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `ExecutionId`: Optional[GuidValue] → Access via `.Value` property
  - `StudyId`: Optional[GuidValue] → Access via `.Value` property
  - `CreatedByUser`: Optional[Contracts_User]
    - `Name`: Optional[str]
    - `Id`: Optional[str]
  - `CreatedAt`: Optional[str]
  - `LastUpdatedAt`: Optional[str]
  - `Models`: Optional[list[str]]
  - `Status`: Optional[str]
  - `ModelIdentifiers`: Optional[list[Contracts_ModelIdentifier]]
    - `Id`: Optional[str] → use as solution_id parameter
    - `Name`: Optional[str]
  - `RetryCount`: Optional[int]

**Example:**
```python
simulation_id = "550e8400-e29b-41d4-a716-446655440000"
study_id = None
execution_id = None
changeset_id = None
order_by = "CreatedAt"
descending = True
top = 10
skip = 0
raw = "filter expression"

simulation_list_simulations_resp: list[CommandResponse[Contracts_ListSimulationResponse]] = pxc.simulation.list_simulations(
    simulation_id=simulation_id,
    study_id=study_id,
    execution_id=execution_id,
    changeset_id=changeset_id,
    order_by=order_by,
    descending=descending,
    top=top,
    skip=skip,
    raw=raw,
    print_message=True
)
simulation_list_simulations_final: Contracts_ListSimulationResponse = SDKBase.get_response_data(simulation_list_simulations_resp)

if simulation_list_simulations_final is not None:
    if simulation_list_simulations_final.SimulationRecords is not None:
        for item in simulation_list_simulations_final.SimulationRecords:
            print(f"Id: {item.Id.Value}")
            print(f"ExecutionId: {item.ExecutionId.Value}")
            print(f"StudyId: {item.StudyId.Value}")
            print(f"CreatedByUser: {item.CreatedByUser}")
            # ... and 6 more properties
    else:
        print(f"No SimulationRecords returned")
else:
    print(f"list_simulations failed: {simulation_list_simulations_resp.Message}")
```

---

### simulation.enqueue_simulation

Enqueue a new simulation using JSON file containing EnqueueSimulationRequest structure. Returns simulation ID and initial status.

**Signature:** `enqueue_simulation(file_path: str, print_message: bool)`

**Parameters:**
- `file_path` (str) *(required)*: file_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_EnqueueSimulationResponse`

**Response Structure:** 
- `SimulationStarted`: Optional[list[Contracts_SimulationStarted]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `ExecutionId`: Optional[GuidValue] → Access via `.Value` property
  - `Status`: Optional[str]

**Example:**
```python
file_path = r"c:\path\to\file.txt"

simulation_enqueue_simulation_resp: list[CommandResponse[Contracts_EnqueueSimulationResponse]] = pxc.simulation.enqueue_simulation(file_path=file_path, print_message=True)
simulation_enqueue_simulation_final: Contracts_EnqueueSimulationResponse = SDKBase.get_response_data(simulation_enqueue_simulation_resp)

if simulation_enqueue_simulation_final is not None:
    if simulation_enqueue_simulation_final.SimulationStarted is not None:
        for item in simulation_enqueue_simulation_final.SimulationStarted:
            print(f"Id: {item.Id.Value}")
            print(f"ExecutionId: {item.ExecutionId.Value}")
            print(f"Status: {item.Status}")
    else:
        print(f"No SimulationStarted returned")
else:
    print(f"enqueue_simulation failed: {simulation_enqueue_simulation_resp.Message}")
```

---

### simulation.list_simulation_engines

List available simulation engines

**Signature:** `list_simulation_engines(optimization_engine_type: Optional[str], print_message: bool)`

**Parameters:**
- `optimization_engine_type` (Optional[str]) *(optional)*: optimization_engine_type parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSimulationEngineResponse`

**Response Structure:** 
- `SimulationEngines`: Optional[list[Contracts_AvailableEngine]]
  - `Id`: Optional[str]
  - `Version`: Optional[str]
  - `DisplayName`: Optional[str]
  - `Description`: Optional[str]
  - `Status`: Optional[str]
  - `ReleasedDate`: Optional[str]
  - `OperatingSystem`: Optional[str]
  - `EngineType`: Optional[str]
  - `OptimizationEngine`: Optional[str]

**Example:**
```python
optimization_engine_type = "PLEXOS"

simulation_list_simulation_engines_resp: list[CommandResponse[Contracts_ListSimulationEngineResponse]] = pxc.simulation.list_simulation_engines(optimization_engine_type=optimization_engine_type, print_message=True)
simulation_list_simulation_engines_final: Contracts_ListSimulationEngineResponse = SDKBase.get_response_data(simulation_list_simulation_engines_resp)

if simulation_list_simulation_engines_final is not None:
    if simulation_list_simulation_engines_final.SimulationEngines is not None:
        for item in simulation_list_simulation_engines_final.SimulationEngines:
            print(f"Id: {item.Id}")
            print(f"Version: {item.Version}")
            print(f"DisplayName: {item.DisplayName}")
            print(f"Description: {item.Description}")
            # ... and 5 more properties
    else:
        print(f"No SimulationEngines returned")
else:
    print(f"list_simulation_engines failed: {simulation_list_simulation_engines_resp.Message}")
```

---

### simulation.list_simulation_pool_capability

List available simulation pool capabilities

**Signature:** `list_simulation_pool_capability(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSimulationPoolCapabilityResponse`

**Response Structure:** 
- `SimulationPoolCapabilities`: Optional[list[Contracts_SimulationPoolCapability]]
  - `Type`: Optional[str]
  - `Cores`: Optional[int]
  - `Memory`: Optional[float]
  - `BaseClockSpeed`: Optional[float]
  - `OperatingSystem`: Optional[str]
  - `Capacity`: Optional[int]

**Example:**
```python
simulation_list_simulation_pool_capability_resp: list[CommandResponse[Contracts_ListSimulationPoolCapabilityResponse]] = pxc.simulation.list_simulation_pool_capability(print_message=True)
simulation_list_simulation_pool_capability_final: Contracts_ListSimulationPoolCapabilityResponse = SDKBase.get_response_data(simulation_list_simulation_pool_capability_resp)

if simulation_list_simulation_pool_capability_final is not None:
    if simulation_list_simulation_pool_capability_final.SimulationPoolCapabilities is not None:
        for item in simulation_list_simulation_pool_capability_final.SimulationPoolCapabilities:
            print(f"Type: {item.Type}")
            print(f"Cores: {item.Cores}")
            print(f"Memory: {item.Memory}")
            print(f"BaseClockSpeed: {item.BaseClockSpeed}")
            # ... and 2 more properties
    else:
        print(f"No SimulationPoolCapabilities returned")
else:
    print(f"list_simulation_pool_capability failed: {simulation_list_simulation_pool_capability_resp.Message}")
```

---

## Solution

### solution.archive_solution

Archive a solution to save storage space

**Signature:** `archive_solution(execution_id: str, print_message: bool)`

**Parameters:**
- `execution_id` (str) *(required)*: Unique identifier for a specific execution
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionStatusCommandResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `SolutionStatus`: Optional[str]
- `ExecutionId`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_archive_solution_resp: list[CommandResponse[Contracts_SolutionStatusCommandResponse]] = pxc.solution.archive_solution(execution_id=execution_id, print_message=True)
solution_archive_solution_final: Contracts_SolutionStatusCommandResponse = SDKBase.get_response_data(solution_archive_solution_resp)

if solution_archive_solution_final is not None:
    print(f"SolutionId: {solution_archive_solution_final.SolutionId}")
    print(f"SolutionStatus: {solution_archive_solution_final.SolutionStatus}")
    print(f"ExecutionId: {solution_archive_solution_final.ExecutionId}")
else:
    print(f"archive_solution failed: {solution_archive_solution_resp.Message}")
```

---

### solution.delete_solution

Delete a solution permanently

**Signature:** `delete_solution(execution_id: str, print_message: bool)`

**Parameters:**
- `execution_id` (str) *(required)*: Unique identifier for a specific execution
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionStatusCommandResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `SolutionStatus`: Optional[str]
- `ExecutionId`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_delete_solution_resp: list[CommandResponse[Contracts_SolutionStatusCommandResponse]] = pxc.solution.delete_solution(execution_id=execution_id, print_message=True)
solution_delete_solution_final: Contracts_SolutionStatusCommandResponse = SDKBase.get_response_data(solution_delete_solution_resp)

if solution_delete_solution_final is not None:
    print(f"SolutionId: {solution_delete_solution_final.SolutionId}")
    print(f"SolutionStatus: {solution_delete_solution_final.SolutionStatus}")
    print(f"ExecutionId: {solution_delete_solution_final.ExecutionId}")
else:
    print(f"delete_solution failed: {solution_delete_solution_resp.Message}")
```

---

### solution.get_solution_id

Get solution ID from study ID and model name

**Signature:** `get_solution_id(study_id: str, model_name: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `model_name` (str) *(required)*: model_name parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetSolutionIdResponse`

**Response Structure:** 
- `ChangesetId`: Optional[str]
- `SolutionId`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
model_name = "MyModel"

solution_get_solution_id_resp: list[CommandResponse[Contracts_GetSolutionIdResponse]] = pxc.solution.get_solution_id(study_id=study_id, model_name=model_name, print_message=True)
solution_get_solution_id_final: Contracts_GetSolutionIdResponse = SDKBase.get_response_data(solution_get_solution_id_resp)

if solution_get_solution_id_final is not None:
    print(f"ChangesetId: {solution_get_solution_id_final.ChangesetId}")
    print(f"SolutionId: {solution_get_solution_id_final.SolutionId}")
else:
    print(f"get_solution_id failed: {solution_get_solution_id_resp.Message}")
```

---

### solution.list_solution_reports

List available report types for solutions

**Signature:** `list_solution_reports(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSolutionReportResponse`

**Response Structure:** 
- `SolutionReports`: Optional[list[Contracts_SolutionReport]]
  - `ReportId`: Optional[str]
  - `ReportName`: Optional[str]

**Example:**
```python
solution_list_solution_reports_resp: list[CommandResponse[Contracts_ListSolutionReportResponse]] = pxc.solution.list_solution_reports(print_message=True)
solution_list_solution_reports_final: Contracts_ListSolutionReportResponse = SDKBase.get_response_data(solution_list_solution_reports_resp)

if solution_list_solution_reports_final is not None:
    if solution_list_solution_reports_final.SolutionReports is not None:
        for item in solution_list_solution_reports_final.SolutionReports:
            print(f"ReportId: {item.ReportId}")
            print(f"ReportName: {item.ReportName}")
    else:
        print(f"No SolutionReports returned")
else:
    print(f"list_solution_reports failed: {solution_list_solution_reports_resp.Message}")
```

---

### solution.list_solutions

List solutions with optional filtering

**Signature:** `list_solutions(solution_id: Optional[str], study_id: Optional[str], simulation_id: Optional[str], execution_id: Optional[str], type: Optional[str], status: Optional[str], order_by: Optional[str], descending: Optional[bool], top: Optional[int], skip: Optional[int], raw: Optional[str], print_message: bool)`

**Parameters:**
- `solution_id` (Optional[str]) *(optional)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results) (default: `None`)
- `study_id` (Optional[str]) *(optional)*: Unique identifier for a specific study (default: `None`)
- `simulation_id` (Optional[str]) *(optional)*: Unique identifier for a specific simulation (default: `None`)
- `execution_id` (Optional[str]) *(optional)*: Unique identifier for a specific execution (default: `None`)
- `type` (Optional[str]) *(optional)*: type parameter (default: `None`)
- `status` (Optional[str]) *(optional)*: Execution status value used for filtering (default: `None`)
- `order_by` (Optional[str]) *(optional)*: Field to order results by (default: `None`)
- `descending` (Optional[bool]) *(optional)*: Order results in descending order (default: `None`)
- `top` (Optional[int]) *(optional)*: Maximum number of results to return (default: `None`)
- `skip` (Optional[int]) *(optional)*: Number of results to skip (default: `None`)
- `raw` (Optional[str]) *(optional)*: Raw OData query string for advanced queries (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSolutionsResponse`

**Response Structure:** 
- `Solutions`: Optional[list[Contracts_Solution]]
  - `SolutionId`: Optional[GuidValue] → Access via `.Value` property
  - `StudyId`: Optional[GuidValue] → Access via `.Value` property
  - `ExecutionId`: Optional[GuidValue] → Access via `.Value` property
  - `SimulationId`: Optional[GuidValue] → Access via `.Value` property
  - `Type`: Optional[str]
  - `Status`: Optional[str]
  - `LastUpdatedDate`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `ModelName`: Optional[str]
  - `TypeVersion`: Optional[int]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"
study_id = "550e8400-e29b-41d4-a716-446655440000"
simulation_id = None
execution_id = None
type = "Standard"
status = "Active"
order_by = "CreatedAt"
descending = True
top = 10
skip = 0
raw = "filter expression"

solution_list_solutions_resp: list[CommandResponse[Contracts_ListSolutionsResponse]] = pxc.solution.list_solutions(
    solution_id=solution_id,
    study_id=study_id,
    simulation_id=simulation_id,
    execution_id=execution_id,
    type=type,
    status=status,
    order_by=order_by,
    descending=descending,
    top=top,
    skip=skip,
    raw=raw,
    print_message=True
)
solution_list_solutions_final: Contracts_ListSolutionsResponse = SDKBase.get_response_data(solution_list_solutions_resp)

if solution_list_solutions_final is not None:
    if solution_list_solutions_final.Solutions is not None:
        for item in solution_list_solutions_final.Solutions:
            print(f"SolutionId: {item.SolutionId.Value}")
            print(f"StudyId: {item.StudyId.Value}")
            print(f"ExecutionId: {item.ExecutionId.Value}")
            print(f"SimulationId: {item.SimulationId.Value}")
            # ... and 6 more properties
    else:
        print(f"No Solutions returned")
else:
    print(f"list_solutions failed: {solution_list_solutions_resp.Message}")
```

---

### solution.solution_reports

Generate reports for a solution

**Signature:** `solution_reports(solution_id: str, report_id: str, output_directory: str, file: Optional[str], print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `report_id` (str) *(required)*: report_id parameter
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `file` (Optional[str]) *(optional)*: file parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionReportsEmptyResponse`

**Response Structure:** None


**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"
report_id = "550e8400-e29b-41d4-a716-446655440000"
output_directory = r"c:\output"
file = "data.csv"

solution_solution_reports_resp: list[CommandResponse[Contracts_SolutionReportsEmptyResponse]] = pxc.solution.solution_reports(
    solution_id=solution_id,
    report_id=report_id,
    output_directory=output_directory,
    file=file,
    print_message=True
)
solution_solution_reports_final: Contracts_SolutionReportsEmptyResponse = SDKBase.get_response_data(solution_solution_reports_resp)

if solution_solution_reports_final is not None:
    print(solution_solution_reports_final)
else:
    print(f"solution_reports failed: {solution_solution_reports_resp.Message}")
```

---

### solution.solution_stitching

Stitch together solution data from parallel runs

**Signature:** `solution_stitching(execution_id: str, number_of_cores: int, memory_in_gb: float, print_message: bool)`

**Parameters:**
- `execution_id` (str) *(required)*: Unique identifier for a specific execution
- `number_of_cores` (int) *(required)*: number_of_cores parameter
- `memory_in_gb` (float) *(required)*: memory_in_gb parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionStitchingResponse`

**Response Structure:** 
- `Data`: Optional[Simulation_EnqueuedSimulation]
  - `Id`: Optional[str]
  - `CreatedAt`: Optional[str]
  - `Status`: Optional[str]
  - `ExecutionId`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"
number_of_cores = 4
memory_in_gb = 8.0

solution_solution_stitching_resp: list[CommandResponse[Contracts_SolutionStitchingResponse]] = pxc.solution.solution_stitching(execution_id=execution_id, number_of_cores=number_of_cores, memory_in_gb=memory_in_gb, print_message=True)
solution_solution_stitching_final: Contracts_SolutionStitchingResponse = SDKBase.get_response_data(solution_solution_stitching_resp)

if solution_solution_stitching_final is not None:
    print(f"Data: {solution_solution_stitching_final.Data}")
else:
    print(f"solution_stitching failed: {solution_solution_stitching_resp.Message}")
```

---

### solution.unarchive_solution

Restore a previously archived solution

**Signature:** `unarchive_solution(execution_id: str, print_message: bool)`

**Parameters:**
- `execution_id` (str) *(required)*: Unique identifier for a specific execution
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionStatusCommandResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `SolutionStatus`: Optional[str]
- `ExecutionId`: Optional[str]

**Example:**
```python
execution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_unarchive_solution_resp: list[CommandResponse[Contracts_SolutionStatusCommandResponse]] = pxc.solution.unarchive_solution(execution_id=execution_id, print_message=True)
solution_unarchive_solution_final: Contracts_SolutionStatusCommandResponse = SDKBase.get_response_data(solution_unarchive_solution_resp)

if solution_unarchive_solution_final is not None:
    print(f"SolutionId: {solution_unarchive_solution_final.SolutionId}")
    print(f"SolutionStatus: {solution_unarchive_solution_final.SolutionStatus}")
    print(f"ExecutionId: {solution_unarchive_solution_final.ExecutionId}")
else:
    print(f"unarchive_solution failed: {solution_unarchive_solution_resp.Message}")
```

---

### solution.get_solution_data_using_view

Get solution data using a predefined view

**Signature:** `get_solution_data_using_view(output_directory: str, solution_id: str, report_id: str, view_id: str, overwrite: Optional[bool], file: Optional[str], print_message: bool)`

**Parameters:**
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `report_id` (str) *(required)*: report_id parameter
- `view_id` (str) *(required)*: view_id parameter
- `overwrite` (Optional[bool]) *(optional)*: overwrite parameter (default: `None`)
- `file` (Optional[str]) *(optional)*: file parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetSolutionReportDataResponse`

**Response Structure:** 
- `FilePath`: Optional[str]

**Example:**
```python
output_directory = r"c:\output"
solution_id = "550e8400-e29b-41d4-a716-446655440000"
report_id = "550e8400-e29b-41d4-a716-446655440000"
view_id = "550e8400-e29b-41d4-a716-446655440000"
overwrite = True
file = "data.csv"

solution_get_solution_data_using_view_resp: list[CommandResponse[Contracts_GetSolutionReportDataResponse]] = pxc.solution.get_solution_data_using_view(
    output_directory=output_directory,
    solution_id=solution_id,
    report_id=report_id,
    view_id=view_id,
    overwrite=overwrite,
    file=file,
    print_message=True
)
solution_get_solution_data_using_view_final: Contracts_GetSolutionReportDataResponse = SDKBase.get_response_data(solution_get_solution_data_using_view_resp)

if solution_get_solution_data_using_view_final is not None:
    print(f"FilePath: {solution_get_solution_data_using_view_final.FilePath}")
else:
    print(f"get_solution_data_using_view failed: {solution_get_solution_data_using_view_resp.Message}")
```

---

### solution.get_view_reports_details

Get details about available view reports

**Signature:** `get_view_reports_details(view_id: str, print_message: bool)`

**Parameters:**
- `view_id` (str) *(required)*: view_id parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetViewReportsDetailsResponse`

**Response Structure:** 
- `ViewReportDetials`: Optional[Solution_ViewReportDetails]
  - `ViewId`: Optional[str]
  - `ViewName`: Optional[str]
  - `Reports`: Optional[list[Solution_ViewReport]]
    - `Id`: Optional[str]
    - `Name`: Optional[str]
    - `SolutionId`: Optional[str]
    - `ModelName`: Optional[str]
    - `Command`: Optional[str]
    - `Type`: Optional[str]

**Example:**
```python
view_id = "550e8400-e29b-41d4-a716-446655440000"

solution_get_view_reports_details_resp: list[CommandResponse[Contracts_GetViewReportsDetailsResponse]] = pxc.solution.get_view_reports_details(view_id=view_id, print_message=True)
solution_get_view_reports_details_final: Contracts_GetViewReportsDetailsResponse = SDKBase.get_response_data(solution_get_view_reports_details_resp)

if solution_get_view_reports_details_final is not None:
    print(f"ViewReportDetials: {solution_get_view_reports_details_final.ViewReportDetials}")
else:
    print(f"get_view_reports_details failed: {solution_get_view_reports_details_resp.Message}")
```

---

### solution.publish_view

Publish a new solution view

**Signature:** `publish_view(view_file_path: str, print_message: bool)`

**Parameters:**
- `view_file_path` (str) *(required)*: view_file_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PublishViewResponse`

**Response Structure:** 
- `ViewId`: Optional[str]

**Example:**
```python
view_file_path = r"c:\path\to\view.json"

solution_publish_view_resp: list[CommandResponse[Contracts_PublishViewResponse]] = pxc.solution.publish_view(view_file_path=view_file_path, print_message=True)
solution_publish_view_final: Contracts_PublishViewResponse = SDKBase.get_response_data(solution_publish_view_resp)

if solution_publish_view_final is not None:
    print(f"ViewId: {solution_publish_view_final.ViewId}")
else:
    print(f"publish_view failed: {solution_publish_view_resp.Message}")
```

---

### solution.query_solution_sql

Execute SQL queries against Solution resources

**Signature:** `query_solution_sql(solution_id: str, sql: str, print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `sql` (str) *(required)*: SQL query to execute
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_SolutionQueryResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Results`: Optional[list[dict[(str, str)]]]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"
sql = "select * from fullkeyinfo"

solution_query_solution_sql_resp: list[CommandResponse[Contracts_SolutionQueryResponse]] = pxc.solution.query_solution_sql(solution_id=solution_id, sql=sql, print_message=True)
solution_query_solution_sql_final: Contracts_SolutionQueryResponse = SDKBase.get_response_data(solution_query_solution_sql_resp)

if solution_query_solution_sql_final is not None:
    print(f"Success: {solution_query_solution_sql_final.Success}")
    if solution_query_solution_sql_final.Results is not None:
        for item in solution_query_solution_sql_final.Results:
            print(f"Item: {item}")
    else:
        print(f"No Results returned")
else:
    print(f"query_solution_sql failed: {solution_query_solution_sql_resp.Message}")
```

---

### solution.download_solution

Download a solution to local storage

**Signature:** `download_solution(solution_id: str, output_directory: str, solution_type: Optional[str], overwrite: Optional[bool], file_name: Optional[str], generate_metadata: Optional[bool], metadata_file_name: Optional[str], print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `solution_type` (Optional[str]) *(optional)*: solution_type parameter (default: `None`)
- `overwrite` (Optional[bool]) *(optional)*: overwrite parameter (default: `None`)
- `file_name` (Optional[str]) *(optional)*: file_name parameter (default: `None`)
- `generate_metadata` (Optional[bool]) *(optional)*: generate_metadata parameter (default: `None`)
- `metadata_file_name` (Optional[str]) *(optional)*: metadata_file_name parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DownloadSolution`

**Response Structure:** 
- `files`: Optional[list[str]]
- `SolutionId`: Optional[str]
- `IsDownloadSuccessful`: Optional[bool]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"
output_directory = r"c:\output"
solution_type = "Standard"
overwrite = True
file_name = "output.txt"
generate_metadata = True
metadata_file_name = "metadata.json"

solution_download_solution_resp: list[CommandResponse[Contracts_DownloadSolution]] = pxc.solution.download_solution(
    solution_id=solution_id,
    output_directory=output_directory,
    solution_type=solution_type,
    overwrite=overwrite,
    file_name=file_name,
    generate_metadata=generate_metadata,
    metadata_file_name=metadata_file_name,
    print_message=True
)
solution_download_solution_final: Contracts_DownloadSolution = SDKBase.get_response_data(solution_download_solution_resp)

if solution_download_solution_final is not None:
    if solution_download_solution_final.files is not None:
        for item in solution_download_solution_final.files:
            print(f"Item: {item}")
    else:
        print(f"No files returned")
    print(f"SolutionId: {solution_download_solution_final.SolutionId}")
    print(f"IsDownloadSuccessful: {solution_download_solution_final.IsDownloadSuccessful}")
else:
    print(f"download_solution failed: {solution_download_solution_resp.Message}")
```

---

### solution.list_solution_files

List files available in a solution

**Signature:** `list_solution_files(solution_id: str, solution_type: Optional[str], include_archive_entries: Optional[bool], print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `solution_type` (Optional[str]) *(optional)*: solution_type parameter (default: `None`)
- `include_archive_entries` (Optional[bool]) *(optional)*: include_archive_entries parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSolutionFile`

**Response Structure:** 
- `ConsoleSolutionTypeFileLists`: Optional[list[Solution_ConsoleSolutionTypeFileList]]
  - `SolutionType`: Optional[str]
  - `Files`: Optional[list[Solution_FileMetaData]]
    - `FileName`: Optional[str]
    - `FileSizeBytes`: Optional[int]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"
solution_type = "Standard"
include_archive_entries = True

solution_list_solution_files_resp: list[CommandResponse[Contracts_ListSolutionFile]] = pxc.solution.list_solution_files(solution_id=solution_id, solution_type=solution_type, include_archive_entries=include_archive_entries, print_message=True)
solution_list_solution_files_final: Contracts_ListSolutionFile = SDKBase.get_response_data(solution_list_solution_files_resp)

if solution_list_solution_files_final is not None:
    if solution_list_solution_files_final.ConsoleSolutionTypeFileLists is not None:
        for item in solution_list_solution_files_final.ConsoleSolutionTypeFileLists:
            print(f"SolutionType: {item.SolutionType}")
            print(f"Files: {item.Files}")
    else:
        print(f"No ConsoleSolutionTypeFileLists returned")
else:
    print(f"list_solution_files failed: {solution_list_solution_files_resp.Message}")
```

---

### solution.list_solution_file_types

List available file types for a solution

**Signature:** `list_solution_file_types(solution_id: str, print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListSolutionFileTypes`

**Response Structure:** 
- `FileTypes`: Optional[list[str]]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_list_solution_file_types_resp: list[CommandResponse[Contracts_ListSolutionFileTypes]] = pxc.solution.list_solution_file_types(solution_id=solution_id, print_message=True)
solution_list_solution_file_types_final: Contracts_ListSolutionFileTypes = SDKBase.get_response_data(solution_list_solution_file_types_resp)

if solution_list_solution_file_types_final is not None:
    if solution_list_solution_file_types_final.FileTypes is not None:
        for item in solution_list_solution_file_types_final.FileTypes:
            print(f"Item: {item}")
    else:
        print(f"No FileTypes returned")
else:
    print(f"list_solution_file_types failed: {solution_list_solution_file_types_resp.Message}")
```

---

### solution.convert_hybrid_to_parquet

Convert hybrid solution format to Parquet

**Signature:** `convert_hybrid_to_parquet(sql_lite_path: str, parquet_directory: str, output_directory: str, print_message: bool)`

**Parameters:**
- `sql_lite_path` (str) *(required)*: sql_lite_path parameter
- `parquet_directory` (str) *(required)*: parquet_directory parameter
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ConvertHybridToParquetResponse`

**Response Structure:** 
- `Response`: Optional[int]

**Example:**
```python
sql_lite_path = r"c:\path\to\data.db"
parquet_directory = r"c:\path\to\parquet"
output_directory = r"c:\output"

solution_convert_hybrid_to_parquet_resp: list[CommandResponse[Contracts_ConvertHybridToParquetResponse]] = pxc.solution.convert_hybrid_to_parquet(sql_lite_path=sql_lite_path, parquet_directory=parquet_directory, output_directory=output_directory, print_message=True)
solution_convert_hybrid_to_parquet_final: Contracts_ConvertHybridToParquetResponse = SDKBase.get_response_data(solution_convert_hybrid_to_parquet_resp)

if solution_convert_hybrid_to_parquet_final is not None:
    print(f"Response: {solution_convert_hybrid_to_parquet_final.Response}")
else:
    print(f"convert_hybrid_to_parquet failed: {solution_convert_hybrid_to_parquet_resp.Message}")
```

---

### solution.convert_raw_zip_to_hybrid

Convert raw ZIP solution to hybrid format

**Signature:** `convert_raw_zip_to_hybrid(zip_path: str, output_directory: str, schema_version: Optional[int], print_message: bool)`

**Parameters:**
- `zip_path` (str) *(required)*: zip_path parameter
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `schema_version` (Optional[int]) *(optional)*: schema_version parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ConvertRawZipToHybridResponse`

**Response Structure:** 
- `Response`: Optional[int]

**Example:**
```python
zip_path = r"c:\path\to\data.zip"
output_directory = r"c:\output"
schema_version = 1

solution_convert_raw_zip_to_hybrid_resp: list[CommandResponse[Contracts_ConvertRawZipToHybridResponse]] = pxc.solution.convert_raw_zip_to_hybrid(zip_path=zip_path, output_directory=output_directory, schema_version=schema_version, print_message=True)
solution_convert_raw_zip_to_hybrid_final: Contracts_ConvertRawZipToHybridResponse = SDKBase.get_response_data(solution_convert_raw_zip_to_hybrid_resp)

if solution_convert_raw_zip_to_hybrid_final is not None:
    print(f"Response: {solution_convert_raw_zip_to_hybrid_final.Response}")
else:
    print(f"convert_raw_zip_to_hybrid failed: {solution_convert_raw_zip_to_hybrid_resp.Message}")
```

---

### solution.convert_raw_zip_to_parquet

Convert raw ZIP solution to Parquet format

**Signature:** `convert_raw_zip_to_parquet(zip_path: str, output_directory: str, parquet_schema_version: Optional[int], print_message: bool)`

**Parameters:**
- `zip_path` (str) *(required)*: zip_path parameter
- `output_directory` (str) *(required)*: Local directory to save downloaded files
- `parquet_schema_version` (Optional[int]) *(optional)*: parquet_schema_version parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ConvertRawZipToParquetResponse`

**Response Structure:** 
- `Response`: Optional[int]

**Example:**
```python
zip_path = r"c:\path\to\data.zip"
output_directory = r"c:\output"
parquet_schema_version = 1

solution_convert_raw_zip_to_parquet_resp: list[CommandResponse[Contracts_ConvertRawZipToParquetResponse]] = pxc.solution.convert_raw_zip_to_parquet(zip_path=zip_path, output_directory=output_directory, parquet_schema_version=parquet_schema_version, print_message=True)
solution_convert_raw_zip_to_parquet_final: Contracts_ConvertRawZipToParquetResponse = SDKBase.get_response_data(solution_convert_raw_zip_to_parquet_resp)

if solution_convert_raw_zip_to_parquet_final is not None:
    print(f"Response: {solution_convert_raw_zip_to_parquet_final.Response}")
else:
    print(f"convert_raw_zip_to_parquet failed: {solution_convert_raw_zip_to_parquet_resp.Message}")
```

---

### solution.bi_status

Get the current status of a BI solution publication

**Signature:** `bi_status(solution_id: str, print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_BiSolutionResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `Status`: Optional[str]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_bi_status_resp: list[CommandResponse[Contracts_BiSolutionResponse]] = pxc.solution.bi_status(solution_id=solution_id, print_message=True)
solution_bi_status_final: Contracts_BiSolutionResponse = SDKBase.get_response_data(solution_bi_status_resp)

if solution_bi_status_final is not None:
    print(f"SolutionId: {solution_bi_status_final.SolutionId}")
    print(f"Status: {solution_bi_status_final.Status}")
else:
    print(f"bi_status failed: {solution_bi_status_resp.Message}")
```

---

### solution.delete_bi

Delete (unpublish) a solution from BI Analytics

**Signature:** `delete_bi(solution_id: str, print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_BiSolutionResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `Status`: Optional[str]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_delete_bi_resp: list[CommandResponse[Contracts_BiSolutionResponse]] = pxc.solution.delete_bi(solution_id=solution_id, print_message=True)
solution_delete_bi_final: Contracts_BiSolutionResponse = SDKBase.get_response_data(solution_delete_bi_resp)

if solution_delete_bi_final is not None:
    print(f"SolutionId: {solution_delete_bi_final.SolutionId}")
    print(f"Status: {solution_delete_bi_final.Status}")
else:
    print(f"delete_bi failed: {solution_delete_bi_resp.Message}")
```

---

### solution.list_bi_solution

List all BI solutions published to BI Analytics with optional filtering by study

**Signature:** `list_bi_solution(study_id: Optional[str], print_message: bool)`

**Parameters:**
- `study_id` (Optional[str]) *(optional)*: Unique identifier for a specific study (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_BiSolutionList`

**Response Structure:** 
- `Solutions`: Optional[list[Contracts_BiSolution]]
  - `SolutionId`: Optional[str]
  - `ModelName`: Optional[str]
  - `StudyName`: Optional[str]
  - `StudyId`: Optional[str]
  - `ChangesetId`: Optional[str]
  - `PublishedAt`: Optional[str]
  - `PublishedBy`: Optional[str]
  - `Type`: Optional[str]
  - `TypeVersion`: Optional[int]
  - `CreatedAt`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

solution_list_bi_solution_resp: list[CommandResponse[Contracts_BiSolutionList]] = pxc.solution.list_bi_solution(study_id=study_id, print_message=True)
solution_list_bi_solution_final: Contracts_BiSolutionList = SDKBase.get_response_data(solution_list_bi_solution_resp)

if solution_list_bi_solution_final is not None:
    if solution_list_bi_solution_final.Solutions is not None:
        for item in solution_list_bi_solution_final.Solutions:
            print(f"SolutionId: {item.SolutionId}")
            print(f"ModelName: {item.ModelName}")
            print(f"StudyName: {item.StudyName}")
            print(f"StudyId: {item.StudyId}")
            # ... and 6 more properties
    else:
        print(f"No Solutions returned")
else:
    print(f"list_bi_solution failed: {solution_list_bi_solution_resp.Message}")
```

---

### solution.publish_bi

Publish a solution to BI Analytics for visualization and reporting

**Signature:** `publish_bi(solution_id: str, print_message: bool)`

**Parameters:**
- `solution_id` (str) *(required)*: Unique identifier for a specific solution (use ModelIdentifier.Id from simulation results)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_BiSolutionResponse`

**Response Structure:** 
- `SolutionId`: Optional[str]
- `Status`: Optional[str]

**Example:**
```python
solution_id = "550e8400-e29b-41d4-a716-446655440000"

solution_publish_bi_resp: list[CommandResponse[Contracts_BiSolutionResponse]] = pxc.solution.publish_bi(solution_id=solution_id, print_message=True)
solution_publish_bi_final: Contracts_BiSolutionResponse = SDKBase.get_response_data(solution_publish_bi_resp)

if solution_publish_bi_final is not None:
    print(f"SolutionId: {solution_publish_bi_final.SolutionId}")
    print(f"Status: {solution_publish_bi_final.Status}")
else:
    print(f"publish_bi failed: {solution_publish_bi_resp.Message}")
```

---

## Study

### study.change_study_owner

Transfer ownership of a study to another user (requires administrator privileges).

**Signature:** `change_study_owner(study_id: str, user_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `user_id` (str) *(required)*: user_id parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ChangeStudyOwnerResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `NewOwnerEmail`: Optional[str]
- `NewOwnerName`: Optional[str]
- `Success`: Optional[bool]
- `Message`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
user_id = "user id"

study_change_study_owner_resp: list[CommandResponse[Contracts_ChangeStudyOwnerResponse]] = pxc.study.change_study_owner(study_id=study_id, user_id=user_id, print_message=True)
study_change_study_owner_final: Contracts_ChangeStudyOwnerResponse = SDKBase.get_response_data(study_change_study_owner_resp)

if study_change_study_owner_final is not None:
    print(f"StudyId: {study_change_study_owner_final.StudyId}")
    print(f"NewOwnerEmail: {study_change_study_owner_final.NewOwnerEmail}")
    print(f"NewOwnerName: {study_change_study_owner_final.NewOwnerName}")
    print(f"Success: {study_change_study_owner_final.Success}")
    print(f"Message: {study_change_study_owner_final.Message}")
else:
    print(f"change_study_owner failed: {study_change_study_owner_resp.Message}")
```

---

### study.clone_study

Clone an existing study

**Signature:** `clone_study(study_id: str, output_directory_path: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `output_directory_path` (str) *(required)*: output_directory_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_CloneStudyResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `OutputPath`: Optional[str]
- `StudyName`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
output_directory_path = r"c:\output"

study_clone_study_resp: list[CommandResponse[Contracts_CloneStudyResponse]] = pxc.study.clone_study(study_id=study_id, output_directory_path=output_directory_path, print_message=True)
study_clone_study_final: Contracts_CloneStudyResponse = SDKBase.get_response_data(study_clone_study_resp)

if study_clone_study_final is not None:
    print(f"StudyId: {study_clone_study_final.StudyId}")
    print(f"OutputPath: {study_clone_study_final.OutputPath}")
    print(f"StudyName: {study_clone_study_final.StudyName}")
else:
    print(f"clone_study failed: {study_clone_study_resp.Message}")
```

---

### study.create_study

Create a new study

**Signature:** `create_study(study_name: str, study_description: str, study_db_path: str, print_message: bool)`

**Parameters:**
- `study_name` (str) *(required)*: study_name parameter
- `study_description` (str) *(required)*: study_description parameter
- `study_db_path` (str) *(required)*: study_db_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_StudyCommandResponse`

**Response Structure:** 
- `StudyId`: Optional[str]

**Example:**
```python
study_name = "My Study"
study_description = "Study description"
study_db_path = r"c:\path\to\study.db"

study_create_study_resp: list[CommandResponse[Contracts_StudyCommandResponse]] = pxc.study.create_study(study_name=study_name, study_description=study_description, study_db_path=study_db_path, print_message=True)
study_create_study_final: Contracts_StudyCommandResponse = SDKBase.get_response_data(study_create_study_resp)

if study_create_study_final is not None:
    print(f"StudyId: {study_create_study_final.StudyId}")
else:
    print(f"create_study failed: {study_create_study_resp.Message}")
```

---

### study.delete_local_study

Delete a study from local storage

**Signature:** `delete_local_study(study_id: str, full_delete: Optional[bool], print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `full_delete` (Optional[bool]) *(optional)*: full_delete parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_StudyCommandResponse`

**Response Structure:** 
- `StudyId`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
full_delete = True

study_delete_local_study_resp: list[CommandResponse[Contracts_StudyCommandResponse]] = pxc.study.delete_local_study(study_id=study_id, full_delete=full_delete, print_message=True)
study_delete_local_study_final: Contracts_StudyCommandResponse = SDKBase.get_response_data(study_delete_local_study_resp)

if study_delete_local_study_final is not None:
    print(f"StudyId: {study_delete_local_study_final.StudyId}")
else:
    print(f"delete_local_study failed: {study_delete_local_study_resp.Message}")
```

---

### study.delete_study

Delete a study

**Signature:** `delete_study(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_StudyCommandResponse`

**Response Structure:** 
- `StudyId`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_delete_study_resp: list[CommandResponse[Contracts_StudyCommandResponse]] = pxc.study.delete_study(study_id=study_id, print_message=True)
study_delete_study_final: Contracts_StudyCommandResponse = SDKBase.get_response_data(study_delete_study_resp)

if study_delete_study_final is not None:
    print(f"StudyId: {study_delete_study_final.StudyId}")
else:
    print(f"delete_study failed: {study_delete_study_resp.Message}")
```

---

### study.find_study

Find a study by name

**Signature:** `find_study(study_name: str, print_message: bool)`

**Parameters:**
- `study_name` (str) *(required)*: study_name parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListStudiesResponse`

**Response Structure:** 
- `Studies`: Optional[list[Contracts_Study]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `Status`: Optional[str]
  - `LastUpdateMessage`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `StudyType`: Optional[str]
  - `isAccessibleToRequestingUser`: Optional[bool]
  - `createdByUserId`: Optional[str]
  - `OwnerUserId`: Optional[str]
  - `User`: Optional[Contracts_User]
    - `Name`: Optional[str]
    - `EmailAddress`: Optional[str]
    - `Id`: Optional[str]

**Example:**
```python
study_name = "My Study"

study_find_study_resp: list[CommandResponse[Contracts_ListStudiesResponse]] = pxc.study.find_study(study_name=study_name, print_message=True)
study_find_study_final: Contracts_ListStudiesResponse = SDKBase.get_response_data(study_find_study_resp)

if study_find_study_final is not None:
    if study_find_study_final.Studies is not None:
        for item in study_find_study_final.Studies:
            print(f"Id: {item.Id.Value}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"Status: {item.Status}")
            # ... and 8 more properties
    else:
        print(f"No Studies returned")
else:
    print(f"find_study failed: {study_find_study_resp.Message}")
```

---

### study.grant_user_access

Grant users access to a study by their email addresses

**Signature:** `grant_user_access(study_id: str, user_emails: list[str], print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `user_emails` (list[str]) *(required)*: user_emails parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GrantUserAccessResponse`

**Response Structure:** 
- `Users`: Optional[list[str]]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
user_emails = ["user@example.com", "admin@example.com"]

study_grant_user_access_resp: list[CommandResponse[Contracts_GrantUserAccessResponse]] = pxc.study.grant_user_access(study_id=study_id, user_emails=user_emails, print_message=True)
study_grant_user_access_final: Contracts_GrantUserAccessResponse = SDKBase.get_response_data(study_grant_user_access_resp)

if study_grant_user_access_final is not None:
    if study_grant_user_access_final.Users is not None:
        for item in study_grant_user_access_final.Users:
            print(f"Item: {item}")
    else:
        print(f"No Users returned")
else:
    print(f"grant_user_access failed: {study_grant_user_access_resp.Message}")
```

---

### study.list_local_studies

List studies available in local storage

**Signature:** `list_local_studies(print_message: bool)`

**Parameters:**
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListLocalStudiesResponse`

**Response Structure:** 
- `StudyRecords`: Optional[list[Contracts_LocalStudyRecordResponse]]
  - `StudyId`: Optional[str]
  - `StudyXmlPath`: Optional[str]

**Example:**
```python
study_list_local_studies_resp: list[CommandResponse[Contracts_ListLocalStudiesResponse]] = pxc.study.list_local_studies(print_message=True)
study_list_local_studies_final: Contracts_ListLocalStudiesResponse = SDKBase.get_response_data(study_list_local_studies_resp)

if study_list_local_studies_final is not None:
    if study_list_local_studies_final.StudyRecords is not None:
        for item in study_list_local_studies_final.StudyRecords:
            print(f"StudyId: {item.StudyId}")
            print(f"StudyXmlPath: {item.StudyXmlPath}")
    else:
        print(f"No StudyRecords returned")
else:
    print(f"list_local_studies failed: {study_list_local_studies_resp.Message}")
```

---

### study.list_studies

List available studies

**Signature:** `list_studies(order_by: Optional[str], descending: Optional[bool], top: Optional[int], skip: Optional[int], study_type: Optional[str], raw: Optional[str], filter_by_user_id: Optional[bool], print_message: bool)`

**Parameters:**
- `order_by` (Optional[str]) *(optional)*: Field to order results by (default: `None`)
- `descending` (Optional[bool]) *(optional)*: Order results in descending order (default: `None`)
- `top` (Optional[int]) *(optional)*: Maximum number of results to return (default: `None`)
- `skip` (Optional[int]) *(optional)*: Number of results to skip (default: `None`)
- `study_type` (Optional[str]) *(optional)*: study_type parameter (default: `None`)
- `raw` (Optional[str]) *(optional)*: Raw OData query string for advanced queries (default: `None`)
- `filter_by_user_id` (Optional[bool]) *(optional)*: filter_by_user_id parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListStudiesResponse`

**Response Structure:** 
- `Studies`: Optional[list[Contracts_Study]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `Name`: Optional[str]
  - `Description`: Optional[str]
  - `Status`: Optional[str]
  - `LastUpdateMessage`: Optional[str]
  - `CreatedDate`: Optional[str]
  - `LastUpdatedAtUtc`: Optional[str]
  - `StudyType`: Optional[str]
  - `isAccessibleToRequestingUser`: Optional[bool]
  - `createdByUserId`: Optional[str]
  - `OwnerUserId`: Optional[str]
  - `User`: Optional[Contracts_User]
    - `Name`: Optional[str]
    - `EmailAddress`: Optional[str]
    - `Id`: Optional[str]

**Example:**
```python
order_by = "CreatedAt"
descending = True
top = 10
skip = 0
study_type = "Standard"
raw = "filter expression"
filter_by_user_id = True

study_list_studies_resp: list[CommandResponse[Contracts_ListStudiesResponse]] = pxc.study.list_studies(
    order_by=order_by,
    descending=descending,
    top=top,
    skip=skip,
    study_type=study_type,
    raw=raw,
    filter_by_user_id=filter_by_user_id,
    print_message=True
)
study_list_studies_final: Contracts_ListStudiesResponse = SDKBase.get_response_data(study_list_studies_resp)

if study_list_studies_final is not None:
    if study_list_studies_final.Studies is not None:
        for item in study_list_studies_final.Studies:
            print(f"Id: {item.Id.Value}")
            print(f"Name: {item.Name}")
            print(f"Description: {item.Description}")
            print(f"Status: {item.Status}")
            # ... and 8 more properties
    else:
        print(f"No Studies returned")
else:
    print(f"list_studies failed: {study_list_studies_resp.Message}")
```

---

### study.list_study_ids_for_folder

Get study IDs for all studies in a directory

**Signature:** `list_study_ids_for_folder(study_directory_path: str, print_message: bool)`

**Parameters:**
- `study_directory_path` (str) *(required)*: study_directory_path parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListStudyIdsForFolderResponse`

**Response Structure:** 
- `StudyIds`: Optional[list[str]]

**Example:**
```python
study_directory_path = r"c:\path\to\study"

study_list_study_ids_for_folder_resp: list[CommandResponse[Contracts_ListStudyIdsForFolderResponse]] = pxc.study.list_study_ids_for_folder(study_directory_path=study_directory_path, print_message=True)
study_list_study_ids_for_folder_final: Contracts_ListStudyIdsForFolderResponse = SDKBase.get_response_data(study_list_study_ids_for_folder_resp)

if study_list_study_ids_for_folder_final is not None:
    if study_list_study_ids_for_folder_final.StudyIds is not None:
        for item in study_list_study_ids_for_folder_final.StudyIds:
            print(f"Item: {item}")
    else:
        print(f"No StudyIds returned")
else:
    print(f"list_study_ids_for_folder failed: {study_list_study_ids_for_folder_resp.Message}")
```

---

### study.study_upgrade

Upgrade/downgrade study database to the target engine version

**Signature:** `study_upgrade(study_id: str, target_engine_version: str, commit_as_changeset: Optional[bool], print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `target_engine_version` (str) *(required)*: target_engine_version parameter
- `commit_as_changeset` (Optional[bool]) *(optional)*: commit_as_changeset parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_UpgradeStudyResponse`

**Response Structure:** 
- `Success`: Optional[bool]
- `Message`: Optional[str]
- `NewChangesetId`: Optional[str]
- `ErrorMessage`: Optional[str]
- `UpgradedSqliteStream`: Optional[IO_Stream]
  - `CanRead`: Optional[bool]
  - `CanWrite`: Optional[bool]
  - `CanSeek`: Optional[bool]
  - `CanTimeout`: Optional[bool]
  - `Length`: Optional[int]
  - `Position`: Optional[int]
  - `ReadTimeout`: Optional[int]
  - `WriteTimeout`: Optional[int]
- `FileName`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
target_engine_version = "target engine version"
commit_as_changeset = "value"

study_study_upgrade_resp: list[CommandResponse[Contracts_UpgradeStudyResponse]] = pxc.study.study_upgrade(study_id=study_id, target_engine_version=target_engine_version, commit_as_changeset=commit_as_changeset, print_message=True)
study_study_upgrade_final: Contracts_UpgradeStudyResponse = SDKBase.get_response_data(study_study_upgrade_resp)

if study_study_upgrade_final is not None:
    print(f"Success: {study_study_upgrade_final.Success}")
    print(f"Message: {study_study_upgrade_final.Message}")
    print(f"NewChangesetId: {study_study_upgrade_final.NewChangesetId}")
    print(f"ErrorMessage: {study_study_upgrade_final.ErrorMessage}")
    print(f"UpgradedSqliteStream: {study_study_upgrade_final.UpgradedSqliteStream}")
    print(f"FileName: {study_study_upgrade_final.FileName}")
else:
    print(f"study_upgrade failed: {study_study_upgrade_resp.Message}")
```

---

### study.list_settings

List all settings for a study

**Signature:** `list_settings(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListStudySettingsResponse`

**Response Structure:** 
- `StudySettings`: Optional[list[Contracts_StudySetting]]
  - `Name`: Optional[str]
  - `Id`: Optional[str]
  - `Status`: Optional[str]
  - `Type`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_list_settings_resp: list[CommandResponse[Contracts_ListStudySettingsResponse]] = pxc.study.list_settings(study_id=study_id, print_message=True)
study_list_settings_final: Contracts_ListStudySettingsResponse = SDKBase.get_response_data(study_list_settings_resp)

if study_list_settings_final is not None:
    if study_list_settings_final.StudySettings is not None:
        for item in study_list_settings_final.StudySettings:
            print(f"Name: {item.Name}")
            print(f"Id: {item.Id}")
            print(f"Status: {item.Status}")
            print(f"Type: {item.Type}")
    else:
        print(f"No StudySettings returned")
else:
    print(f"list_settings failed: {study_list_settings_resp.Message}")
```

---

### study.download_specific_changeset

Download a specific changeset for a study

**Signature:** `download_specific_changeset(study_id: str, changeset_id: str, output_directory_path: str, list_files: Optional[bool], print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `changeset_id` (str) *(required)*: Unique identifier for a specific changeset
- `output_directory_path` (str) *(required)*: output_directory_path parameter
- `list_files` (Optional[bool]) *(optional)*: list_files parameter (default: `None`)
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_DownloadSpecificChangesetResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `ChangesetId`: Optional[str]
- `DownloadedFilePaths`: Optional[list[Contracts_StudyFile]]
  - `FilePath`: Optional[str]
  - `DataType`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
changeset_id = None
output_directory_path = r"c:\output"
list_files = True

study_download_specific_changeset_resp: list[CommandResponse[Contracts_DownloadSpecificChangesetResponse]] = pxc.study.download_specific_changeset(
    study_id=study_id,
    changeset_id=changeset_id,
    output_directory_path=output_directory_path,
    list_files=list_files,
    print_message=True
)
study_download_specific_changeset_final: Contracts_DownloadSpecificChangesetResponse = SDKBase.get_response_data(study_download_specific_changeset_resp)

if study_download_specific_changeset_final is not None:
    print(f"StudyId: {study_download_specific_changeset_final.StudyId}")
    print(f"ChangesetId: {study_download_specific_changeset_final.ChangesetId}")
    if study_download_specific_changeset_final.DownloadedFilePaths is not None:
        for item in study_download_specific_changeset_final.DownloadedFilePaths:
            print(f"FilePath: {item.FilePath}")
            print(f"DataType: {item.DataType}")
    else:
        print(f"No DownloadedFilePaths returned")
else:
    print(f"download_specific_changeset failed: {study_download_specific_changeset_resp.Message}")
```

---

### study.get_changeset_sync_status

Check if study changesets are in sync with server

**Signature:** `get_changeset_sync_status(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetChangesetSyncStatusResponse`

**Response Structure:** 
- `Status`: Optional[Contracts_ChangesetSyncStatus]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_get_changeset_sync_status_resp: list[CommandResponse[Contracts_GetChangesetSyncStatusResponse]] = pxc.study.get_changeset_sync_status(study_id=study_id, print_message=True)
study_get_changeset_sync_status_final: Contracts_GetChangesetSyncStatusResponse = SDKBase.get_response_data(study_get_changeset_sync_status_resp)

if study_get_changeset_sync_status_final is not None:
    print(f"Status: {study_get_changeset_sync_status_final.Status}")
else:
    print(f"get_changeset_sync_status failed: {study_get_changeset_sync_status_resp.Message}")
```

---

### study.get_last_changeset_id

Get ID of the most recent changeset

**Signature:** `get_last_changeset_id(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetLastChangesetIdResponse`

**Response Structure:** 
- `ChangesetId`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_get_last_changeset_id_resp: list[CommandResponse[Contracts_GetLastChangesetIdResponse]] = pxc.study.get_last_changeset_id(study_id=study_id, print_message=True)
study_get_last_changeset_id_final: Contracts_GetLastChangesetIdResponse = SDKBase.get_response_data(study_get_last_changeset_id_resp)

if study_get_last_changeset_id_final is not None:
    print(f"ChangesetId: {study_get_last_changeset_id_final.ChangesetId}")
else:
    print(f"get_last_changeset_id failed: {study_get_last_changeset_id_resp.Message}")
```

---

### study.get_last_local_changeset_id

Get ID of the most recent local changeset

**Signature:** `get_last_local_changeset_id(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetLastChangesetIdResponse`

**Response Structure:** 
- `ChangesetId`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_get_last_local_changeset_id_resp: list[CommandResponse[Contracts_GetLastChangesetIdResponse]] = pxc.study.get_last_local_changeset_id(study_id=study_id, print_message=True)
study_get_last_local_changeset_id_final: Contracts_GetLastChangesetIdResponse = SDKBase.get_response_data(study_get_last_local_changeset_id_resp)

if study_get_last_local_changeset_id_final is not None:
    print(f"ChangesetId: {study_get_last_local_changeset_id_final.ChangesetId}")
else:
    print(f"get_last_local_changeset_id failed: {study_get_last_local_changeset_id_resp.Message}")
```

---

### study.get_studies_download_urls

Gets SimulationData by study_id and changeset_id required for SimulationData in json and enqueue

**Signature:** `get_studies_download_urls(study_id: str, changeset_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `changeset_id` (str) *(required)*: Unique identifier for a specific changeset
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_GetStudiesDownloadUrlsResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `ChangesetId`: Optional[str]
- `SimulationDataUrls`: Optional[list[Contracts_SimulationDataUrl]]
  - `Uri`: Optional[str]
  - `Type`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
changeset_id = None

study_get_studies_download_urls_resp: list[CommandResponse[Contracts_GetStudiesDownloadUrlsResponse]] = pxc.study.get_studies_download_urls(study_id=study_id, changeset_id=changeset_id, print_message=True)
study_get_studies_download_urls_final: Contracts_GetStudiesDownloadUrlsResponse = SDKBase.get_response_data(study_get_studies_download_urls_resp)

if study_get_studies_download_urls_final is not None:
    print(f"StudyId: {study_get_studies_download_urls_final.StudyId}")
    print(f"ChangesetId: {study_get_studies_download_urls_final.ChangesetId}")
    if study_get_studies_download_urls_final.SimulationDataUrls is not None:
        for item in study_get_studies_download_urls_final.SimulationDataUrls:
            print(f"Uri: {item.Uri}")
            print(f"Type: {item.Type}")
    else:
        print(f"No SimulationDataUrls returned")
else:
    print(f"get_studies_download_urls failed: {study_get_studies_download_urls_resp.Message}")
```

---

### study.list_changesets

List all changesets for a study

**Signature:** `list_changesets(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListChangesetsResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `Changesets`: Optional[list[Contracts_Changeset]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `CommitMessage`: Optional[str]
  - `LastUpdateMessage`: Optional[str]
  - `CreatedByUserId`: Optional[StringValue] → Access via `.Value` property
  - `CreatedDate`: Optional[str]
  - `UpdatedDate`: Optional[str]
  - `Status`: Optional[str]
  - `CreatedByUserName`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_list_changesets_resp: list[CommandResponse[Contracts_ListChangesetsResponse]] = pxc.study.list_changesets(study_id=study_id, print_message=True)
study_list_changesets_final: Contracts_ListChangesetsResponse = SDKBase.get_response_data(study_list_changesets_resp)

if study_list_changesets_final is not None:
    print(f"StudyId: {study_list_changesets_final.StudyId}")
    if study_list_changesets_final.Changesets is not None:
        for item in study_list_changesets_final.Changesets:
            print(f"Id: {item.Id.Value}")
            print(f"CommitMessage: {item.CommitMessage}")
            print(f"LastUpdateMessage: {item.LastUpdateMessage}")
            print(f"CreatedByUserId: {item.CreatedByUserId.Value}")
            # ... and 4 more properties
    else:
        print(f"No Changesets returned")
else:
    print(f"list_changesets failed: {study_list_changesets_resp.Message}")
```

---

### study.list_local_changesets

List all local changesets for a study

**Signature:** `list_local_changesets(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_ListChangesetsResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `Changesets`: Optional[list[Contracts_Changeset]]
  - `Id`: Optional[GuidValue] → Access via `.Value` property
  - `CommitMessage`: Optional[str]
  - `LastUpdateMessage`: Optional[str]
  - `CreatedByUserId`: Optional[StringValue] → Access via `.Value` property
  - `CreatedDate`: Optional[str]
  - `UpdatedDate`: Optional[str]
  - `Status`: Optional[str]
  - `CreatedByUserName`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_list_local_changesets_resp: list[CommandResponse[Contracts_ListChangesetsResponse]] = pxc.study.list_local_changesets(study_id=study_id, print_message=True)
study_list_local_changesets_final: Contracts_ListChangesetsResponse = SDKBase.get_response_data(study_list_local_changesets_resp)

if study_list_local_changesets_final is not None:
    print(f"StudyId: {study_list_local_changesets_final.StudyId}")
    if study_list_local_changesets_final.Changesets is not None:
        for item in study_list_local_changesets_final.Changesets:
            print(f"Id: {item.Id.Value}")
            print(f"CommitMessage: {item.CommitMessage}")
            print(f"LastUpdateMessage: {item.LastUpdateMessage}")
            print(f"CreatedByUserId: {item.CreatedByUserId.Value}")
            # ... and 4 more properties
    else:
        print(f"No Changesets returned")
else:
    print(f"list_local_changesets failed: {study_list_local_changesets_resp.Message}")
```

---

### study.pull_latest

Pull latest changes from server

**Signature:** `pull_latest(study_id: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PullLatestResponse`

**Response Structure:** None


**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"

study_pull_latest_resp: list[CommandResponse[Contracts_PullLatestResponse]] = pxc.study.pull_latest(study_id=study_id, print_message=True)
study_pull_latest_final: Contracts_PullLatestResponse = SDKBase.get_response_data(study_pull_latest_resp)

if study_pull_latest_final is not None:
    print(study_pull_latest_final)
else:
    print(f"pull_latest failed: {study_pull_latest_resp.Message}")
```

---

### study.push_changeset

Push local changes to server

**Signature:** `push_changeset(study_id: str, commit_message: str, print_message: bool)`

**Parameters:**
- `study_id` (str) *(required)*: Unique identifier for a specific study
- `commit_message` (str) *(required)*: commit_message parameter
- `print_message` (bool) *(optional)*: Enable verbose SDK logs for troubleshooting (default: `False`)

**Returns:** `Contracts_PushChangesetResponse`

**Response Structure:** 
- `StudyId`: Optional[str]
- `ChangesetId`: Optional[str]
- `CloudStudyName`: Optional[str]

**Example:**
```python
study_id = "550e8400-e29b-41d4-a716-446655440000"
commit_message = "Updated study configuration"

study_push_changeset_resp: list[CommandResponse[Contracts_PushChangesetResponse]] = pxc.study.push_changeset(study_id=study_id, commit_message=commit_message, print_message=True)
study_push_changeset_final: Contracts_PushChangesetResponse = SDKBase.get_response_data(study_push_changeset_resp)

if study_push_changeset_final is not None:
    print(f"StudyId: {study_push_changeset_final.StudyId}")
    print(f"ChangesetId: {study_push_changeset_final.ChangesetId}")
    print(f"CloudStudyName: {study_push_changeset_final.CloudStudyName}")
else:
    print(f"push_changeset failed: {study_push_changeset_resp.Message}")
```

---

## Important Notes

### Response Handling Pattern
All CloudSDK functions follow this type-safe response pattern:

```python
function_resp: list[CommandResponse[ContractType]] = pxc.domain.function_name(parameters)
function_final: ContractType = SDKBase.get_response_data(function_resp)

if function_final is not None:
    print(f"Property: {function_final.property_name}")
else:
    print(f"function_name failed: {function_resp.Message}")
```

### List Property Handling
When response properties contain lists, always check for null and iterate properly:

```python
if response_final is not None:
    if response_final.list_property is not None:
        for item in response_final.list_property:
            print(f"Item Property: {item.PropertyName}")
            print(f"Item Value: {item.PropertyValue}")
    else:
        print("No items returned in list")
```

### GuidValue and StringValue Types
These wrapper types require accessing the `.Value` property:

```python
simulation_id: str = simulation.Id.Value
user_id: str = changeset.CreatedByUserId.Value
```

### Error Handling Best Practices
Always implement proper error handling with null checks:

```python
function_resp: list[CommandResponse[ContractType]] = pxc.domain.function_name()
function_final: ContractType = SDKBase.get_response_data(function_resp)

if function_final is not None:
    if hasattr(function_final, 'list_property') and function_final.list_property is not None:
        for item in function_final.list_property:
            pass
    else:
        print("No data returned")
else:
    print(f"Operation failed: {function_resp.Message}")
```
