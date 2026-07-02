"""
ResearchAgent — Perplexity-style deep research.

Flow:
  1. Decompose query into 3-5 sub-questions (LLM)
  2. Parallel SearXNG searches for each sub-question
  3. Parallel page fetch for top N results per search
  4. LLM synthesizes all content into answer with citations
  5. Each step streams progress via async generator
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncGenerator

from app.utils import logger


@dataclass
class ResearchStep:
    type: str          # "decompose" | "search" | "read" | "synthesize" | "done" | "error"
    message: str = ""
    data: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        import json
        payload = {"type": self.type, "message": self.message, "data": self.data}
        return f"data: {json.dumps(payload)}\n\n"


@dataclass
class ResearchResult:
    answer: str
    sources: list[dict]        # [{url, title, snippet}]
    sub_questions: list[str]
    steps_taken: int


class ResearchAgent:
    name = "research"
    MAX_SOURCES_PER_QUERY = 3
    MAX_SUBQUESTIONS = 4
    MAX_TEXT_PER_PAGE = 2500

    async def research(
        self,
        query: str,
        depth: str = "standard",   # "quick" | "standard" | "deep"
    ) -> AsyncGenerator[ResearchStep, None]:
        """
        Async generator — yields ResearchStep at each stage.
        Caller collects final "done" step for full result.
        """
        from app.services.chat_service import get_llm
        from app.services.search_service import web_search as search
        from app.services.browser_service import fetch_pages_parallel

        llm = get_llm()

        # ── Step 1: Decompose query ────────────────────────────────────────
        yield ResearchStep("decompose", f"Breaking down: {query}")

        n_sub = {"quick": 2, "standard": 3, "deep": self.MAX_SUBQUESTIONS}.get(depth, 3)
        sub_questions = await self._decompose(llm, query, n_sub)
        yield ResearchStep("decompose", f"Generated {len(sub_questions)} sub-questions", {"questions": sub_questions})

        # ── Step 2: Parallel searches ──────────────────────────────────────
        yield ResearchStep("search", f"Searching {len(sub_questions)} angles in parallel...")

        search_results = await asyncio.gather(
            *[self._search_one(q) for q in sub_questions],
            return_exceptions=True,
        )

        all_urls: list[str] = []
        url_to_query: dict[str, str] = {}
        for q, result in zip(sub_questions, search_results):
            if isinstance(result, list):
                for item in result[:self.MAX_SOURCES_PER_QUERY]:
                    url = item.get("url", "")
                    if url and url not in all_urls:
                        all_urls.append(url)
                        url_to_query[url] = q

        yield ResearchStep("search", f"Found {len(all_urls)} sources to read", {"urls": all_urls})

        # ── Step 3: Parallel page reads ────────────────────────────────────
        if not all_urls:
            yield ResearchStep("error", "No search results found. Try different query.")
            return

        max_pages = {"quick": 3, "standard": 6, "deep": 12}.get(depth, 6)
        urls_to_fetch = all_urls[:max_pages]

        yield ResearchStep("read", f"Reading {len(urls_to_fetch)} pages in parallel...")
        pages = await fetch_pages_parallel(urls_to_fetch, max_concurrent=4)

        ok_pages = [p for p in pages if p.ok]
        yield ResearchStep("read", f"Successfully read {len(ok_pages)}/{len(urls_to_fetch)} pages")

        if not ok_pages:
            # Fall back to search snippets only
            yield ResearchStep("read", "Using search snippets only (pages blocked)", {})

        # ── Step 4: Synthesize ─────────────────────────────────────────────
        yield ResearchStep("synthesize", "Synthesizing answer from all sources...")

        sources_text = self._build_sources_context(ok_pages, url_to_query)
        answer = await self._synthesize(llm, query, sub_questions, sources_text)

        sources = [
            {
                "url": p.url,
                "title": p.title or p.url,
                "snippet": p.text[:200].strip(),
            }
            for p in ok_pages
        ]

        yield ResearchStep("done", "Research complete", {
            "answer": answer,
            "sources": sources,
            "sub_questions": sub_questions,
            "steps_taken": len(sub_questions) + len(urls_to_fetch) + 2,
        })

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _decompose(self, llm, query: str, n: int) -> list[str]:
        prompt = (
            f"Break this research query into {n} specific sub-questions that together cover it fully.\n"
            f"Query: {query}\n\n"
            f"Reply with ONLY a JSON array of {n} strings. No explanation."
        )
        try:
            response = await llm.complete(prompt)
            text = response.strip()
            # Extract JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                questions = json.loads(text[start:end])
                return [str(q) for q in questions[:n]]
        except Exception as e:
            logger.warning(f"Decompose failed: {e}, using original query")
        return [query]

    async def _search_one(self, query: str) -> list[dict]:
        try:
            from app.services.search_service import web_search as search
            results = await search(query)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"Search failed for '{query}': {e}")
            return []

    def _build_sources_context(self, pages, url_to_query: dict) -> str:
        parts = []
        for i, page in enumerate(pages, 1):
            text = page.text[:self.MAX_TEXT_PER_PAGE]
            parts.append(
                f"[Source {i}] {page.title or page.url}\nURL: {page.url}\n{text}\n"
            )
        return "\n---\n".join(parts)

    async def _synthesize(self, llm, query: str, sub_questions: list[str], sources: str) -> str:
        prompt = (
            f"You are a research assistant. Synthesize the sources below into a comprehensive answer.\n\n"
            f"Main question: {query}\n"
            f"Sub-questions covered: {'; '.join(sub_questions)}\n\n"
            f"SOURCES:\n{sources}\n\n"
            f"Write a clear, well-structured answer. "
            f"Reference sources by number [1], [2] etc. "
            f"Be factual. If sources conflict, note it."
        )
        try:
            return await llm.complete(prompt)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Research gathered {len(sources)} sources but synthesis failed: {e}"


_agent: ResearchAgent | None = None


def get_research_agent() -> ResearchAgent:
    global _agent
    if _agent is None:
        _agent = ResearchAgent()
    return _agent
