# jns23lab AI Features (Gemini / Vertex AI)

## Architecture

```
Client
  │
  ├─ POST /api/ai/analyze        → [all users, rate limited] → ai_service.generate_analyze
  │                                  → cache lookup → Gemini (if miss) → cache save + usage log
  │
  ├─ POST /api/ai/chat           → [premium only, 50/day]   → ai_service.generate_chat
  │                                  → history from ai_chat_messages → Gemini → save turn + usage log
  │
  └─ POST /api/ai/chat-with-image → [premium only, 50/day]   → ai_service.generate_chat_with_image
                                     → image + message → Gemini → save turn + usage log
```

## Feature 1: AI Analyze

- **Purpose:** When a student fails a UKK step (e.g. WEB-04 Nginx PHP-FPM), they can send exam result details + optional config snippets and get an explanation and suggested fix.
- **Access:** All authenticated users (not blacklisted). Non-premium: 3 requests/day; Premium: 20 requests/day.
- **Caching:** Same request (same user + same payload hash) returns cached result; no Gemini call.
- **Security:** Secrets and credentials in `exam_result_details` and `config_snippets` are redacted before sending to Gemini (`ai_security.filter_secrets_*`).

### Request/Response

- **POST /api/ai/analyze**  
  Body: `{ "exam_result_details": [ {...}, ... ], "config_snippets": { "nginx_config": "...", "error_log": "..." } }`  
  Response: `{ "explanation": "...", "from_cache": false }`

### Example prompt (built in service)

- System instruction: expert for jns23lab UKK; explain failure and suggest fix; no credentials.
- User prompt: JSON of failed steps + optional config blocks; then "Please explain why this step failed and suggest a fix."

---

## Feature 2: AI Assistant (Premium only)

- **Purpose:** Chat for learning and debugging (Proxmox, Ubuntu, Nginx, MySQL, WordPress, DNS, UKK prep, platform usage).
- **Access:** Premium users only. 50 messages per day (including chat-with-image).
- **History:** Last 10 messages per user stored in `ai_chat_messages` and sent as context to Gemini.
- **Image:** POST /api/ai/chat-with-image accepts an image file (screenshot of error/config/terminal) + optional text; sent to Gemini via `Part.from_bytes`.

### Request/Response

- **POST /api/ai/chat**  
  Body: `{ "message": "How do I fix Nginx 502?" }`  
  Response: `{ "reply": "...", "input_tokens": 100, "output_tokens": 50, "remaining_today": 49 }`

- **POST /api/ai/chat-with-image**  
  Form: `message` (optional), `image` (file).  
  Response: same as chat.

### System prompt (assistant)

Defined in `app/services/ai_service.py` → `ASSISTANT_SYSTEM_PROMPT`: jns23lab AI assistant; DevOps/UKK; educational and supportive; no harmful/insecure advice; can describe screenshots.

---

## Config (.env)

- `VERTEX_PROJECT_ID` – GCP project ID (required).
- `VERTEX_LOCATION` – e.g. `us-central1`.
- `VERTEX_CREDENTIALS_PATH` – path to service account JSON; empty = Application Default Credentials.
- `GEMINI_MODEL` – e.g. `gemini-2.0-flash-exp` or `gemini-2.0-flash-lite`.

---

## Database

- **ai_usage_logs** – one row per analyze or chat call; `feature` (analyze | chat), `user_id`, `created_at`, optional token counts.
- **ai_analyze_cache** – cache key (hash of user_id + payload), `response_text`, `user_id`.
- **ai_chat_messages** – last N messages per user for context; `role` (user | assistant), `content`, optional token fields.

---

## Rate limits (in code)

- Analyze: non-premium 3/day, premium 20/day (`ai_rate_limiter.check_analyze_limit`).
- Chat: 50/day per user (`ai_rate_limiter.check_chat_limit`).
- When exceeded: HTTP 429 with message "Daily limit reached ...".

---

## Files

| Path | Role |
|------|------|
| `app/config.py` | Vertex/Gemini settings |
| `app/models/ai_usage_log.py` | Usage log model |
| `app/models/ai_analyze_cache.py` | Analyze cache model |
| `app/models/ai_chat_message.py` | Chat history model |
| `app/services/ai_security.py` | Redact secrets before sending to AI |
| `app/services/ai_service.py` | Gemini client, analyze + chat + chat-with-image |
| `app/services/ai_rate_limiter.py` | Daily limits and log_usage |
| `app/schemas/ai.py` | Request/response schemas |
| `app/routers/ai.py` | POST /ai/analyze, /ai/chat, /ai/chat-with-image |

Run migration: `alembic upgrade head`.  
Install deps: `pip install google-genai google-auth`.
