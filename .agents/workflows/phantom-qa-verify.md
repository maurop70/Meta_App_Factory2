---
description: Run Phantom QA after any code change to Sentinel or Factory apps
---

# Phantom QA Auto-Verify Workflow

This workflow **MUST** be executed automatically after any code change to Sentinel Bridge, Resonance, or any Factory app. The agent should NOT wait for the user to ask for testing.

## When to trigger

- After implementing any new endpoint or modifying an existing one
- After fixing bugs in any app
- After applying gap remediation or architecture changes
- After any EXECUTION phase before reporting results to the user

## Steps

### 1. Run API endpoint tests
// turbo
```
python "<Factory_Dir>/Project_Aether/C-Suite_Active_Logic/Phantom_QA/phantom_agent.py" --app Sentinel
```

If the built-in suite doesn't cover the changed endpoints, write a targeted test script and run it.

### 2. Run UI impersonation tests via browser

Open the app dashboard in the browser and test user flows:

- Navigate to `http://localhost:5009/dashboard`
- Test any new UI features (buttons, forms, modals) by clicking through them
- Verify visual feedback (toasts, updated lists, modals opening/closing)
- Take screenshots as evidence for the walkthrough

### 3. Report results

- Include pass/fail counts in the task summary
- Attach screenshots from UI tests to the walkthrough
- If any test fails, switch to EXECUTION mode and fix before reporting to user

## Important

> [!CAUTION]
> **Never skip Phantom QA.** The user expects automatic testing after every change.
> Skipping this workflow is equivalent to shipping untested code.
