import json
from looksmaxxing_workflow import ALLOWLIST, SafetyAuditor, Trace, run

def test_offline_workflow_is_cited_and_safe():
    result = run("Does creatine cause hair loss?")
    assert result["audit"]["safety"]["status"] == "pass"
    assert result["audit"]["editorial"]["status"] == "pass"
    assert len(result["trace"]) == 6
    assert all(source["domain"] in ALLOWLIST for source in result["brief"]["sources"])
    assert "## FAQs" in result["markdown"] and "## Sources" in result["markdown"]

def test_seeded_defect_is_detected():
    result = run("Does creatine cause hair loss?")
    result["brief"]["sections"][0]["body"] = "Creatine is guaranteed to cause hair loss."
    # A seeded defect gives us a small, measurable regression check for the safety gate.
    from looksmaxxing_workflow import Brief, Source
    brief = Brief(**result["brief"])
    audit = SafetyAuditor().run(brief, Trace())
    assert audit["status"] == "fail"
    assert any(f["type"] == "medical_overclaim" for f in audit["findings"])
    assert json.loads(json.dumps(result["audit"]))
