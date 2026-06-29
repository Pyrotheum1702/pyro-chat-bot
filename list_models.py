#!/usr/bin/env python3
"""List models available for use with LangChain, per provider.

For each provider this queries the provider's *live* models endpoint (rather than
hardcoding a list that goes stale) and prints the model IDs alongside the
LangChain chat class you'd use to call them.

Providers covered:
  - anthropic  (Claude)        -> langchain_anthropic.ChatAnthropic
  - openai     (GPT / o-series)-> langchain_openai.ChatOpenAI
  - google     (Gemini)        -> langchain_google_genai.ChatGoogleGenerativeAI
  - fireworks  (open models)   -> langchain_fireworks.ChatFireworks
  - ollama     (local models)  -> langchain_ollama.ChatOllama

Each provider degrades gracefully: if its SDK isn't installed or its API key
isn't set, that provider is skipped with a one-line reason instead of crashing.

Env vars read:
  ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY (or GEMINI_API_KEY),
  FIREWORKS_API_KEY.
  Ollama needs no key; it reads OLLAMA_HOST (default http://localhost:11434).

A .env file in this folder is auto-loaded, so `cp .env.example .env` and filling
in your keys is enough — no need to `export` them. (Real env vars still win.)

Usage:
  python list_models.py                # all providers
  python list_models.py --provider anthropic
  python list_models.py --json         # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def load_dotenv(path: str | None = None) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no dependency).

    Looks for a .env next to this script by default. Real environment
    variables take precedence, so an exported key always wins over the file.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            line = line.removeprefix("export ").strip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")  # drop optional quotes
            if key and key not in os.environ:  # don't clobber real env vars
                os.environ[key] = value


# Each provider returns a list of model-id strings. A provider raises
# ProviderUnavailable (with a human reason) when it can't run, so the caller
# can skip it cleanly.
class ProviderUnavailable(Exception):
    """Raised when a provider can't be queried (missing SDK or API key)."""


def list_anthropic() -> list[str]:
    """Claude models via the Anthropic Models API (auto-paginates)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ProviderUnavailable("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError:
        raise ProviderUnavailable("pip install anthropic")

    client = anthropic.Anthropic()
    # Iterating the list result auto-paginates across all pages.
    return [m.id for m in client.models.list()]


def list_openai() -> list[str]:
    """OpenAI chat-capable models (filtered heuristically from /v1/models)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ProviderUnavailable("OPENAI_API_KEY not set")
    try:
        from openai import OpenAI
    except ImportError:
        raise ProviderUnavailable("pip install openai")

    client = OpenAI()
    ids = [m.id for m in client.models.list().data]
    # /v1/models returns embeddings, audio, image models too — keep the ones
    # usable as chat models. Heuristic, not authoritative.
    chat = lambda mid: (mid.startswith(("gpt", "o1", "o3", "o4", "chatgpt"))
                        and not any(x in mid for x in
                                    ("embedding", "audio", "realtime",
                                     "transcribe", "tts", "image", "moderation")))
    return sorted(m for m in ids if chat(m))


def list_google() -> list[str]:
    """Gemini models that support text generation (generateContent)."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ProviderUnavailable("GOOGLE_API_KEY / GEMINI_API_KEY not set")
    try:
        import google.generativeai as genai
    except ImportError:
        raise ProviderUnavailable("pip install google-generativeai")

    genai.configure(api_key=key)
    return [m.name.removeprefix("models/")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods]


def list_fireworks() -> list[str]:
    """Fireworks AI serverless models via its OpenAI-compatible /v1/models.

    No SDK required — it's a plain REST GET with a Bearer token. Lists the
    models available to your account (open-weight: Llama, Qwen, Mixtral, ...).
    """
    key = os.getenv("FIREWORKS_API_KEY")
    if not key:
        raise ProviderUnavailable("FIREWORKS_API_KEY not set")
    url = "https://api.fireworks.ai/inference/v1/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except Exception as e:  # auth failure, network error, etc.
        raise ProviderUnavailable(f"Fireworks API error ({e.__class__.__name__})")
    # IDs look like "accounts/fireworks/models/llama-v3p1-70b-instruct".
    return sorted(m["id"] for m in data.get("data", []))


def list_ollama() -> list[str]:
    """Models already pulled into a local Ollama instance (no API key)."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as resp:
            data = json.load(resp)
    except Exception as e:  # connection refused, timeout, etc.
        raise ProviderUnavailable(f"no Ollama at {host} ({e.__class__.__name__})")
    return sorted(m["name"] for m in data.get("models", []))


# provider key -> (lister, LangChain class, pip package, import line)
PROVIDERS = {
    "anthropic": (list_anthropic, "ChatAnthropic", "langchain-anthropic",
                  "from langchain_anthropic import ChatAnthropic"),
    "openai": (list_openai, "ChatOpenAI", "langchain-openai",
               "from langchain_openai import ChatOpenAI"),
    "google": (list_google, "ChatGoogleGenerativeAI", "langchain-google-genai",
               "from langchain_google_genai import ChatGoogleGenerativeAI"),
    "fireworks": (list_fireworks, "ChatFireworks", "langchain-fireworks",
                  "from langchain_fireworks import ChatFireworks"),
    "ollama": (list_ollama, "ChatOllama", "langchain-ollama",
               "from langchain_ollama import ChatOllama"),
}


def collect(selected: list[str]) -> dict:
    """Run the selected providers; return {provider: {...result...}}."""
    out: dict[str, dict] = {}
    for key in selected:
        lister, cls, pkg, imp = PROVIDERS[key]
        try:
            models = lister()
            out[key] = {"ok": True, "langchain_class": cls, "pip": pkg,
                        "import": imp, "models": models}
        except ProviderUnavailable as e:
            out[key] = {"ok": False, "reason": str(e)}
    return out


def print_human(results: dict) -> None:
    for key, r in results.items():
        cls = PROVIDERS[key][1]
        header = f"{key}  ({cls})"
        print(f"\n{header}\n{'-' * len(header)}")
        if not r["ok"]:
            print(f"  skipped: {r['reason']}")
            continue
        if not r["models"]:
            print("  (no models returned)")
            continue
        for mid in r["models"]:
            print(f"  {mid}")
        print(f"\n  use:  {r['import']}")
        print(f"        llm = {cls}(model=\"{r['models'][0]}\")")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=[*PROVIDERS, "all"], default="all",
                    help="which provider to query (default: all)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    load_dotenv()  # pick up keys from a local .env if present

    selected = list(PROVIDERS) if args.provider == "all" else [args.provider]
    results = collect(selected)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_human(results)
        any_ok = any(r["ok"] for r in results.values())
        if not any_ok:
            print("\nNo providers were reachable. Set an API key (e.g. "
                  "ANTHROPIC_API_KEY) or start Ollama, then re-run.",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
