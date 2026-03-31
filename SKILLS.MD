## Frontend

- Framework: Next.js (App Router) with TypeScript
- Styling: Tailwind CSS


### Chat Experience
- Every new chat session must open with a unique ID
- Left sidebar must list full chat history, same pattern as standard chat applications
- Chat history persists via PostgreSQL — same db used by the backend

### Research Results Display
- Tavily results must never be rendered in raw format
- Each source renders as a clean card showing: title, URL, and summary only
- No raw delimiters, no XML-style tags, no key_excerpts blocks, no separator lines

