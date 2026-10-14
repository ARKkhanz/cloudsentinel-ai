# CloudSentinel AI

> **An AI-assisted cloud reliability prototype that detects unusual service metrics, creates evidence-backed incidents, and helps a developer investigate them.**

*Developed following the CloudSentinel AI Four-Day Implementation & Learning Blueprint.*

---

## Project Status

- **Day 1**: Skeleton + real API + connected dashboard (In Progress)
  - [x] Milestone 0: Repository & GitHub setup
  - [ ] Milestone 1: FastAPI backend + synthetic metrics
  - [ ] Milestone 2: Backend tests
  - [ ] Milestone 3: React + TypeScript frontend
  - [ ] Milestone 4: Connected dashboard + UI states
  - [ ] Milestone 5: Build, verification, documentation and GitHub checkpoint
- **Day 2**: Persistence + detection + incidents + evaluation (Planned)
- **Day 3**: Engineering quality + Docker + CI (Planned)
- **Day 4**: Verification, documentation & demo (Planned)

---

## Important Notice on Telemetry Data
All metric data ingested or processed during Day 1 is **strictly synthetic** and generated deterministically for testing and demonstration purposes. This prototype does not claim production monitoring, real outage prediction, or unmeasured accuracy.

---

## Repository Structure (Proposed)

```text
cloudsentinel-ai/
├── frontend/          # React + TypeScript + Vite UI
├── backend/           # FastAPI backend service
│   ├── app/           # Application logic, schemas, and routes
│   └── tests/         # Automated pytest test suite
├── docs/              # Architecture and learning documentation
├── .env.example       # Safe template configuration
├── .gitignore         # Version control exclusion rules
└── README.md          # Project documentation and instructions
```

---

## Initial Setup & Prerequisites

- **Python 3.10+**
- **Node.js 18+ & npm**
- **Git**
