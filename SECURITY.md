# Security policy

## What this software does
It runs **locally** on your Windows PC and lets an AI assistant call the COM APIs of programs you already have open (ETABS, SAP2000, SAFE, AutoCAD). It makes **no network connections** and sends no telemetry.

## Protections
* **Read-only by default for real work.** Write tools only act on documents created by the tools (sandbox folder) or empty new ones.
* **`allow_edit`** unlocks one real document for a limited time, saves a backup first, and is logged to `logs/audit.log`. The AI is instructed to call it only when *you* explicitly ask.
* Path validation (extension allow-list, no `..`, no device names), no overwriting outside `sandbox/` and `exports/`.
* AutoCAD `send_command` blocks commands that save/close/open files, run programs or delete files.
* Output size limits, per-call timeouts, crash recovery (supervisor).

## Limits - read this
* The guard protects against mistakes, not against a hostile local user: anything running as you can edit your files anyway.
* `set_table` / `send_command` are powerful (they can change a lot of the open sandbox document).
* A backup contains the last **saved** version; unsaved changes inside the program are not in it.
* Always review engineering results independently. See the disclaimer in the README.

## Reporting a vulnerability
Please do **not** open a public issue for a security problem. Use GitHub's "Report a vulnerability" (private security advisory) on this repository. Include the version, steps, and impact. We aim to respond within 7 days.
