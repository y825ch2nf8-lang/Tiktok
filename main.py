#!/usr/bin/env python3
"""TikTok-Bot - Einstiegspunkt.

    python main.py                 # ein komplettes Video produzieren
    python main.py --test          # Testmodus (keine API-Aufrufe)
    python main.py --count 3       # drei Videos nacheinander
    python main.py --topic "Oktopus"   # eigenes Thema (Wikipedia-Artikelname) statt Themensuche
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from config import load_config
from src.logger import log, setup_logging
from src.pipeline import Pipeline
from src.utils import PipelineError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vollautomatische TikTok-Video-Produktion (Dark Cinematic Knowledge)")
    p.add_argument("--test", action="store_true", help="Testmodus: keine API-Aufrufe, lokale Beispieldaten")
    p.add_argument("--count", type=int, default=1, help="Anzahl Videos (Standard: 1)")
    p.add_argument("--topic", type=str, default=None, help="Eigenes Thema (Titel eines Wikipedia-Artikels)")
    p.add_argument("--config", type=Path, default=None, help="Pfad zu einer alternativen config.yaml")
    p.add_argument("--keep-work", action="store_true", help="Zwischendateien (output/work) behalten")
    p.add_argument("--verbose", "-v", action="store_true", help="Ausfuehrliche Ausgabe (Debug)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, test_mode=args.test)
    if args.keep_work:
        cfg.export.keep_work = True
    setup_logging(cfg.log_dir, verbose=args.verbose)

    if args.test:
        log.info("TESTMODUS aktiv: keine API-Aufrufe, Beispieldaten + lokale Synthese")

    pipeline = Pipeline(cfg)
    ok, failed = 0, 0
    for n in range(1, max(1, args.count) + 1):
        if args.count > 1:
            log.info(f"=== Video {n}/{args.count} ===")
        try:
            pipeline.run(manual_topic=args.topic)
            ok += 1
        except PipelineError as exc:
            failed += 1
            log.error(str(exc))
        except KeyboardInterrupt:
            log.error("Abgebrochen")
            return 130
        except Exception as exc:
            failed += 1
            log.error(f"Unerwarteter Fehler: {exc!r}")
            log.debug(traceback.format_exc())

    if args.count > 1:
        log.info(f"Fertig: {ok} erfolgreich, {failed} fehlgeschlagen")
    return 0 if ok and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
