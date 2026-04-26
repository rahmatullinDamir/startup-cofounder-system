import json


def safe_json_parse(text):
    try:
        return json.loads(text)

    except Exception:

        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass

    return {
        "error": "invalid_json",
        "raw": text
    }
