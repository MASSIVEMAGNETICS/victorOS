#!/usr/bin/env python3
"""
VOS CLI Entry Point — Bando Bandz / Massive Magnetics
Usage: python main.py --title "Track" --artist "Name" --no-ai
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vos_core.core_router import CORERouter


def main():
    parser = argparse.ArgumentParser(description="VOS v0.1.0 CLI")
    parser.add_argument("--title", default="Untitled")
    parser.add_argument("--artist", default="Independent")
    parser.add_argument("--genre", default="Hip-Hop/Rap")
    parser.add_argument("--mood", default="Gritty")
    parser.add_argument("--bpm", type=int, default=140)
    parser.add_argument("--key", default="C Minor")
    parser.add_argument("--release", default=None)
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip local LLM prompt generation",
    )
    args = parser.parse_args()

    raw = {
        "title": args.title,
        "artist": args.artist,
        "genre": args.genre,
        "mood": args.mood,
        "bpm": args.bpm,
        "key": args.key,
        "release_date": args.release,
    }

    router = CORERouter()
    result = router.process_input(raw, generate_ai=not args.no_ai)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
