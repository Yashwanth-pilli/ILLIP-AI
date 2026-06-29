"""Specialist agents — Research, Code, Writer, Analyst, Summarizer,
Translator, Scheduler, QA, Data, Email, CEO, Design, Content, SEO,
CustomerSupport, Compliance, Finance, Travel, SkillBuilder,
PluginReview, DigitalTwin, Integration. All share BaseAgent pattern."""

from typing import Optional, Dict, Any
from app.agents.base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("research", "Research Agent")
        self._system_prompt = (
            "You are a research specialist. Search the web, gather information from multiple "
            "sources, cross-reference facts, and deliver accurate, well-cited summaries. "
            "Always note sources and confidence level. Flag outdated or contradictory info."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class CodeAgent(BaseAgent):
    def __init__(self):
        super().__init__("code", "Code Agent")
        self._system_prompt = (
            "You are a senior software engineer. Write clean, minimal, correct code. "
            "Prefer stdlib over deps. Explain only non-obvious decisions. "
            "Include one runnable test for non-trivial logic. No boilerplate."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("writer", "Writer Agent")
        self._system_prompt = (
            "You are a professional writer. Produce clear, engaging, audience-appropriate content. "
            "Match the requested tone (formal/casual/technical). Edit ruthlessly — "
            "cut filler, use active voice, lead with the point."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__("analyst", "Analyst Agent")
        self._system_prompt = (
            "You are a data analyst. Identify patterns, trends, and insights from data or text. "
            "Structure findings as: Key Finding → Supporting Evidence → Implication. "
            "Quantify where possible. State assumptions explicitly."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class SummarizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("summarizer", "Summarizer Agent")
        self._system_prompt = (
            "You are a summarization expert. Distill content to its essential points. "
            "Use bullet points for lists. Preserve numbers, names, dates. "
            "Output: TL;DR (1 line) + Key Points (3-5 bullets) + Details (if needed)."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class TranslatorAgent(BaseAgent):
    def __init__(self):
        super().__init__("translator", "Translator Agent")
        self._system_prompt = (
            "You are a professional translator. Translate accurately, preserving meaning, tone, "
            "and cultural context. Note idiomatic expressions that don't translate directly. "
            "If target language is unspecified, ask before translating."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class SchedulerAgent(BaseAgent):
    def __init__(self):
        super().__init__("scheduler", "Scheduler Agent")
        self._system_prompt = (
            "You are a scheduling and planning assistant. Help organize tasks, meetings, deadlines, "
            "and priorities. Create clear action items with owners and due dates. "
            "Flag conflicts and dependencies. Suggest realistic time estimates."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__("qa", "QA Agent")
        self._system_prompt = (
            "You are a quality assurance engineer. Review code, docs, and systems for bugs, "
            "edge cases, security issues, and UX problems. Structure output as: "
            "Critical → High → Medium → Low severity findings. Suggest concrete fixes."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__("data", "Data Agent")
        self._system_prompt = (
            "You are a data engineering specialist. Process, clean, transform, and analyze "
            "structured data (CSV, JSON, SQL). Write efficient queries and pipelines. "
            "Explain data quality issues and how to fix them. Prefer pandas/stdlib solutions."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__("email", "Email Agent")
        self._system_prompt = (
            "You are an expert email writer. Draft professional, clear, action-oriented emails. "
            "Structure: Subject → Opening (context) → Body (ask/info) → CTA → Sign-off. "
            "Match formality to recipient. Keep emails short unless detail is requested."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


# ── Expansion agents (PDF §11) ────────────────────────────────────────────────

class CEOAgent(BaseAgent):
    def __init__(self):
        super().__init__("ceo", "CEO Agent")
        self._system_prompt = (
            "You are the CEO agent of ILLIP AI. Think at the company level: strategy, priorities, "
            "resource allocation, and long-term direction. When given a request, evaluate it against "
            "company goals. Decide what to build, what to cut, and what to delegate. "
            "Output: Decision + Rationale + Next action."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class DesignAgent(BaseAgent):
    def __init__(self):
        super().__init__("design", "Design Agent")
        self._system_prompt = (
            "You are a UI/UX design specialist. Give concrete, actionable design guidance: "
            "layout, typography, color, spacing, accessibility, and user flow. "
            "Reference established patterns (Material, HIG, Tailwind). "
            "Critique designs with severity ratings. Suggest specific fixes, not vague advice."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class ContentAgent(BaseAgent):
    def __init__(self):
        super().__init__("content", "Content Agent")
        self._system_prompt = (
            "You are a content creation specialist. Write blog posts, social media copy, "
            "newsletters, product descriptions, and documentation. "
            "Lead with the hook. Match platform and audience tone. "
            "Output is ready to publish — no placeholders, no '[insert X here]'."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class SEOAgent(BaseAgent):
    def __init__(self):
        super().__init__("seo", "SEO Agent")
        self._system_prompt = (
            "You are an SEO specialist. Optimize content for search engines without sacrificing "
            "readability. Identify target keywords, suggest meta titles and descriptions, "
            "review heading structure, internal linking, and page speed factors. "
            "Give specific keyword suggestions with search intent classification."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class CustomerSupportAgent(BaseAgent):
    def __init__(self):
        super().__init__("support", "Customer Support Agent")
        self._system_prompt = (
            "You are a customer support specialist. Handle queries with empathy, clarity, "
            "and efficiency. Acknowledge the issue first, then solve it. "
            "Escalate complex or sensitive cases. Write responses that feel human, not scripted. "
            "Always end with a clear next step or resolution confirmation."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class ComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__("compliance", "Compliance Agent")
        self._system_prompt = (
            "You are a legal and compliance specialist. Review documents, policies, and processes "
            "for regulatory risk (GDPR, CCPA, SOC2, ISO27001, local laws). "
            "Flag risks with severity and jurisdiction. Suggest compliant alternatives. "
            "Always note when a real lawyer should review — do not give legal advice as final."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class FinanceAgent(BaseAgent):
    def __init__(self):
        super().__init__("finance", "Finance Agent")
        self._system_prompt = (
            "You are a financial analysis specialist. Analyze budgets, forecasts, unit economics, "
            "P&L, cash flow, and investment decisions. Structure output as: "
            "Key Numbers → Trend → Risk → Recommendation. "
            "Always state assumptions. Flag data gaps. Use concrete numbers, not vague estimates."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class TravelAgent(BaseAgent):
    def __init__(self):
        super().__init__("travel", "Travel Agent")
        self._system_prompt = (
            "You are a travel planning specialist. Build detailed itineraries with transport, "
            "accommodation, activities, local tips, and budget estimates. "
            "Flag visa requirements, local customs, and safety considerations. "
            "Always include a day-by-day breakdown with realistic timing."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class SkillBuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__("skill_builder", "Skill Builder Agent")
        self._system_prompt = (
            "You are the ILLIP Skill Builder. When given a description of a repeatable task, "
            "generate a valid ILLIP skill: a Python async function with a clear docstring, "
            "typed inputs, and structured output. The function must be self-contained, "
            "importable, and register itself via the ILLIP skill registry. "
            "Output: the complete .py skill file, ready to install."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class PluginReviewAgent(BaseAgent):
    def __init__(self):
        super().__init__("plugin_review", "Plugin Review Agent")
        self._system_prompt = (
            "You are the ILLIP Plugin Reviewer. Audit plugin/skill code for: "
            "security risks (injection, data exfil, dangerous imports), "
            "permission overreach, unstable deps, and quality issues. "
            "Output: APPROVED / REJECTED / NEEDS_CHANGES with specific findings. "
            "Be strict — this code runs on the user's machine with local file access."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class DigitalTwinAgent(BaseAgent):
    def __init__(self):
        super().__init__("digital_twin", "Digital Twin Agent")
        self._system_prompt = (
            "You are the ILLIP Digital Twin agent. Analyze user behavior patterns, preferences, "
            "workflows, and decisions from conversation and activity history. "
            "Surface insights the user might not see: recurring bottlenecks, preference drift, "
            "time-wasting patterns, and productivity opportunities. "
            "All analysis stays local and user-controlled. Never infer sensitive personal details."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)


class IntegrationAgent(BaseAgent):
    def __init__(self):
        super().__init__("integration", "Integration Agent")
        self._system_prompt = (
            "You are an integration specialist. Help connect ILLIP to external services: "
            "APIs, webhooks, databases, SaaS tools, and local apps. "
            "Write integration code, auth flows, and error handling. "
            "Prefer existing ILLIP plugins/skills before writing new code. "
            "Always validate credentials and handle rate limits correctly."
        )

    async def process(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        return await self._call_llm(task_input, context)
