# Frontend

## Stack

The frontend is a Streamlit app located in `/Users/sameet/Documents/Projects/applygraph/frontend`.

It is intentionally lightweight and Python-only.

## UX Model

The app behaves like a session-based chat client:

- multiple chat threads in the sidebar
- one uploaded resume per session
- stage-by-stage streaming progress
- rendered backend response in the main pane
- thumbs up / thumbs down feedback per assistant response

## Session Behavior

The frontend creates sessions through the backend.

Important behavior:

- clicking `New chat` reuses an existing empty session instead of creating duplicates
- switching sessions loads that session’s messages and resume metadata
- deleting a session removes it from the backend and updates the sidebar

## Resume Handling

Resume flow:

1. user uploads PDF
2. frontend extracts text locally
3. extracted text is saved to the selected backend session
4. every future prompt in that session implicitly uses that resume

This keeps the chat payload small:

- only `session_id`
- only current user message

The backend injects resume context from the session.

## Rendering Behavior

Current response rendering:

- `analyze_job` -> render `output.response`
- `tailor_resume` -> render `output.response`
- `draft_message` -> render DM/email sections if present
- `rejected` -> render error message

## Files

- `/Users/sameet/Documents/Projects/applygraph/frontend/app.py` - Streamlit entrypoint
- `/Users/sameet/Documents/Projects/applygraph/frontend/ui.py` - UI composition
- `/Users/sameet/Documents/Projects/applygraph/frontend/rendering.py` - backend response rendering
- `/Users/sameet/Documents/Projects/applygraph/frontend/services/api.py` - backend API calls
- `/Users/sameet/Documents/Projects/applygraph/frontend/services/pdf.py` - PDF extraction
- `/Users/sameet/Documents/Projects/applygraph/frontend/state.py` - Streamlit session-state helpers
- `/Users/sameet/Documents/Projects/applygraph/frontend/models.py` - typed frontend models
