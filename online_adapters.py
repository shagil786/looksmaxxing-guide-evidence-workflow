"""Online adapters for the looksmaxxing.guide workflow.

Optional dependencies: none. Credentials are read only from environment
variables: BRAVE_SEARCH_API_KEY and OPENAI_API_KEY.
"""
from __future__ import annotations
import json, os, re, time
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from looksmaxxing_workflow import ALLOWLIST, Source, Trace

def _allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWLIST)

class BraveSearch:
    def __init__(self, timeout: int = 8):
        self.api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        self.timeout = timeout
    def search(self, questions: list[str], trace: Trace, limit: int = 5) -> list[Source]:
        if not self.api_key:
            trace.add("research", "search_failed", error="missing BRAVE_SEARCH_API_KEY")
            raise RuntimeError("BRAVE_SEARCH_API_KEY is required for online search")
        query = questions[0]
        try:
            req = Request("https://api.search.brave.com/res/v1/web/search?q=" + quote(query), headers={"Accept":"application/json", "X-Subscription-Token":self.api_key})
            with urlopen(req, timeout=self.timeout) as response: payload = json.load(response)
        except Exception as exc:
            trace.add("research", "search_failed", error=type(exc).__name__)
            raise
        sources = []
        for i, item in enumerate(payload.get("web", {}).get("results", [])):
            url = item.get("url", "")
            if _allowed(url):
                sources.append(Source(item.get("title", "Untitled"), url, urlparse(url).hostname or "", item.get("description", ""), "search_result", "search", f"online-{i}"))
            if len(sources) >= limit: break
        trace.add("research", "searched", mode="online", provider="brave", result_count=len(sources), allowlist=sorted(ALLOWLIST))
        return sources

class TinyFishSearch:
    """Adapter for the TinyFish MCP web-agent result.

    The host agent supplies `run_website`, keeping MCP transport out of the
    domain workflow. Expected result items contain title, url, and snippet.
    """
    def __init__(self, run_website):
        self.run_website = run_website
    def search(self, questions: list[str], trace: Trace, limit: int = 5) -> list[Source]:
        if not callable(self.run_website): raise TypeError("run_website must be callable")
        try:
            result = self.run_website("Search the web for authoritative medical/editorial sources for: " + questions[0])
            items = result.get("results", result) if isinstance(result, dict) else result
            sources = []
            for i, item in enumerate(items[:limit]):
                url = item.get("url", "")
                if _allowed(url):
                    sources.append(Source(item.get("title", "Untitled"), url, urlparse(url).hostname or "", item.get("snippet", item.get("description", "")), "tinyfish_search", "search", f"tinyfish-{i}"))
            trace.add("research", "searched", mode="online", provider="tinyfish", result_count=len(sources), allowlist=sorted(ALLOWLIST))
            return sources
        except Exception as exc:
            trace.add("research", "search_failed", provider="tinyfish", error=type(exc).__name__)
            raise

def fetch_pages(sources: list[Source], trace: Trace, timeout: int = 8) -> list[Source]:
    fetched = []
    for source in sources:
        if not _allowed(source.url): continue
        try:
            req = Request(source.url, headers={"User-Agent":"looksmaxxing-guide-research/0.1"})
            with urlopen(req, timeout=timeout) as response: html = response.read(120_000).decode("utf-8", "ignore")
            text = re.sub(r"<[^>]+>", " ", html); text = re.sub(r"\s+", " ", text).strip()
            fetched.append(Source(source.title, source.url, source.domain, text[:2500], "fetched", source.section, source.chunk_id))
        except Exception as exc:
            trace.add("research", "fetch_failed", url=source.url, error=type(exc).__name__)
    trace.add("research", "fetched", requested=len(sources), returned=len(fetched), max_chars=2500)
    return fetched

class OpenAISmallModel:
    """OpenAI-compatible small-model JSON writer.

    Supports OneRouter/OpenAI-compatible Chat Completions endpoints. The
    provider URL, model, and key are environment-configured only.
    """
    def __init__(self, model: str | None = None, timeout: int = 30):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LOOKSMAXXING_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout
    def write(self, topic: str, sources: list[Source], trace: Trace) -> dict:
        if not self.api_key:
            trace.add("writer", "model_failed", error="missing OPENAI_API_KEY")
            raise RuntimeError("OPENAI_API_KEY is required for the online writer")
        sources = [s for s in sources if _allowed(s.url)][:10]
        context = "\n".join(f"[{i+1}] {s.title} ({s.url})\n{s.excerpt}" for i, s in enumerate(sources))
        schema = {"type":"object", "properties":{"title":{"type":"string"},"summary":{"type":"string"},"sections":{"type":"array","items":{"type":"object","properties":{"heading":{"type":"string"},"body":{"type":"string"}},"required":["heading","body"],"additionalProperties":False}},"faqs":{"type":"array","items":{"type":"object","properties":{"q":{"type":"string"},"a":{"type":"string"}},"required":["q","a"],"additionalProperties":False}}},"required":["title","summary","sections","faqs"],"additionalProperties":False}
        payload = {"model":self.model, "messages":[{"role":"system","content":"Write only from the supplied sources. Return valid JSON matching the requested shape. Use inline citations [1], [2]. State uncertainty, avoid diagnosis, and include escalation guidance."},{"role":"user","content":f"Topic: {topic}\nSources:\n{context}"}], "response_format":{"type":"json_object"}, "extra_body":{"provider":{"service_tier":"standard"}}}
        for attempt in range(2):
            try:
                req = Request(self.base_url + "/chat/completions", data=json.dumps(payload).encode(), headers={"Authorization":"Bearer " + self.api_key, "Content-Type":"application/json"})
                with urlopen(req, timeout=self.timeout) as response: data = json.load(response)
                trace.add("writer", "model_call", model=self.model, attempt=attempt + 1, structured=True)
                result = json.loads(data["choices"][0]["message"]["content"])
                valid_sections = isinstance(result.get("sections"), list) and all(isinstance(x, dict) and isinstance(x.get("heading"), str) and isinstance(x.get("body"), str) for x in result["sections"])
                valid_faqs = isinstance(result.get("faqs"), list) and all(isinstance(x, dict) and isinstance(x.get("q"), str) and isinstance(x.get("a"), str) for x in result["faqs"])
                if not (isinstance(result.get("title"), str) and isinstance(result.get("summary"), str) and valid_sections and valid_faqs):
                    raise ValueError("structured response missing required fields")
                return result
            except Exception as exc:
                if attempt == 1:
                    trace.add("writer", "model_failed", error=type(exc).__name__, attempts=2)
                    raise
                time.sleep(0.5)
