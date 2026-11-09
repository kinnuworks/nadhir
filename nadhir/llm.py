"""Model calls, with recording so every run can be replayed exactly without the model.

NADHIR_LLM=auto (default): use a recording if one exists, else call the API.
NADHIR_LLM=replay: recordings only (CI and the hosted demo's replay tables).
NADHIR_LLM=live: always call the API (and record).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Local runs read the key from a .env file in the repo root (never committed).
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
REC_DIR = Path(os.environ.get("NADHIR_RECORDINGS", ROOT / "runs" / "recordings"))
MODEL = os.environ.get("NADHIR_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("NADHIR_EFFORT", "medium")
# The institution reviewers run on a different model from the drafter, so the two don't share blind spots.
REVIEW_MODEL = os.environ.get("NADHIR_REVIEW_MODEL", "claude-sonnet-5-5")


class ModelError(RuntimeError):
    pass


def _key(model, system, user, schema, salt):
    blob = json.dumps({"m": model, "s": system, "u": user, "f": schema, "salt": salt}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def call_json(system: str, user: str, schema: dict, *, salt: str = "", mode: str | None = None,
              effort: str | None = None, model: str | None = None) -> tuple[dict, dict]:
    """Ask the model for JSON that matches `schema`. Returns (data, meta).

    `salt` separates repeated runs of the same prompt (run 1, 2, 3) so each has its own recording.
    """
    mode = mode or os.environ.get("NADHIR_LLM", "auto")
    model = model or MODEL
    key = _key(model, system, user, schema, salt)
    path = REC_DIR / f"{key}.json"
    if mode in ("auto", "replay") and path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec["data"], {**rec["meta"], "recording": path.name, "replayed": True}
    if mode == "replay":
        raise ModelError(f"no recording {path.name} (run with NADHIR_LLM=live to create it)")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ModelError("Live drafting is switched off on this copy (no API key is set). "
                         "The prefilled example still works: it replays a recorded answer.")
    import anthropic
    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort or EFFORT, "format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.RateLimitError as e:
        raise ModelError("the model is busy (rate limit); try again in a minute") from e
    except anthropic.APIStatusError as e:
        raise ModelError(f"model API error {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise ModelError("could not reach the model API") from e
    if resp.stop_reason == "refusal":
        raise ModelError("the model declined this request")
    if resp.stop_reason == "max_tokens":
        raise ModelError("the model's answer was cut off")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    meta = {"model": resp.model, "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if os.environ.get("NADHIR_RECORD", "1") == "1":
        try:
            REC_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"key": key, "system": system, "user": user, "schema": schema,
                                        "data": data, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass  # read-only file system on the hosted demo
    return data, {**meta, "recording": path.name, "replayed": False}
