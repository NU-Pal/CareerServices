---
title: CareerServices
emoji: 🎯
colorFrom: gray
colorTo: blue
sdk: docker
pinned: false
---

## Career Services API (FastAPI)

Three modules for **NUPAL**:

| Folder | Routes | Purpose |
|--------|--------|---------|
| `app/services/resume_parsing` | `/v1/resume/*` | PDF → structured JSON |
| `app/services/job_description` | `/v1/resume/job-fit/*` | Job posting vs resume |
| `app/services/ai_interview` | `/v1/interview/*` | Questions, feedback, voice agent |

### One database with NUPAL.Core

Uses **MongoDB** with the same **`MONGO_URL`** and database name **`nupal`** as `NUPAL-Core-Services` (`resume_analyses`, `job_fit_results`). Documents follow the same shape as the C# entities (`StudentEmail`, `Data`, `AnalysisJson`, …).

### Environment variables

See **`.env.example`** (explains `CAREER_SERVICES_API_KEY` and `CORS_ORIGINS`).

- **`GROQ_API_KEY`** — same role as **`GroqApiKey`** in the .NET API; one Groq key is enough for all services (create/revoke keys in [Groq Console](https://console.groq.com)).
- **`MONGO_URL`** — same as **`MONGO_URL`** in `appsettings` / user secrets for NUPAL.Core.Api.
- **`MONGO_DATABASE`** — default `nupal` (must match `GetDatabase("nupal")` in .NET).
- **`DEEPGRAM_API_KEY`** — only for live voice interview.
- **`CAREER_SERVICES_API_KEY`** — optional shared secret; your Next.js proxy sends `X-API-Key`.

### NUPAL frontend

Set `CAREER_SERVICES_URL` + `CAREER_SERVICES_API_KEY` in server env (see `NUPAL-Frontend/.env.example`).

### ملاحظات سريعة (عربي)

- **`CAREER_SERVICES_API_KEY`**: كلمة سر **أنت تختارها** (لحماية الـ Space العام). نفس القيمة في سيرفر Next.js تحت `CAREER_SERVICES_API_KEY`.
- **`CORS_ORIGINS`**: من يقدر يضرب الـ API من المتصفح مباشرة؛ لو الفرونت يمر على `/api/career-services` فـ `*` غالباً كافي.

**تنبيه أمني:** لو ظهرت مفاتيح Groq أو Mongo في شات أو Git، أنشئ مفاتيح جديدة من لوحة Groq وغيّر كلمة مرور مستخدم Mongo في Atlas.
