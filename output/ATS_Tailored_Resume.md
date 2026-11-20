# Shashwat Sahu
Contact Line: +91-7007599585 | shashwatsahu25@gmail.com | Bengaluru, India | linkedin.com/in/contactshashwatsahu | github.com/Shashwat-Sahu

## Professional Summary
Highly motivated Backend Software Engineer with 3+ years of experience in building microservices, caching, and OAuth 2.0/JWT access control in Node.js, C#/.NET Core, Python, and Redis for insurance and financial services. Proven track record of leading IPO-readiness, shipping self-serve pricing and routing platforms, and implementing JWT-based identity and PII access control.

## Core Technical Skills
### Languages
- C#
- JavaScript
- TypeScript
- Python
- SQL

### Backend & Frameworks
- Node.js
- .NET Core
- REST APIs
- Microservices
- Kafka
- WebSockets

### Security & Auth
- OAuth 2.0
- JWT
- Identity & Access Control

### Architecture
- Distributed Systems
- Event-Driven Architecture
- Caching Strategies
- Load Testing

### Cloud, DevOps & Observability
- AWS
- Docker
- Kubernetes
- Istio
- CI/CD
- Datadog
- PagerDuty
- Git
- GitHub

### Other
- Apache Airflow
- React.js

## Professional Experience
### Ethos Life Technologies, Software Engineer 2
- Led IPO-readiness for two services (Product Config and Product Routing) and supported the main app: cut p99 latency of the heaviest API from 2–4s to 300ms, categorized and reduced errors by 60%, and ran extensive load tests that guided scaling microservices from 2 to 10 pods and the main app from 18 to 108.
- Eliminated client-facing 500s with retry logic; added PagerDuty alerts on critical paths (failed or slow quote generation traces) and DB latency checks; wrote on-call handover docs per service mapping each error to the relevant code.
- Built a self-serve rate and routing configuration platform (engine plus two admin services) that removed the engineering-deploy dependency for 10–15 pricing and routing changes per month; validated rollout with a 7-day live-traffic shadow run and zero mismatches across 1M+ requests.
- Migrated quote calculation for four insurance products into the Product Config Service via an SDK driven by ingested rate sheets; added instance-level LRU caching that cut latency by 20ms and reduced Redis dependency.
- Implemented JWT-based identity and PII access control (Node.js and Python SDKs, role-based actors), moving decrypted SSN/ITIN/driver's-license access behind a profile-service endpoint and replacing 100+ ungated call sites; authored the launch and rollback plan.
- Secured 30+ Airflow DAGs/jobs with Ory Hydra OAuth 2.0 via the internal gateway, adding authentication for jobs that call internal services.
- Migrated a core eligibility call from the monolith to the Product Routing Service in one day as a P0 (Istio-exposed endpoints, persisted carrier responses, case-creation API; 1500+ requests/day); added routing explainability, a 5M term-coverage cap, and fallback routing when eligibility APIs fail.
- Led the IUL + Choice living-benefits bundle launch in California solo (riders, documents, activation, Datadog dashboard) and built the ITIN flow full-stack, publishing IDV events to Kafka for lifecycle email processing.

### Wells Fargo, Software Developer
- Developed a market data streaming service with .NET Core and SignalR on Wells Fargo's custom "Carina" grid.
- Delivered an admin portal for authorization-based updates to 100,000+ parameters (50% faster, 100+ users).
- Automated report comparison across 200+ indicators with a metadata-driven parser and improved benchmarking.
- Raised code coverage from 40% to the team's 60% target by writing C# tests across a 125,000+ line codebase.

### Wells Fargo, Software Engineering Intern
- Built a buy/sell/hold recommendation mechanism over 10+ indicators for a trading suggestion platform and managed data sourcing for 100+ stocks, authentication, deployment, and testing in an Agile team.

## Key Projects
### Video Conferencing App (WebRTC)
- Launched a full-stack video conferencing web app in one month using WebRTC, React.js, Node.js, MongoDB, and WebSockets, supporting group video calls, screen sharing, recording, live chat, and transcripts (10 concurrent participants tested).

## Education & Certifications
### Bachelor of Technology, Information Technology
- National Institute of Technology, Kurukshetra
- 2019 – 2023
- CGPA: 9.40