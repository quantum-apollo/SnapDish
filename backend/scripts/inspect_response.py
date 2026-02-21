import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()  # loads repo-root .env in this workspace
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)

    model_id = os.environ.get("SNAPDISH_MODEL", "gpt-5.2")

    resp = client.responses.create(
        model=model_id,
        input=[
            {"role": "developer", "content": "Return JSON with key hello (string)."},
            {"role": "user", "content": "Say hi"},
        ],
        store=False,
        text={"format": {"type": "json_object"}},
        max_output_tokens=100,
    )

    logging.info(f"output_text: {repr(getattr(resp, 'output_text', None))}")
    logging.info(f"output: {resp.output}")


if __name__ == "__main__":
    main()
