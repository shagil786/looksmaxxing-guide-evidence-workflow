#!/usr/bin/env python3
"""Run the online TinyFish -> OneRouter -> audit workflow."""
import argparse, json, subprocess
from looksmaxxing_workflow import Brief, EditorialValidator, Planner, SafetyAuditor, Trace, render_markdown
from online_adapters import OpenAISmallModel, TinyFishSearch, fetch_pages

def tinyfish_search(prompt: str):
    raw = subprocess.check_output(["npx", "-y", "@tiny-fish/cli@latest", "search", "query", prompt, "--include-domains", "nih.gov,ods.nih.gov,pubmed.ncbi.nlm.nih.gov,aad.org,nhs.uk,mayoclinic.org,health.harvard.edu,gq.com,menshealth.com"], text=True, timeout=60)
    return json.loads(raw)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("topic"); parser.add_argument("--out", default="online-artifacts")
    args = parser.parse_args(); trace = Trace(); questions = Planner().run(args.topic, trace)
    sources = TinyFishSearch(tinyfish_search).search(questions, trace); sources = fetch_pages(sources, trace)
    model = OpenAISmallModel(); data = model.write(args.topic, sources, trace)
    brief = Brief(args.topic, data["title"], data["summary"], data["sections"], data["faqs"], sources)
    audit = {"safety": SafetyAuditor().run(brief, trace), "editorial": EditorialValidator().run(brief, trace)}
    from pathlib import Path
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True); (out / "brief.md").write_text(render_markdown(brief)); (out / "audit.json").write_text(json.dumps(audit, indent=2));
    with (out / "trace.jsonl").open("w") as f:
        for event in trace.events: f.write(json.dumps(event) + "\n")
    print(json.dumps({"output": str(out), "safety": audit["safety"]["status"], "editorial": audit["editorial"]["status"], "sources": len(sources)}, indent=2))

if __name__ == "__main__": main()
