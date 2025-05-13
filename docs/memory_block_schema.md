# Memory Block Schema Documentation

## ExecutableMetadata Mixin

The `ExecutableMetadata` mixin is a component of the Memory Block schema system that enhances metadata models for executable work items like Tasks, Bugs, Projects, and Epics. This mixin adds fields to support AI agent execution and validation, following a structured lifecycle from planning to completion.

### Field Categories

The mixin organizes fields into three distinct categories:

#### Planning Fields (Pre-Execution)

Fields that define what must be done:

- `tool_hints`: List of suggested tools to use for executing the item
- `action_items`: Specific actions needed to complete the item
- `acceptance_criteria`: Criteria that must be met for the item to be considered complete
- `expected_artifacts`: Expected deliverables or artifacts to be produced
- `blocked_by`: IDs of items that must be completed before this one can start
- `priority_score`: Numeric priority score (higher = more important)
- `reviewer`: ID of user or agent responsible for reviewing this item

#### Agent Framework Compatibility Fields

Fields that support integration with AI agent orchestration frameworks:

- `execution_timeout_minutes`: Maximum time allowed for execution in minutes
- `cost_budget_usd`: Maximum budget allowed for execution in USD
- `role_hint`: Suggested agent role (e.g., 'developer', 'researcher')

#### Completion Fields (Post-Execution)

Fields that document what was actually produced and how it was verified:

- `deliverables`: Actual artifacts or file paths produced during execution
- `validation_report`: Structured validation results for all acceptance criteria

### Task Lifecycle

The ExecutableMetadata mixin supports a clear task lifecycle:

1. **Planning** → Populate `action_items`, `acceptance_criteria`, `expected_artifacts`
2. **In Progress** → Agents work; `deliverables` & `validation_report` remain null
3. **Review** → Review agent or human fills `deliverables`; runs checks → writes `validation_report`
4. **Done** → Status set to done; `validation_report` provides audit trail

### Validation Report Structure

The validation report consists of:

- `ValidationReport`: Container for validation metadata and results
  - `validated_by`: User or agent ID who performed the validation
  - `timestamp`: When the validation was performed
  - `results`: List of validation results for each criterion

- `ValidationResult`: Result for a single acceptance criterion
  - `criterion`: The acceptance criterion being validated
  - `status`: "pass" or "fail"
  - `notes`: Optional notes about the validation

### Validation Rules

The mixin enforces several validation rules:

1. At least one acceptance criterion is required for all executable items
2. When an item is marked as "done" or "completed", it must have a validation report
3. All validation results in the validation report must have "pass" status for an item to be considered done

## Agent Framework Compatibility

The ExecutableMetadata fields are designed to be compatible with popular AI agent frameworks:

### CrewAI Compatibility

| CrewAI Field | ExecutableMetadata Field |
|--------------|--------------------------|
| description | TaskMetadata.description |
| expected_output | ExecutableMetadata.expected_artifacts |
| tools | ExecutableMetadata.tool_hints |
| verify | ExecutableMetadata.acceptance_criteria |
| dependent_tasks | ExecutableMetadata.blocked_by |
| priority | ExecutableMetadata.priority_score |
| reviewer | ExecutableMetadata.reviewer |
| result | ExecutableMetadata.deliverables |
| verification_result | ExecutableMetadata.validation_report |

### OtherSideAI Workflow Engine Compatibility

| Workflow Step Attribute | ExecutableMetadata Field |
|-------------------------|--------------------------|
| objective | TaskMetadata.title / description |
| actions | ExecutableMetadata.action_items |
| required_artifacts | ExecutableMetadata.expected_artifacts |
| blocking_steps | ExecutableMetadata.blocked_by |
| evaluation_tests | ExecutableMetadata.acceptance_criteria |
| priority | ExecutableMetadata.priority_score |
| outputs | ExecutableMetadata.deliverables |
| test_results | ExecutableMetadata.validation_report |

### AutoGen GroupChat/Swarms Compatibility

| Agent Message Contract | ExecutableMetadata Field |
|------------------------|--------------------------|
| plan | ExecutableMetadata.action_items |
| criteria | ExecutableMetadata.acceptance_criteria |
| artifacts | ExecutableMetadata.expected_artifacts |
| result_block | deliverables + validation_report |

## Memory Block Types and Relationships

### Epic

An Epic represents a large body of work that can be broken down into multiple projects, tasks, or stories. It typically represents a significant business initiative or a major feature set.

Relationships via BlockLinks:
- `parent_of`: Points to projects that are part of this epic
- `epic_contains`: Points to tasks that are part of this epic
- `has_bug`: Points to bugs that affect this epic

### Project

A Project represents a well-defined body of work with a specific goal and timeline.

Relationships via BlockLinks:
- `child_of`: Points to a parent project that this project is part of
- `parent_of`: Points to a child project that is part of this project
- `belongs_to_epic`: Points to an epic that this project is part of
- `epic_contains`: Points to an epic that is related to this project (if project contains epics)
- `has_bug`: Points to a bug that is related to this project

### Task

A Task represents a specific, actionable piece of work to be done.

Relationships via BlockLinks:
- `subtask_of`: Points to a parent task or project that this task is part of
- `depends_on`: Points to another task that must be completed before this one can start
- `belongs_to_epic`: Points to an epic that this task is part of
- `blocks`: Points to another task that cannot proceed until this one is complete
- `is_blocked_by`: Points to another task that is blocking this one
- `has_bug`: Points to a bug that is related to this task

### Bug

A Bug represents an issue, defect, or unexpected behavior in software that needs to be addressed.

Relationships via BlockLinks:
- `bug_affects`: Points to a component, project, or system affected by this bug
- `is_blocked_by`: Points to another task or bug that is blocking this one
- `blocks`: Points to another task or bug that is blocked by this one 