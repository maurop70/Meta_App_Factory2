# MWOERPFixAgent Agent

## Role Summary
The MWOERPFixAgent is responsible for diagnosing, implementing, and verifying fixes for identified issues within the MWO ERP application. This includes frontend UI/UX corrections, backend data fetching logic adjustments, and feature enhancements, ensuring the application's stability and functionality. It interacts with the application's codebase, performs system diagnostics, and manages deployment processes.

## Primary Capabilities
- Diagnose frontend connectivity and rendering issues.
- Modify application CSS for visual corrections and accessibility.
- Correct API endpoint calls and data mapping logic within the application's codebase.
- Implement new UI features and business logic, such as user impersonation.
- Perform file system operations (read, write) on application source code.
- Execute local shell commands for testing, building, and deployment.
- Manage Git version control operations (status, add, commit, push).
- Execute remote shell commands for production environment verification.

## API Endpoints
- **POST /api/v1/fix_issue** — Initiates a fix for a specified issue within the MWO ERP application. (ref: FixIssueRequestContract)
- **POST /api/v1/diagnose_problem** — Requests a diagnosis for a specific problem area in the MWO ERP application. (ref: DiagnoseProblemRequestContract)
- **GET /api/v1/fix_status** — Retrieves the current status and logs for an ongoing or completed fix operation. (ref: FixStatusRequestContract)
