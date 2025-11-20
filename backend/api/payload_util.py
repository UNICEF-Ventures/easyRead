import json

def get_json_payload(request):
    """
    Unified way to get JSON payload that works:
      - Locally with DRF (request.data populated)
      - On Lambda with Mangum (request.body populated, request.data empty)

    IMPORTANT: use this instead of touching request.data / request.body directly.
    """

    # 1) If this is a DRF Request and data is already parsed, use it
    data = getattr(request, "data", None)
    if data not in (None, {}, []):
        return data

    # 2) Otherwise, fall back to raw body (Lambda case)
    #    Make sure this runs BEFORE anything else touches request.body.
    if request.method in ("POST", "PUT", "PATCH"):
        raw = request.body  # in Lambda this should be safe & available
        if not raw:
            return {}

        try:
            # Decode & parse JSON; adjust if you accept other encodings
            return json.loads(raw.decode(request.encoding or "utf-8"))
        except (ValueError, UnicodeDecodeError):
            # Not JSON or bad encoding – return empty or handle as needed
            return {}

    return {}
