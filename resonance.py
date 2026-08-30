#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from vos_core.resonance_ledger import EVIDENCE_WEIGHTS, RELATIONS, ResonanceLedger


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _read_source(value: str) -> tuple[str, str]:
    if value == "-":
        return sys.stdin.read(), "stdin"
    path = Path(value)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8"), str(path)
    return value, "inline"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resonance",
        description="A1-RL-001 Resonance Ledger / Signal Seed Analyzer",
    )
    parser.add_argument("--db", default=".victor/resonance.db", help="SQLite ledger path")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Preserve a source and bind its SHA-256")
    ingest.add_argument("source", help="UTF-8 file path, '-' for stdin, or inline text")
    ingest.add_argument("--type", default="episode", dest="source_type")
    ingest.add_argument("--title", default="")
    ingest.add_argument("--domain", action="append", default=[])
    ingest.add_argument("--author", default="unknown")
    ingest.add_argument("--timestamp", default=None)
    ingest.add_argument("--source-id", default=None)

    extract = sub.add_parser("extract", help="Deterministically extract candidate concepts")
    extract.add_argument("source_id")
    extract.add_argument("--max", type=int, default=20, dest="max_concepts")

    observe = sub.add_parser("observe", help="Bind a concept observation to source evidence")
    observe.add_argument("concept")
    observe.add_argument("source_id")
    observe.add_argument("--span", required=True)
    observe.add_argument("--confidence", type=float, default=0.7)
    observe.add_argument("--interpretation-state", default="explicit")
    observe.add_argument(
        "--evidence-state", default="OBSERVED", choices=sorted(EVIDENCE_WEIGHTS)
    )

    link = sub.add_parser("link", help="Create a provenance-aware concept relation")
    link.add_argument("concept_a")
    link.add_argument("relation", choices=sorted(RELATIONS))
    link.add_argument("concept_b")
    link.add_argument("--source-id", default=None)
    link.add_argument("--confidence", type=float, default=0.8)
    link.add_argument("--status", default="inference")

    alias = sub.add_parser("alias", help="Bind an explicit alias to an existing concept")
    alias.add_argument("concept")
    alias.add_argument("alias")

    scan = sub.add_parser("scan", help="Calculate resonance vectors and classifications")
    scan.add_argument("--json", action="store_true")

    history = sub.add_parser("history", help="Show evidence/edge history for one concept")
    history.add_argument("concept")

    sub.add_parser("verify", help="Verify source hashes, event hash chain, and FKs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with ResonanceLedger(args.db) as ledger:
            if args.command == "ingest":
                text, origin = _read_source(args.source)
                source_id = ledger.ingest_text(
                    text,
                    source_type=args.source_type,
                    title=args.title or origin,
                    domains=args.domain,
                    author=args.author,
                    source_timestamp=args.timestamp,
                    source_id=args.source_id,
                )
                _print_json({"source_id": source_id, "integrity": ledger.verify_integrity()})
                return 0

            if args.command == "extract":
                _print_json(ledger.extract(args.source_id, max_concepts=args.max_concepts))
                return 0

            if args.command == "observe":
                observation_id = ledger.record_observation(
                    args.concept,
                    args.source_id,
                    args.span,
                    confidence=args.confidence,
                    interpretation_state=args.interpretation_state,
                    evidence_state=args.evidence_state,
                )
                _print_json({"observation_id": observation_id})
                return 0

            if args.command == "link":
                edge_id = ledger.link(
                    args.concept_a,
                    args.relation,
                    args.concept_b,
                    source_id=args.source_id,
                    confidence=args.confidence,
                    status=args.status,
                )
                _print_json({"edge_id": edge_id})
                return 0

            if args.command == "alias":
                ledger.add_alias(args.concept, args.alias)
                _print_json({"concept": args.concept, "alias": args.alias})
                return 0

            if args.command == "scan":
                rows = ledger.scan()
                if args.json:
                    _print_json([asdict(row) for row in rows])
                else:
                    if not rows:
                        print("No concepts recorded.")
                        return 0
                    print(
                        f"{'concept':32} {'R':>6} {'P':>6} {'D':>6} {'C':>6} {'E':>6} {'V':>6} {'K':>6} classification"
                    )
                    for row in rows:
                        print(
                            f"{row.concept[:32]:32} {row.resonance_score:6.3f} "
                            f"{row.persistence:6.3f} {row.domain_diversity:6.3f} "
                            f"{row.centrality:6.3f} {row.evidence_quality:6.3f} "
                            f"{row.volatility:6.3f} {row.contradiction_pressure:6.3f} "
                            f"{row.classification}"
                        )
                return 0

            if args.command == "history":
                _print_json(ledger.history(args.concept))
                return 0

            if args.command == "verify":
                report = ledger.verify_integrity()
                _print_json(report)
                return 0 if report["ok"] else 2

    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
