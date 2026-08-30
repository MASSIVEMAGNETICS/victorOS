import pytest

from vos_core.resonance_ledger import ResonanceLedger


def make_ledger(tmp_path):
    return ResonanceLedger(tmp_path / "resonance.db")


def test_ingest_hash_chain_and_verify(tmp_path):
    with make_ledger(tmp_path) as ledger:
        sid = ledger.ingest_text(
            "Evidence requires provenance.",
            title="episode-a",
            domains=["VictorOS", "Ethica A.I."],
            author="human",
        )
        assert sid.startswith("SRC-")
        report = ledger.verify_integrity()
        assert report["ok"] is True
        assert report["sources"] == 1
        assert report["events"] >= 1


def test_exact_duplicate_source_is_deduplicated(tmp_path):
    with make_ledger(tmp_path) as ledger:
        a = ledger.ingest_text("same evidence", source_type="episode")
        b = ledger.ingest_text("same evidence", source_type="episode")
        assert a == b
        assert ledger.verify_integrity()["sources"] == 1


def test_heuristic_extract_never_claims_verified_truth(tmp_path):
    text = """
    Provenance preserves evidence lineage. Provenance preserves causal history.
    Evidence lineage supports continuity. Evidence lineage must remain inspectable.
    """
    with make_ledger(tmp_path) as ledger:
        sid = ledger.ingest_text(text, domains=["victoros"])
        extracted = ledger.extract(sid, max_concepts=8)
        assert extracted
        assert all(item["evidence_state"] == "EXTRACTED" for item in extracted)
        states = {
            row["evidence_state"]
            for row in ledger.conn.execute("SELECT evidence_state FROM observations")
        }
        assert states == {"EXTRACTED"}


def test_repeated_cross_domain_evidence_can_form_nodal_candidate(tmp_path):
    with make_ledger(tmp_path) as ledger:
        for idx, domain in enumerate(["victoros", "music", "business"]):
            sid = ledger.ingest_text(
                f"episode {idx}: provenance and continuity",
                title=f"ep-{idx}",
                domains=[domain],
            )
            ledger.record_observation(
                "provenance", sid, "provenance", confidence=1.0, evidence_state="VERIFIED"
            )
            ledger.record_observation(
                "continuity", sid, "continuity", confidence=1.0, evidence_state="VERIFIED"
            )
        ledger.link("provenance", "SUPPORTS", "continuity", confidence=1.0, status="verified")
        ledger.link("continuity", "DEPENDS_ON", "provenance", confidence=1.0, status="verified")
        rows = {row.concept: row for row in ledger.scan()}
        assert rows["provenance"].resonance_score >= 0.45
        assert rows["provenance"].classification == "NODAL_INVARIANT_CANDIDATE"


def test_resonance_is_not_truth_confidence(tmp_path):
    with make_ledger(tmp_path) as ledger:
        for idx, domain in enumerate(["a", "b", "c"]):
            sid = ledger.ingest_text(f"repeated disputed claim {idx}", domains=[domain])
            ledger.record_observation(
                "repeated disputed claim",
                sid,
                "repeated disputed claim",
                confidence=1.0,
                evidence_state="DISPUTED",
                interpretation_state="reported_claim",
            )
        ledger.link("repeated disputed claim", "SUPPORTS", "discussion importance")
        rows = {row.concept: row for row in ledger.scan()}
        claim = rows["repeated disputed claim"]
        assert claim.persistence > 0.8
        assert claim.evidence_quality <= 0.35
        assert claim.resonance_score < 0.45


def test_contradiction_pressure_is_preserved_not_averaged_away(tmp_path):
    with make_ledger(tmp_path) as ledger:
        sid = ledger.ingest_text("A conflicts with B", domains=["test"])
        ledger.record_observation("claim a", sid, "A", confidence=0.9, evidence_state="OBSERVED")
        ledger.record_observation("claim b", sid, "B", confidence=0.9, evidence_state="OBSERVED")
        ledger.link("claim a", "CONTRADICTS", "claim b", source_id=sid, confidence=1.0)
        rows = {row.concept: row for row in ledger.scan()}
        assert rows["claim a"].contradiction_pressure > 0
        assert rows["claim b"].contradiction_pressure > 0


def test_source_tamper_is_detected(tmp_path):
    db = tmp_path / "resonance.db"
    with ResonanceLedger(db) as ledger:
        sid = ledger.ingest_text("original source")
        ledger.conn.execute("UPDATE sources SET raw_text = 'tampered' WHERE source_id = ?", (sid,))
        ledger.conn.commit()
        report = ledger.verify_integrity()
        assert report["ok"] is False
        assert sid in report["source_hash_errors"]


def test_event_chain_tamper_is_detected(tmp_path):
    db = tmp_path / "resonance.db"
    with ResonanceLedger(db) as ledger:
        ledger.ingest_text("source one")
        ledger.ingest_text("source two")
        ledger.conn.execute("UPDATE events SET payload_json = '{}' WHERE seq = 1")
        ledger.conn.commit()
        report = ledger.verify_integrity()
        assert report["ok"] is False
        assert 1 in report["event_chain_errors"]


def test_history_returns_provenance(tmp_path):
    with make_ledger(tmp_path) as ledger:
        sid = ledger.ingest_text("signal seed carries lineage", title="song", domains=["music"])
        ledger.record_observation(
            "signal seed",
            sid,
            "signal seed carries lineage",
            confidence=0.95,
            evidence_state="SOURCE_BOUND",
        )
        history = ledger.history("signal seed")
        assert history["concept"]["name"] == "signal seed"
        assert history["observations"][0]["source_id"] == sid
        assert history["observations"][0]["source_sha256"]


def test_single_source_cannot_become_invariant(tmp_path):
    with make_ledger(tmp_path) as ledger:
        sid = ledger.ingest_text("provenance supports continuity", domains=["victoros"])
        ledger.record_observation(
            "provenance", sid, "provenance", confidence=1.0, evidence_state="VERIFIED"
        )
        ledger.record_observation(
            "continuity", sid, "continuity", confidence=1.0, evidence_state="VERIFIED"
        )
        ledger.link("provenance", "SUPPORTS", "continuity", confidence=1.0, status="verified")
        rows = {row.concept: row for row in ledger.scan()}
        assert rows["provenance"].classification == "EXPERIMENT"
