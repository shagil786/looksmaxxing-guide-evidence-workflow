#!/usr/bin/env python3
"""Fast independent-style evaluation for the offline evidence workflow."""
from looksmaxxing_workflow import ALLOWLIST, Brief, SafetyAuditor, Trace, run

def evaluate() -> dict:
    result = run("Does creatine cause hair loss?")
    brief = result["brief"]
    checks = {
        "all_sources_allowlisted": all(s["domain"] in ALLOWLIST for s in brief["sources"]),
        "all_sections_cited": all("[" in s["body"] for s in brief["sections"]),
        "faqs_present": len(brief["faqs"]) >= 2,
        "trace_has_all_agents": {e["agent"] for e in result["trace"]} >= {"planner", "research", "writer", "safety_auditor", "editorial_validator"},
        "clean_brief_passes": result["audit"]["safety"]["status"] == "pass" and result["audit"]["editorial"]["status"] == "pass",
    }
    defect = dict(brief)
    defect["sections"] = [dict(brief["sections"][0], body="This is guaranteed to work and has no risk.")]
    defect["sections"] += [dict(s) for s in brief["sections"][1:]]
    defect_audit = SafetyAuditor().run(Brief(**defect), Trace())
    checks["seeded_overclaim_fails"] = defect_audit["status"] == "fail"
    return {"passed": sum(checks.values()), "total": len(checks), "checks": checks}

if __name__ == "__main__":
    import json
    report = evaluate()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
