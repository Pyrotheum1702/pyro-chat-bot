"""Agent tools. Each is a LangChain @tool returning a plain string for the model.

Tools:
  search_documents(query)  — semantic search over the uploaded knowledge base
  calculator(expression)   — safe arithmetic
  web_search(query)        — public web search (Tavily if configured, else DuckDuckGo)
  ingest_url(url)          — fetch a web page and add it to the knowledge base
"""
from __future__ import annotations

import ast
import logging
import math
import operator
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

from langchain_core.tools import tool

from . import db, rag
from .config import get_settings
from .security import safe_filename

logger = logging.getLogger("ragchat")


# ---------------------------------------------------------------------------
# search_documents
# ---------------------------------------------------------------------------
@tool
def search_documents(query: str) -> str:
    """Search the user's uploaded documents (the knowledge base) for passages
    relevant to QUERY. Use this to answer questions about the uploaded documents."""
    docs = rag.retrieve(query)
    if not docs:
        return "No relevant passages were found in the uploaded documents."
    blocks = []
    for i, d in enumerate(docs):
        src = (d.metadata or {}).get("source", "unknown")
        blocks.append(f"[{i + 1}] (source: {src})\n{d.page_content}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# calculator (safe AST evaluator — no eval())
# ---------------------------------------------------------------------------
_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "log": math.log,
          "log10": math.log10, "sin": math.sin, "cos": math.cos, "tan": math.tan}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numeric literals are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
    raise ValueError("unsupported expression")


def _safe_eval(expression: str):
    return _eval_node(ast.parse(expression, mode="eval").body)


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '2 * (3 + 4) ** 2'.
    Supports + - * / % ** // parentheses and sqrt/abs/round/log/sin/cos/tan and pi/e."""
    try:
        return str(_safe_eval(expression))
    except Exception as e:
        return f"Error: could not evaluate expression ({e})."


# ---------------------------------------------------------------------------
# web_search (Tavily if configured, else DuckDuckGo, else not-configured msg)
# ---------------------------------------------------------------------------
def _web_search(query: str) -> str:
    s = get_settings()
    if s.tavily_api_key:
        try:
            from tavily import TavilyClient

            res = TavilyClient(api_key=s.tavily_api_key).search(query, max_results=5)
            items = res.get("results", [])
            if items:
                return "\n\n".join(
                    f"{r.get('title', '')}\n{r.get('url', '')}\n{r.get('content', '')}"
                    for r in items
                )
        except Exception:
            logger.exception("Tavily search failed; falling back to DuckDuckGo")

    # 2. DuckDuckGo (no key). `ddgs` is the maintained package; fall back to the
    #    old `duckduckgo_search`. Both can fail on some TLS stacks — notably the
    #    macOS system Python built against LibreSSL, which lacks TLS 1.3.
    for modname in ("ddgs", "duckduckgo_search"):
        try:
            mod = __import__(modname, fromlist=["DDGS"])
            with mod.DDGS() as ddg:
                items = list(ddg.text(query, max_results=5))
            if items:
                return "\n\n".join(
                    f"{r.get('title', '')}\n{r.get('href') or r.get('url', '')}\n{r.get('body', '')}"
                    for r in items
                )
        except ImportError:
            continue
        except Exception:
            logger.exception("%s web search failed", modname)
            continue

    # Nothing worked — be honest about *why* so the model doesn't tell the user
    # "the web has no results" when web search is simply unavailable.
    if not s.tavily_api_key:
        return (
            "Web search is unavailable: no TAVILY_API_KEY is configured and the "
            "keyless DuckDuckGo fallback isn't working in this environment. "
            "Set TAVILY_API_KEY to enable web search."
        )
    return "Web search returned no results for this query."


@tool
def web_search(query: str) -> str:
    """Search the public web for current or external information that is NOT in
    the uploaded documents. Returns the top results (title, url, snippet)."""
    return _web_search(query)


# ---------------------------------------------------------------------------
# ingest_url (fetch a web page -> add to the knowledge base)
# ---------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)


def _fetch_url_text(url: str) -> str:
    # http(s) only (basic SSRF guard — see SECURITY.md).
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("only http(s) URLs are allowed")
    req = urllib.request.Request(url, headers={"User-Agent": "rag-chatbot/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read(5_000_000)  # cap at ~5 MB
    text = raw.decode("utf-8", errors="ignore")
    if "html" in ctype.lower() or text.lstrip().startswith("<"):
        parser = _TextExtractor()
        parser.feed(text)
        return "\n".join(parser.parts)
    return text


@tool
def ingest_url(url: str) -> str:
    """Fetch the web page at URL and add its text to the knowledge base so it can
    be searched later with search_documents. URL must be http(s)."""
    s = get_settings()
    try:
        text = _fetch_url_text(url)
    except Exception as e:
        return f"Could not fetch the URL: {e}"
    if not text.strip():
        return "Fetched the URL but found no readable text."

    host = urlparse(url).netloc or "page"
    name = safe_filename(f"{host}.txt")
    dest = s.upload_dir / name
    dest.write_text(text, encoding="utf-8")
    try:
        chunks = rag.ingest_path(str(dest), name)
    except Exception as e:
        logger.exception("ingest_url failed for %s", url)
        return f"Fetched the page but failed to ingest it: {e}"
    db.add_document(name, chunks)
    return (f"Ingested '{name}' from {url} ({chunks} chunks). "
            f"You can now answer questions about it with search_documents.")


ALL_TOOLS = [search_documents, calculator, web_search, ingest_url]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
