# Junior-eligible search, assist-apply, and attribution

## Junior-eligible (search set, not a label rewrite)

A job is **junior-eligible** when:

- `career_stage` is `internship`, `new_grad`, or `junior`, **or**
- `career_stage` is `unknown` IC (not senior-coded in the title) **and** `years_required_min` is null or ≤ 2

It is **not** junior-eligible when `years_required_min >= 3` or the stage is `mid` / `senior`.

We **never** store unlabeled Software Engineer as `junior`. Unspecified eligible roles badge as **Seniority not stated**.

Search `career_stage=junior` uses this eligible set. Internships-only remains exact `career_stage=internship`.

## Assist-apply policy

Remote Atlas **never submits applications**. The candidate copies a field card / note into the employer’s ATS and clicks Apply on the official URL. No Greenhouse/Lever/LinkedIn auto-submit, no Easy Apply clone, no proxy emails.

## Sources and attribution

- Himalayas: we link back via official apply URLs from their public search API.
- GitHub community lists (e.g. cvrve/New-Grad, MIT license): used as **ATS slug discovery only**. We fetch jobs from employer Greenhouse/Lever/Ashby APIs.
- Simplify / Pitt CSC lists: no LICENSE found — do **not** republish those JSON files as our catalog. Do not scrape simplify.jobs.

## Resume storage

Extracted text is in Postgres. Files on Render’s disk are ephemeral; expect uploads to disappear after a dyno restart. Tailored PDFs can be rebuilt from stored text.

## Chat vs embeddings

Embeddings stay **Gemini 768-d**. Chat (tailor, parse, fit-brief) prefers **DeepSeek then Gemini** so embed cron quota is not starved.
