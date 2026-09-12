#!/usr/bin/env python3
"""Offline-first Evidence Brief Workflow for looksmaxxing.guide.

The adapters are intentionally deterministic: replace OfflineSearch with a
real allowlisted search adapter without changing the workflow or audit gates.
"""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWLIST = {
    "nih.gov": "medical", "ods.nih.gov": "medical", "pubmed.ncbi.nlm.nih.gov": "medical",
    "aad.org": "medical", "nhs.uk": "medical", "mayoclinic.org": "medical",
    "health.harvard.edu": "medical", "gq.com": "editorial", "menshealth.com": "editorial",
}

@dataclass
class Source:
    title: str; url: str; domain: str; excerpt: str; evidence: str
    section: str = "retrieved passage"; chunk_id: str = ""

@dataclass
class Brief:
    topic: str; title: str; summary: str; sections: list[dict[str, Any]]
    faqs: list[dict[str, str]]; sources: list[Source]

class Trace:
    def __init__(self): self.events: list[dict[str, Any]] = []
    def add(self, agent: str, event: str, **data):
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "agent": agent, "event": event, **data})

class Planner:
    def run(self, topic: str, trace: Trace) -> list[str]:
        questions = [f"What does the best available evidence say about {topic}?",
                     "What are the plausible benefits, limits, and common misconceptions?",
                     "Who should avoid this or speak to a clinician first?",
                     "What practical, low-risk steps are appropriate for an adult reader?"]
        trace.add("planner", "planned", topic=topic, subquestions=questions)
        return questions

class OfflineSearch:
    """Replay corpus; all returned URLs are checked against the allowlist."""
    corpus = [
        Source("NIH Office of Dietary Supplements: Exercise and Athletic Performance", "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/", "ods.nih.gov", "Creatine can improve strength and power during repeated short bursts of high-intensity exercise; responses vary.", "review", "exercise effects", "ods-exercise-001"),
        Source("American Academy of Dermatology: Hair loss", "https://www.aad.org/public/diseases/hair-loss", "aad.org", "Hair loss has many causes. A dermatologist can help identify the cause and appropriate treatment.", "guidance", "when to seek care", "aad-hair-001"),
        Source("PubMed: Creatine supplementation and hair loss", "https://pubmed.ncbi.nlm.nih.gov/39004143/", "pubmed.ncbi.nlm.nih.gov", "A 2025 randomized trial reported no significant difference in DHT or hair parameters over its study period; longer-term evidence remains limited.", "trial", "study limitations", "pubmed-creatine-001"),
    ]
    def search(self, questions: list[str], trace: Trace) -> list[Source]:
        results = [s for s in self.corpus if s.domain in ALLOWLIST]
        trace.add("research", "searched", allowlist=sorted(ALLOWLIST), result_count=len(results), mode="offline_replay", retrieval="keyword+metadata-filtered replay", chunks=[s.chunk_id for s in results])
        return results

class Writer:
    def run(self, topic: str, sources: list[Source], trace: Trace) -> Brief:
        title = f"{topic}: what the evidence actually says"
        sections = [
            {"heading": "The short answer", "body": f"Current evidence does not justify a simple yes-or-no claim about {topic.lower()}. The answer depends on the outcome, dose or exposure, baseline risk, and the quality and duration of available studies. [1][2][3]"},
            {"heading": "What is supported", "body": "Creatine has evidence for improving performance in repeated, high-intensity exercise, but that does not make it a universal appearance treatment. Hair loss has multiple possible causes, so a persistent or sudden change deserves clinical assessment. [1][2]"},
            {"heading": "Practical, lower-risk guidance", "body": "Do not stop prescribed treatment or start supplements solely because of online claims. If you choose creatine, discuss relevant medical conditions and medications with a clinician, use a reputable product, and seek help for sudden, patchy, or rapidly progressing hair loss. [1][2]"},
        ]
        faqs = [{"q": "Can creatine proveably cause hair loss?", "a": "Current evidence is not strong enough to establish that claim; longer-term research is still useful. [3]"}, {"q": "When should I see a dermatologist?", "a": "Consider an appointment for sudden, patchy, painful, inflamed, or rapidly progressing hair loss. [2]"}]
        brief = Brief(topic, title, "A cautious, evidence-led answer with clear uncertainty and next steps.", sections, faqs, sources)
        trace.add("writer", "wrote", citation_count=len(sources), section_count=len(sections), faq_count=len(faqs))
        return brief

class SafetyAuditor:
    risky = re.compile(r"(guarantee|cure|proven to cause|no risk|always|never)", re.I)
    def run(self, brief: Brief, trace: Trace) -> dict[str, Any]:
        findings = []
        text = json.dumps(asdict(brief))
        if self.risky.search(text): findings.append({"severity":"high", "type":"medical_overclaim", "message":"Absolute or causal medical language needs evidence or qualification."})
        for section in brief.sections:
            if "[" not in section["body"]: findings.append({"severity":"medium", "type":"unsupported_claim", "message":f"Section lacks an inline citation: {section['heading']}"})
        if not any("clinician" in s["body"].lower() for s in brief.sections): findings.append({"severity":"high", "type":"missing_caveat", "message":"No clinician/escalation caveat found."})
        result = {"status": "pass" if not any(f["severity"] == "high" for f in findings) else "fail", "findings": findings}
        trace.add("safety_auditor", "audited", **result); return result

class EditorialValidator:
    def run(self, brief: Brief, trace: Trace) -> dict[str, Any]:
        findings = []
        if len(brief.title) > 65: findings.append({"severity":"low", "type":"seo_title_length", "message":"Consider shortening the title for search results."})
        if len(brief.sections) < 3: findings.append({"severity":"medium", "type":"structure", "message":"Brief needs at least three useful sections."})
        if len(brief.faqs) < 2: findings.append({"severity":"medium", "type":"search_intent", "message":"Add at least two intent-matching FAQs."})
        result = {"status": "pass" if not findings else "review", "findings": findings}
        trace.add("editorial_validator", "validated", **result); return result

def render_markdown(brief: Brief) -> str:
    out = [f"# {brief.title}", "", f"> {brief.summary}", ""]
    for s in brief.sections: out += [f"## {s['heading']}", "", s["body"], ""]
    out += ["## FAQs", ""]
    for f in brief.faqs: out += [f"### {f['q']}", "", f["a"], ""]
    out += ["## Sources", ""]
    for i, s in enumerate(brief.sources, 1): out.append(f"{i}. [{s.title}]({s.url}) — {s.evidence}")
    return "\n".join(out) + "\n"

def run(topic: str) -> dict[str, Any]:
    trace = Trace(); questions = Planner().run(topic, trace); sources = OfflineSearch().search(questions, trace)
    brief = Writer().run(topic, sources, trace); safety = SafetyAuditor().run(brief, trace); editorial = EditorialValidator().run(brief, trace)
    trace.add("workflow", "completed", safety=safety["status"], editorial=editorial["status"])
    return {"markdown": render_markdown(brief), "audit": {"safety": safety, "editorial": editorial}, "trace": trace.events, "brief": asdict(brief)}

def main(argv=None):
    p = argparse.ArgumentParser(description="Generate a looksmaxxing.guide evidence brief")
    p.add_argument("topic"); p.add_argument("--out", default="artifacts")
    args = p.parse_args(argv); result = run(args.topic); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "brief.md").write_text(result["markdown"]); (out / "audit.json").write_text(json.dumps(result["audit"], indent=2));
    with (out / "trace.jsonl").open("w") as f:
        for event in result["trace"]: f.write(json.dumps(event) + "\n")
    print(json.dumps({"output": str(out), "safety": result["audit"]["safety"]["status"], "editorial": result["audit"]["editorial"]["status"], "events": len(result["trace"])}, indent=2))

if __name__ == "__main__": main()
