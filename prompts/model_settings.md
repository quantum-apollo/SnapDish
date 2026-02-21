# SnapDish — Suggested Model Settings (Non-binding)

These are *behavioral* and *quality* tuning suggestions. Exact parameter names can vary by SDK/version.

## Recommended generation settings
- `temperature`: 0.4–0.7 (lower for precise cooking steps)
- `top_p`: 0.9–1.0
- `max_output_tokens`: 600–1200 (raise for full recipes)

## Safety guidance (implementation-agnostic)
- Use a system/developer prompt with explicit refusals + safe redirections.
- Encourage clarification when image recognition is uncertain.
- For food safety: use conservative guidance and suggest a thermometer.

## Response formatting
- If your UI benefits from structure, consider using a JSON schema response format.
- Otherwise, keep headings consistent with the default response format in `chef_marco_system.md`.
