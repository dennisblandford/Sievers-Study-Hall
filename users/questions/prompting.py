import os
import json

from flask import current_app

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError
from huggingface_hub.errors import BadRequestError

from data.data_processing.exercises import get_level_from_exercise
from users.session_management.logging import log_prompt_usage

response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "exercise_feedback",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "inquiry_correct": {
                    "type": "string",
                    "enum": ["yes", "no"]
                },
                "meaning_coherent": {
                    "type": "string",
                    "enum": ["yes", "no"]
                },
                "german_sentence": {
                    "type": "string"
                },
                "translation": {
                    "type": "string"
                },
                "cefr_level": {
                    "type": "string",
                },
                "commentary": {
                    "type": "string"
                }
            },
            "required": [
                "inquiry_correct",
                "meaning_coherent",
                "german_sentence",
                "translation",
                "cefr_level",
                "commentary",
            ],
            "additionalProperties": False
        }
    }
}

model = {
    'A1': 'openai/gpt-oss-120b',
    'A2': 'openai/gpt-oss-120b',
    'B1': 'openai/gpt-oss-120b',
    'B2': 'openai/gpt-oss-120b',
    'C1': 'openai/gpt-oss-120b',
    'C2': 'openai/gpt-oss-120b',
}

# The client is cheap to build but holds an HTTP session; reuse one per worker.
_CLIENT = None

# Bounded cache of successful grading responses. Prompt exercises are graded by
# a remote model, which dominates the request time; identical submissions (e.g.
# a user retrying the same sentence) can be answered without another round trip.
_PROMPT_CACHE = {}
_PROMPT_CACHE_MAX = 256


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = InferenceClient(
            api_key=os.environ["HF_TOKEN"],
            provider="groq",
            timeout=60.0,
        )
    return _CLIENT


def get_response_from_prompt(unit, exercise, prompt):
    key = (unit, exercise, prompt)

    cached = _PROMPT_CACHE.get(key)
    if cached is not None:
        return cached

    result = _request_from_prompt(unit, exercise, prompt)

    # Only cache successful (dict) responses; transient failures should be
    # retried on the next submission.
    if isinstance(result, dict):
        if len(_PROMPT_CACHE) >= _PROMPT_CACHE_MAX:
            _PROMPT_CACHE.pop(next(iter(_PROMPT_CACHE)))
        _PROMPT_CACHE[key] = result

    return result


def _request_from_prompt(unit, exercise, prompt):
    client = _get_client()

    level = get_level_from_exercise(unit, exercise)

    def make_request(temperature):
        response = client.chat.completions.create(
            model=model[level],
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=temperature,
            max_tokens=1000,
            response_format=response_format,
            extra_body={
                "reasoning_effort": "low"
            }
        )

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        usage= response.usage

        log_prompt_usage(unit, exercise, input_tokens, output_tokens, usage)

        return json.loads(response.choices[0].message.content)

    try:
        try:
            return make_request(temperature=0.7)

        except BadRequestError as e:
            if "json_validate_failed" not in str(e):
                raise

            # Retry once
            return make_request(temperature=0.2)

    except BadRequestError as e:
        if "json_validate_failed" not in str(e):
            raise
        return None

    except HfHubHTTPError as e:
        if e.response is not None and e.response.status_code == 503:
            current_app.logger.warning("Hugging Face/Groq unavailable: %s", e)
            return None
        raise

