# n8n Automation

n8n runs as a service in the dev and prod stacks and hosts BKN's automation
workflows (notification routing, EOD reports, news ingestion — all later
sprints).

- **Editor:** http://localhost:5678 (dev).
- **Workflows** are version-controlled as exported JSON under `workflows/`.
- To add one: build it in the editor, export it (Download), and commit the JSON
  here. Do not embed secrets in workflow JSON — use n8n credentials/environment.

No workflows are defined in Sprint 1; this is scaffolding for the Notification
Service (Sprint 17).
