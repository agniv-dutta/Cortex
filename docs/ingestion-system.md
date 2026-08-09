# Think9 Decision Intelligence — Automated Ingestion System

**Version:** 1.0
**Status:** Draft for review
**Companion docs:** `decision-intelligence-spec.md` (§3 ingestion, §4 data model, §5 embeddings), `decision-intelligence-mvp.md`, `agentic-workflow.md`. This doc is the detailed, source-by-source ingestion specification.

---

## 1. Scope & Design Principles

Automated ingestion turns five live sources — meetings, playbooks, email, Slack, and CRM/operational systems — into versioned, deduplicated, provenance-clean documents in the canonical corpus.

Principles (inherited from the full spec):
1. **Raw-first.** Every source event persists immutably to object storage before any transformation. Reprocessing is always possible.
2. **Idempotent.** Each source event maps to a unique `event_id`; replaying is a no-op.
3. **Content-addressed.** Documents/chunks are keyed by `sha256`; identical content is never re-ingested.
4. **Versioning, not overwriting.** Edits create new versions; old versions stay queryable with `superseded_by`.
5. **Fail-degraded, never fail-silent.** Degradation is logged and observable; permanent failures land in a DLQ for review.

### 1.1 High-level pipeline

```
 SOURCES (5)                       INGEST CORE                           CANONICAL CORPUS
 ┌──────────────────────┐   ┌──────────────────────────────────────┐   ┌──────────────────────┐
 │ 1. Zoom / Meet API   │──▶│ event-bus → adapter → validate        │──▶│ documents            │
 │ 2. Drive / Notion    │──▶│ persist-raw → parse → redact →        │──▶│ chunks (vector)      │
 │ 3. Gmail API         │──▶│ normalize → entity-resolve →          │──▶│ decisions            │
 │ 4. Slack Events API  │──▶│ extract (LLM) → chunk → embed →       │──▶│ learnings            │
 │ 5. Airtable/SFDC     │──▶│ index → publish-event                 │   │ vendors/brands meta  │
 └──────────────────────┘   └──────────────────────────────────────┘   └──────────────────────┘
        sync/stream/event            │ retries → DLQ → audit log
        adapters + per-source        ▼
        polling schedules      object storage (raw vault, immutable)
```

---

## 2. Source Adapters

### 2.1 Meetings — Zoom / Google Meet

**Trigger:** provider webhook when a recording/transcript is ready (Zoom `recording.completed`, Google Meet transcript export via Workspace), with a scheduled backfill poll as fallback.

**Pipeline:**
```
webhook (meeting_ended + transcript ready)
  → fetch transcript + participants via provider API
  → persist raw (audio ref, transcript, metadata)
  → redact external-party PII (keep internal attribution)
  → LLM: meeting summary          → doc_type=meeting_summary
  → LLM: extract decisions/owners/deadlines → decision rows + @mentions of owners
  → classify brand(s) + function(s)         → tagging metadata
  → chunk transcript (speaker-turn aware)   → embed → index
  → emit decision.created + meeting.indexed events
```

**Deliverables per meeting:**

| Output | doc_type | Content | Notes |
|--------|----------|---------|-------|
| Transcript | `meeting` | Speaker-tagged chunks | Chunk at speaker-turn boundaries (§3.1) |
| Summary | `meeting_summary` | LLM digest, decisions, owners, deadlines | Single doc; linked to transcript by `meeting_id` |
| Decisions | `decision` | Each extracted decision as a standalone doc | Carries owner, deadline, status=`proposed` |
| Tags | metadata | `brands[]`, `functions[]` | From classifier + entity resolution |

**Zoom specifics:** use API v2 (`/meetings/{id}/recordings`, transcript download), OAuth app scopes: `recording:read`, `meeting:read`. 
**Meet specifics:** Google Workspace exports captions/transcripts to Drive; watch that Drive folder + Meet API for participant/recording metadata.

**Sample adapter event:**
```jsonc
{ "event_id": "evt_z2m_01JZ…", "source": "zoom",
  "provider_event": { "meeting_id": "964-0123-4567", "topic": "Q3 Vendor Strategy",
    "started_at": "2026-08-08T14:00:00Z", "duration_min": 58,
    "transcript_url": "https://api.zoom.us/…/transcript", "type": "recording.completed" } }
```

### 2.2 Playbooks — Google Drive / Notion

**Trigger:** Drive — watch-channel push (`changes.list`) + nightly poll; Notion — incremental poll on `last_edited_time`, or Notion webhook via third-party bridge.

**Pipeline:**
```
change event (drive_file / notion_block updated)
  → fetch latest content (Drive: export to text/MD; Notion: blocks API recursive)
  → compute content hash → compare with latest indexed version
  → if unchanged: no-op (update last_seen)
  → if changed: new version v_{n+1} → parse → extract rules (LLM) → chunk → embed → index
  → version diff: rule-level comparison vs previous active version
       → contradiction across versions? → flag + deprecate old version
       → deprecated content? → mark old version status=superseded, superseded_by=v_{n+1}
  → publish playbook.versioned + contradiction.detected events
```

**Versioning semantics:**
- Each content change = new `document.version` (monotonic per doc_id).
- Old versions remain in the corpus with `effective_to` and `status=superseded`; retrieval filters them out for *new* lookups but keeps them for "as-of" historical queries.
- **Cross-version contradiction check:** extract structured rule statements per version (`rule_statement`, `constraint`). Compare new version's rules against the previous active version. A rule is flagged `contradicts` when semantic similarity is high but the normative direction is opposite (e.g., "renegotiate early" vs "never renegotiate before 90 days"). Emit `playbook.contradiction` event → surfaces in the contradiction flagger (§6 of agentic spec) and an email alert.

**Drive specifics:** OAuth with `drive.readonly`; use `files.export` (MIME `text/markdown`, `text/plain`). Watch channel TTL 10 days — must renew.
**Notion specifics:** integration token; `block.children.list` recursion with depth cap; skip huge page trees via page-level index.

### 2.3 Email digest — Gmail API

**Trigger:** Gmail push (Pub/Sub `historyId` watch) with polling fallback.

**Pipeline:**
```
push notification (historyId delta)
  → incremental sync (users.messages.list with historyId) — only NEW/CHANGED messages
  → relevance filter (decision-related thread heuristics, §2.3.1)
  → for relevant threads: persist raw (EML), redact BCC/signatures
  → LLM: extract action items + follow-ups + any decision signals
  → link to originating decision (mention of dec_ID, or fuzzy title match)
  → chunk digest → embed → index → emit email.ingested + action_item.created
```

**Relevance filter (decision-related threads):** a message is ingested when it matches any:
- Thread already tracked as decision-related (has an existing `decision` or `action_item` link).
- Subject/body matches entity-aware signals (vendor names, `decision`, `renewal`, `renegotiate`, `approval`, milestone terms).
- Sender/recipients in an active decision thread (participant list).
- Reply-to on a known decision thread (thread linkage preserved).
Everything else is skipped (no corpus spam).

**Linking to originating decision:**
- Exact: body contains `dec_<ULID>` or a decision reference token.
- Fuzzy: LLM matches thread content against candidate decision titles (from `decisions` collection) at similarity ≥ 0.8, or against the meeting it was decided in (via `meeting_id` in thread headers/body).

**Gmail specifics:** OAuth 2.0 scopes `gmail.readonly`; `historyId` monotonic per mailbox — incremental sync never rescans full inbox. Rate limits: stay under 250 quota units/user/s; use batch where possible.

### 2.4 Slack channel scraping

**Trigger:** Events API (real-time) for subscribed key channels + backfill crawl of those channels.

**Pipeline:**
```
event (message.channel / message.posted in subscribed channel)
  → dedupe by (channel_id, ts) — idempotent
  → noise classifier (§2.4.1): drop greetings/off-topic/react-threads
  → accumulate thread context (parent + replies)
  → LLM: on thread close, extract decisions + consensus points + owners
  → persist raw, redact external PII, chunk digest → embed → index
  → emit slack.ingested + consensus.recorded
```

**Noise suppression (mandatory):** a lightweight classifier scores each message `informative | noise`:
- Drop: greetings, "thanks", reactions-only, meeting invites, bot pings, off-topic channels (opt-in list).
- Keep: decisions, proposals, numbers/terms, action assignments, outcome reports, links to decisions.
- Threshold: keep when `informative_prob ≥ 0.85`; borderline messages are kept but tagged `low_confidence` for spot review (prevents silent loss).

**Consensus extraction:** threads are summarized once at close (or after 24h idle). Consensus points = statements with ≥2 participants agreeing and no unresolved objection — stored as `learnings` candidates pending human confirm (or auto-accepted under eval threshold, Phase 2).

**Slack specifics:** app with `channels:history`, `channels:read`, `groups:history`; Events API `message.channel`; `conversations.history` for backfill; ignore bot messages except our own ingest bot's replies; cap backfill at 6 months per channel in Phase 1.

### 2.5 CRM / Operational — Airtable, Salesforce

**Trigger:** Airtable — webhook (`table.records.updated`) + scheduled base sync; Salesforce — Change Data Capture (CDC) streaming events + scheduled sobject sync.

**Pipeline:**
```
event (airtable record update / SFDC CDC)
  → normalize record → map to canonical entity (vendor/launch/feedback)
  → resolve dedupe key (vendor name+domain, launch_id)
  → fetch related records (negotiations, stages, owners)
  → LLM: summarize negotiation history / customer feedback → digest doc
  → link to decisions (vendor_id ↔ decisions.vendors)
  → persist + index + emit vendor.updated / launch.updated / feedback.summary
```

**What becomes corpus content (not raw records):**

| Source object | Canonical mapping | Corpus output |
|---------------|-------------------|---------------|
| Airtable `Vendors` | `vendor` entity | vendor profile (terms, spend, contacts) |
| Airtable `Negotiations` | `negotiation` doc | negotiation timeline + outcomes |
| Salesforce `Opportunity` | `negotiation`/`launch` doc | deal history, stage changes |
| Salesforce `Case` / feedback | `feedback_summary` | summarized customer signal, tagged brand/product |
| SFDC/Airtable launch records | `launch` doc | launch plan + post-launch outcome |

**Airtable specifics:** Personal Access Token; `GET /v0/{base}/{table}` with cursor for >100 rows; store a `base.table.id + updated_time` watermark per base for incremental pulls.
**Salesforce specifics:** Connected App OAuth; CDC on the sobjects above (push events to the event bus); full refresh nightly via bulk API 2.0.

---

## 3. Processing Pipeline

### 3.1 Chunk strategy (by doc_type)

Consistent with the full spec §5.2; extended for the new source types.

| doc_type | Boundary strategy | Target tokens | Overlap | Rationale |
|----------|-------------------|---------------|---------|-----------|
| `meeting` (transcript) | Speaker-turn aware; never split a turn; heading boundaries | 300–500 | 50 | Preserve attribution |
| `meeting_summary` | Whole doc (or section if >2k tokens) | ≤ 800 | 0 | Summaries are compact; keep whole for citation |
| `playbook` | Rule-aware: one rule/constraint per chunk, heading-bound | 300 | 30 | Rules must be self-contained to diff/flag |
| `decision` | Whole decision block (statement+rationale+outcome) | ≤ 500 | 0 | Matchability requires self-containment |
| `email` | Whole email; if >600 tokens, split on paragraph after a reply marker | ≤ 500 | 30 | Thread atomicity |
| `action_item` | Single item | ≤ 150 | 0 | Single purpose |
| `slack_digest` | Whole digest (thread summary) | ≤ 800 | 0 | Compact, citable |
| `vendor` / `negotiation` / `launch` / `feedback_summary` | Section-aware (profile, terms, timeline, outcome) | 400 | 40 | Source-specific structure |

### 3.2 Metadata extraction

Two passes — **deterministic** (from source fields, always wins) and **LLM-extracted** (fills gaps, validated).

| Field | Deterministic source | LLM extraction |
|-------|----------------------|----------------|
| `authored_at` | Provider timestamp | — |
| `owner` | Meeting organizer / doc author / thread sender | Action-item owner (@mention → resolve to user) |
| `brands[]` | Drive folder / Slack channel / Airtable brand field | Classifier on content |
| `functions[]` | Mapping table (channel → function) | Classifier on content |
| `category` | — | Classifier (procurement/brand/product/hr/legal/ops) |
| `priority` | — | Priority signal (urgency words, deadline proximity, $ values) |
| `deadline` | — | Date entity + relative-date resolution |
| `entities[]` | Linked records (vendor/launch) | Vendor/product/region NER |
| `status` | Source record state | proposed/draft/active/executed |

LLM metadata is always *suggested*: schema-validated JSON, low-confidence tags (`< 0.7`) go to a review queue rather than being silently dropped.

### 3.3 Embedding generation

| Setting | Value | Rationale |
|---------|-------|-----------|
| Model | `text-embedding-3-small` (1,536 dim) default; `BGE-M3` fallback profile | Cost + quality for ~6–20k chunks |
| Batch size | 64 per request (within provider rate limits) | Max throughput at steady state; tune via latency probe |
| Concurrency | 4–8 workers per ingest job | Avoids provider throttling; bounded by queue depth |
| Caching | Embedding cache keyed by `sha256(content)` | Re-processing an unchanged chunk costs 0 embeddings |
| Role marker | Prefix chunk content with role token (e.g., `[rule]`) where the model supports asymmetric search | Improves retrieval for normative content |
| Versioning | `embedding_model_version` stamped on every write | Enables blue/green re-embed (§5.4 full spec) |

### 3.4 Vector DB insertion — versioning & update logic

**Insert/update semantics (idempotent upsert):**
```
For each (document_id, version):
  1. snapshot current chunks (for tombstones)
  2. upsert new/edited chunk vectors  (ON CONFLICT chunk_id DO UPDATE)
  3. delete vector entries for chunks removed in this version (tombstone)
  4. update document row: version, sha256, status, effective_from/to, superseded_by
  5. publish document.versioned
```

**Version lifecycle:**

| Status | Meaning | Retrieval visibility |
|--------|---------|----------------------|
| `active` | Current version | Included (default) |
| `superseded` | Replaced by newer version | Excluded from default retrieval; queryable "as-of" |
| `archived` | Retired (no successor / legal hold) | Excluded; audit access only |
| `draft` | Ingested but not confirmed (e.g., low-confidence transcript) | Excluded until confirmed |

**Rules:**
- Chunk IDs are stable per `(document_id, version, chunk_index)` — no dangling citations after an update (citations always resolve to a real chunk or a tombstone marker).
- Supersede is written *after* the new version is fully indexed (never partial states).
- Deletions are tombstones, not hard deletes (audit requirement). Tombstone GC runs quarterly.
- ACL/classification are copied from the document row into chunk payload at write time.

### 3.5 Deduplication rules

Applied in order; first match wins.

| Rule | Key | Behavior |
|------|-----|----------|
| 1. Exact content hash | `sha256(normalized_content)` | Skip entirely; refresh `last_seen` |
| 2. Near-duplicate embedding | cosine ≥ 0.97 (same doc_type, 60-day window) | Keep the one with richer metadata; tag the other `duplicate_of` |
| 3. Source-native id | Provider event/message/record id | Upsert (source is source of truth for its object) |
| 4. Thread linkage | `(channel_id, ts)` / `(thread_id, message_id)` | Slack dedupe; email thread collapse |
| 5. Entity canonicalization | Vendor name+domain, launch_id, meeting_id | Merge into canonical entity; dedupe on vendor profile docs |
| 6. Cross-version duplicate | Same doc, unchanged hash | Version no-op (§2.2) |

**Near-dup handling:** the lower-quality copy is not indexed for retrieval but retained as a *reference doc* (points to the canonical doc_id) so search results never show twins.

---

## 4. API Contracts

### 4.1 Public ingest API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/ingest/{source}` | POST | Trigger ingestion for a source ref (e.g., a Drive file id, Zoom recording id) |
| `/v1/ingest/{source}/backfill` | POST | Full/date-range backfill for a source |
| `/v1/ingest/jobs/{job_id}` | GET | Job status + progress |
| `/v1/ingest/jobs/{job_id}/retry` | POST | Re-queue a failed job |
| `/v1/ingest/documents/{doc_id}` | GET | Document + versions + status |
| `/v1/ingest/documents/{doc_id}/supersede` | POST | Manually mark a doc superseded (admin) |
| `/v1/ingest/dedupe/report` | GET | Recent dedupe decisions (audit) |

### 4.2 Webhook receivers (provider push)

| Endpoint | Provider | Verified by |
|----------|----------|-------------|
| `POST /webhooks/zoom` | Zoom recording/transcript ready | Zoom `Authorization` header + app secret |
| `POST /webhooks/meet` | Meet transcript exported to Drive | Drive watch channel |
| `POST /webhooks/gmail` | Gmail push (Pub/Sub) | Pub/Sub push token |
| `POST /webhooks/slack` | Slack Events API | Slack `X-Slack-Signature` (HMAC) |
| `POST /webhooks/airtable` | Airtable table updates | Airtable webhook secret |
| `POST /webhooks/salesforce` | SFDC CDC push | SFDC JWT / org identity |

### 4.3 Sample — trigger ingestion (request/response)

```jsonc
// POST /v1/ingest/drive
{ "source_ref": { "kind": "drive_file", "id": "1AbC…", "mime": "text/markdown" },
  "force_reprocess": false }

// 202 Accepted
{ "job_id": "ing_01JZ…", "status": "queued",
  "stages": ["fetch","parse","redact","extract","chunk","embed","index"],
  "estimated_documents": 1 }
```

### 4.4 Ingest job event schema (internal, on the event bus)

```jsonc
{ "event_id": "evt_…", "event_type": "ingest.job.completed",
  "trace_id": "trc_…", "source": "slack",
  "job_id": "ing_…",
  "documents": [{ "document_id": "doc_…", "version": "3", "sha256": "…", "doc_type": "playbook" }],
  "chunks": 47, "duplicates_skipped": 12, "failures": 0,
  "elapsed_ms": 8400, "embedding_model_version": "text-embedding-3-small@1" }
```

---

## 5. Error Handling

### 5.1 Error taxonomy

| Class | Examples | Handling |
|-------|----------|----------|
| **Transient** | Provider 429, 5xx, timeout, network blip | Retry with backoff; resume at same stage |
| **Authentication / scope** | OAuth token expired, revoked scope | Refresh token (auto) → if fails, alert owner + pause source |
| **Schema drift** | Airtable base renamed a field, SFDC object changed | Stage the event; notify integrator; do not guess |
| **Content malformed** | Empty transcript, unreadable PDF, encoding error | DLQ with sample; source owner reviews |
| **Poison payload** | Parser/LLM cannot make sense after 3 attempts | DLQ; never silently drop |

### 5.2 Retry logic

| Dimension | Policy |
|-----------|--------|
| Retry count | 3 attempts per stage, then 1 full-stage retry after DLQ review |
| Backoff | Exponential: 1s → 4s → 15s, + full jitter |
| Provider 429 | Honor `Retry-After` header when present; else min(60s, backoff) |
| Idempotency | Retries replay the same `(event_id, stage)` — always safe (content-addressed) |
| Circuit breaker | Per-provider, per-source: trip after 5 consecutive 5xx/429; half-open after 60s probe |
| Deadline | Per-job timeout (source-dependent, e.g., 30 min); a timed-out job resumes at last checkpoint (stage + offset), never restarts raw fetch |
| DLQ | Every permanent failure + 3-strikes + poison payload → `dlq` topic; retention 90 days; admin replay UI |

### 5.3 Degradation behavior
- **Provider outage:** source adapter pauses (circuit open), catch-up on recovery — ingestion is eventually consistent, never lossy.
- **Embedder outage:** jobs wait on the embedding stage (queue), do not fall back to a different model silently (would mix vector spaces).
- **LLM outage (summarize/extract):** deterministic fallback — keep raw content + deterministic metadata; mark doc `draft`; LLM enrichment retried on a background pass. Corpus is never blocked on an LLM.
- **Index outage:** buffer at the index stage; replayed on recovery (idempotent upsert).

---

## 6. Audit Trails

### 6.1 What is audited (append-only, WORM)
| Event | Records |
|-------|---------|
| Ingest lifecycle | `ingest.job.started`, `.stage_started`, `.stage_completed`, `.job.failed`, `.job.dequeued` |
| Document lifecycle | `document.created`, `.versioned`, `.superseded`, `.archived`, `.tombstoned` |
| Extraction | `extraction.summary`, `.decisions`, `.action_items`, `.tags` (with model + prompt version) |
| Dedup | `dedupe.hit` (rule, winner, loser, hash) |
| Contradiction | `playbook.contradiction`, `content.deprecated` |
| Errors | `ingest.failed`, `dlq.enqueued`, `dlq.replayed` |
| Admin actions | manual supersede, force-reprocess, backfill, retention GC |

### 6.2 Audit record shape
```jsonc
{ "audit_id": "aud_…", "ts": "2026-08-09T10:12:33.112Z",
  "actor": { "type": "system|user", "id": "ingest-worker-3 | U123" },
  "action": "document.versioned",
  "target": { "type": "document", "id": "doc_…", "version": "3" },
  "trace_id": "trc_…", "source_event_id": "evt_z2m_…",
  "sha256": "…", "payload_summary": "v3 adds §7 pricing rule; supersedes v2" }
```

### 6.3 Properties
- **Immutable:** append-only table + object-storage journal; tamper-evident hash chain over the journal (each row links `prev_hash`).
- **Correlatable:** every record carries `trace_id`, `source_event_id`, `sha256` — the full path from provider event to indexed chunk is reconstructible.
- **Reprocessing:** given a `source_event_id`, the pipeline can replay the exact event through all stages (the "replay from envelope" audit use case).
- **Queryable:** audit UI + SQL: "show all versions of doc_…", "what did we ingest from Zoom on Aug 8", "which chunks changed in playbook v3".
- **Retention:** journal 7 years (compliance); raw vault 7 years; DLQ 90 days; vector tombstone GC quarterly.

---

## 7. Deployment Notes (Phase fit)

| Component | Phase 1 (MVP) | Full |
|-----------|---------------|------|
| Meetings (transcript-ready trigger) | ✅ Zoom + Meet transcript exports | ✅ + raw audio STT |
| Drive + Notion playbook sync | ✅ (Drive + Notion) | ✅ |
| Gmail decision digest | ✅ (poll + relevance filter) | ✅ + push |
| Slack real-time ingestion | ✅ (key channels) | ✅ + broader channels |
| Airtable/Salesforce | ✅ (Airtable only) | ✅ + SFDC CDC |
| Playbook version contradiction detection | ✅ (rule-diff) | ✅ + cross-doc memo sweep |
| LLM extraction (owners/deadlines/action items) | ✅ (gpt-4o-mini) | ✅ + evals on extraction accuracy |

**Runbooks (key):** "Drive/Notion sync stalled" → check watch-channel TTL + token; "Gmail historyId overflow (>1k messages)" → reset to watermark, full incremental catch-up; "Slack rate limit during backfill" → pause crawl, resume offset; "Embedder mixed-vector-space risk" → never auto-failover; always use the pinned profile.

---

## 8. Open Questions

1. Do Zoom/Meet transcripts need to be *confirmed* by a human before decisions extracted from them become `decision` docs, or is LLM extraction + `draft` status sufficient for Phase 1?
2. For Gmail: is the decision-thread relevance filter tuned on real inbox data before Phase 1 (needed to avoid over/under-inclusion)?
3. Notion webhooks need a bridge (no native webhooks) — is a 15-min poll acceptable, or must it be near-real-time?
4. Slack noise classifier: ship rule-based first and collect labels, or fine-tune immediately (requires ~2k labeled messages)?
5. Who owns per-source error DLQ review (integrator per source vs. central data-ops team)?
