# API

## Primary Endpoints

### Health

- `GET /health`

Simple liveness endpoint.

### Sessions

- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `PATCH /sessions/{session_id}/resume`
- `DELETE /sessions/{session_id}`
- `POST /sessions/{session_id}/messages/{message_id}/feedback`

### Chat

- `POST /chat/stream`

This is the primary runtime endpoint.

It accepts a prompt plus a `session_id` and returns Server-Sent Events.

## Session Payloads

### Create session

```json
{
  "title": "Optional custom title"
}
```

### Session summary response

```json
{
  "id": "uuid",
  "title": "New chat",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "resume_filename": "resume.pdf",
  "message_count": 4
}
```

### Session detail response

```json
{
  "id": "uuid",
  "title": "New chat",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "resume_filename": "resume.pdf",
  "resume_page_count": 2,
  "resume_char_count": 5380,
  "messages": [
    {
      "id": "uuid",
      "role": "assistant",
      "content": "message text",
      "backend_response": {},
      "request_type": "analyze_job",
      "feedback_rating": "up",
      "created_at": "ISO timestamp"
    }
  ]
}
```

## Resume Upload

`PATCH /sessions/{session_id}/resume`

```json
{
  "filename": "sameet_resume.pdf",
  "text": "Extracted PDF text ...",
  "page_count": 2,
  "char_count": 5380
}
```

## Feedback Capture

`POST /sessions/{session_id}/messages/{message_id}/feedback`

```json
{
  "rating": "up"
}
```

Allowed values:

- `up`
- `down`

## Streaming Chat

`POST /chat/stream`

```json
{
  "session_id": "uuid",
  "message": "Analyze this role against my resume."
}
```

The response is an SSE stream with:

- stage events
- one final event
- optional error event

### Example stage event

```text
data: {"type":"stage","stage":"retrieve_memory","status":"completed","message":"Retrieving saved context","meta":{"memory_count":2}}
```

### Example final event

```text
data: {"type":"final","data":{"request_type":"analyze_job","output":{"response":"...","retrieved_memory":[]}}}
```

## Current Output Shapes

### `analyze_job`

```json
{
  "response": "Generic answer text",
  "retrieved_memory": []
}
```

### `tailor_resume`

```json
{
  "response": "Generic resume-tailoring answer",
  "retrieved_memory": []
}
```

### `draft_message`

```json
{
  "outreach_message": "Optional DM",
  "email_version": "Optional email",
  "retrieved_memory": []
}
```

### `rejected`

```json
{
  "message": "I can only help with job application topics."
}
```
