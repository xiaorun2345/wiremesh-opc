from datetime import datetime, timedelta

from app.services.lead_radar import LeadCandidate, score_candidate


def test_wire_mesh_lead_scores_high_with_complete_specs():
    candidate = LeadCandidate(
        source="ted",
        external_id="TED-1",
        title="Supply of anti-climb wire-mesh fencing",
        buyer="Public Buyer",
        country="Malta",
        deadline_at=datetime.utcnow() + timedelta(days=20),
        budget=100000,
        text="wire-mesh fencing, galvanized steel, wire diameter 3.5mm, mesh size 50x50mm, size 2x3m, quantity 100 pcs, hot dip galvanized",
    )
    score, reasons, extracted = score_candidate(candidate, {"countries": ["Malta"]})
    assert score >= 80
    assert extracted["spec"]["product_type"] == "fence_mesh"
    assert any("官方采购来源" in reason for reason in reasons)


def test_expired_lead_is_archived_score():
    candidate = LeadCandidate(
        source="rss", external_id="expired", title="wire mesh", deadline_at=datetime.utcnow() - timedelta(days=1), text="wire mesh"
    )
    score, reasons, _ = score_candidate(candidate, {})
    assert score == 0
    assert "已过截止日期" in reasons
