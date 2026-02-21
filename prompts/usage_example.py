import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
import os
from openai import OpenAI


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)

    system_prompt = load_text("prompts/chef_marco_system.md")

    user_text = "I have tomatoes, garlic, olive oil, and pasta. Make dinner for 2 in 20 minutes."

    resp = client.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        # Optional tuning:
        # temperature=0.6,
    )

    logging.info(resp.output_text)


if __name__ == "__main__":
    main()
