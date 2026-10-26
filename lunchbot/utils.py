"""Utils for lunchbot."""

import hashlib
import logging
import os
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # Loads variables from .env file

logger = logging.getLogger(__name__)

COLORS = {
    "yellow": "\033[93m",
    "green": "\033[92m",
    "red": "\033[91m",
    "end": "\033[0m",
}


def color_text(text: str, color: str):
    """Color text for terminal output."""
    return COLORS[color] + text + COLORS["end"]


def translate_german_food_description_to_english(
    meal_name: str,
    return_prompt_answer: bool = False,
    system_content: str = None,
):
    """Translate a German food description to English.

    Parameters
    ----------
    meal_name : str
        The name of the meal in German.
    return_prompt_answer : bool, optional
        Whether to return the prompt and the answer, by default False
    system_content : str, optional
        The system content to use for the prompt, by default None

    Returns
    -------
    str or tuple
        The answer or a tuple of the prompt and the answer (if return_prompt_answer=True).
    """

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    if system_content is None:
        system_content = (
            "You translate German meal names into English for a menu. "
            "Keep brand or product names unchanged. "
            "Return only the translated meal name, with no notes, alterantive or explanations."
        )


    logger.info(f"System Content: {system_content}")

    completion = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": meal_name},
        ],
        response_format={
            "type":"json_schema",
            "json_schema":{
                "name":"translation",
                "strict":True,
                "schema":{
                    "type":"object",
                    "properties":{"translation":{"type":"string"}},
                    "required":["translation"],
                    "additionalProperties":False,
                }
            }
        }
    )

    response = completion.choices[0].message.content
    translation = json.loads(response)['translation']

    if return_prompt_answer:
        return meal_name, translation

    return translation


def generate_hash(input_string: str):
    """Get the first 20 characters of the SHA256 hash of a string."""
    return hashlib.sha256(input_string.encode()).hexdigest()[:20]
