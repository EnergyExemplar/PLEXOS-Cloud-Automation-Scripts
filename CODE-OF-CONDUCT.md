# Contributor Code of Conduct

## Our Pledge

We are committed to maintaining a professional and technical repository that prioritises code quality, adherence to standards, security best practices, and collaborative development. This Code of Conduct establishes expectations for all contributors to the Pre & Post Automation project, ensuring consistency, maintainability, and reliability of automation scripts.

## Our Standards

### Recommended Practices

- Follow all Python script standards and coding conventions defined in the platform-specific guides ([PLEXOS](PLEXOSReadme.md), [Aurora](AuroraReadme.md))
- Use Python 3.11 or higher (required for CLI SDK compatibility)
- Use `argparse` for all script inputs with explicit validation
- Organise scripts using the folder structure defined in the platform guides
- Include clear logging and error handling in all automation scripts
- Write small, focused scripts — one script, one job
- **For Pre/Post/Compute scripts:** Write self-contained scripts with no imports from other scripts; chain via `ExecutionOrder`
- **For Automation scripts:** Scripts can import from other Automation scripts when running locally; each script should still be runnable independently
- Provide complete documentation in each script's `README.md`
- Include unit tests to validate core script logic (recommended)
- Use meaningful variable and function names following naming conventions
- Avoid hardcoded paths, credentials, and configuration values; use environment variables and the Secret Manager from the PLEXOS Cloud Python SDK for any secrets or sensitive configuration
- Validate inputs and implement proper error handling
- Keep documentation and examples free of internal names, environment identifiers, personal folder paths, or any information that is not intended for public audiences

### Non-Compliant Practices

- Submitting code that does not follow the Python script standards or naming conventions
- Not using Python 3.11 or higher
- Hardcoding secrets, credentials, or sensitive configuration data
- Creating scripts without proper documentation or error handling
- Deviating from the required folder structure
- Submitting code with unvalidated inputs or missing argument handling
- **For Pre/Post/Compute scripts:** Importing from other scripts (must be self-contained)
- **For Automation scripts:** Creating shared utility modules (import from other scripts instead)
- Including internal environment names, internal system identifiers, or personal DataHub paths in code or documentation
- Including malicious code, security vulnerabilities, or unsafe practices
- Bypassing required code review processes
- Other conduct that violates professional software development standards

## Our Responsibilities

Project maintainers are responsible for:

- Enforcing the Python script standards and coding guidelines
- Ensuring all contributions follow the repository structure
- Validating that scripts include proper error handling, logging, and documentation
- Reviewing code for security vulnerabilities and best practices
- Removing, editing, or rejecting contributions that do not meet established standards
- Maintaining the integrity of the automation framework
- Ensuring all automation scripts comply with the naming conventions and configuration guidelines
- Requiring updates to code that violates established standards
- Addressing violations through appropriate corrective action

All contributors must be prepared to update their submissions to meet project standards and guidelines.

## Scope

This Code of Conduct applies to all contributions, submissions, and interactions within the Pre & Post Automation repository, including:

- All Python automation scripts
- Pull requests and code reviews
- Issues and feature requests
- Documentation and README files
- Contributing to any folder within the repository structure

## Enforcement

Violations of this Code of Conduct should be reported to project maintainers. All violations will be reviewed and addressed through appropriate corrective action. Common violations include:

- Submitting code that does not follow script standards
- Including hardcoded secrets, credentials, or internal system identifiers
- Including internal environment names, personal or team-specific DataHub paths, or other non-public information in code or documentation examples
- Failing to provide required documentation
- Not adhering to repository structure guidelines
- Deviating from Python coding conventions and best practices

Maintainers reserve the right to reject contributions that do not comply with this Code of Conduct and established project standards.

## Key Requirements

All contributors must adhere to:

- **Python Version**: Use Python 3.11 or higher (required for CLI SDK compatibility)
- **Script Standards**: Use `argparse` for inputs, validate all arguments, avoid hardcoding
- **Repository Structure**: Follow the platform folder structure; one folder = one script
- **Documentation**: Provide a `README.md` per script with purpose, arguments, environment variables used, related scripts, and usage examples
- **Testing**: Include unit tests for core script logic (recommended); test scripts locally before submission using `pip install -r requirements.txt`
- **Code Quality**: Implement error handling, clear logging, and focused functions
- **Script Isolation**:
  - **Pre/Post/Compute**: Must be self-contained with no imports from other scripts
  - **Automation**: Can import from other Automation scripts; each script must remain runnable independently
- **Security**: Never hardcode secrets, credentials, internal environment names, or personal identifiers; use environment variables and the Secret Manager from the PLEXOS Cloud Python SDK; use generic placeholders (e.g. `Project/Study/`) in all documentation examples; validate all inputs
- **Review**: All contributions require code review for standards compliance

Reference the platform-specific guides for detailed requirements: [PLEXOS](PLEXOSReadme.md) | [Aurora](AuroraReadme.md)
