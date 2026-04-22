import os

from groq import Groq


def generate_completion(
    prompt: str,
    system_prompt: str = "You are a sales intelligence assistant.",
    temperature: float = 0.7,
    max_tokens: int = 500,
    max_completion_tokens: int | None = None,
) -> str:
    api_key = str(os.getenv("GROQ_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured. Please set a valid key in backend .env.")

    model = str(os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")).strip() or "llama-3.1-8b-instant"
    token_limit = int(max_completion_tokens if max_completion_tokens is not None else max_tokens)

    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
        max_tokens=token_limit,
    )

    message = chat_completion.choices[0].message
    content = message.content if message else ""
    return str(content or "")
