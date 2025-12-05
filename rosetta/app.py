"""Primary entry point for the Rosetta toolkit.

This module collects frequently used helpers behind a small CLI so the
package can be invoked with ``python -m rosetta`` once installed in editable
mode. The CLI is intentionally lightweight and reuses the shared helpers
rather than duplicating logic that already lives inside the package.
"""
from __future__ import annotations

import argparse
import json
from typing import Iterable, Mapping

from rosetta import __version__
from rosetta.helpers import build_aspect_graph, format_dms, format_longitude


def _parse_positions(raw: Iterable[str]) -> Mapping[str, float]:
    """Parse position strings of the form ``Name=123.4`` into a mapping."""
    positions = {}
    for entry in raw:
        if "=" not in entry:
            raise ValueError(f"Position '{entry}' must look like Name=degrees")
        name, value = entry.split("=", 1)
        positions[name.strip()] = float(value)
    return positions


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rosetta command-line helpers")
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command", required=True)

    fmt_dms = subparsers.add_parser("format-dms", help="Render a value as DMS")
    fmt_dms.add_argument("value", type=float, help="Decimal value to format")
    fmt_dms.add_argument("--speed", action="store_true", help="Format as speed")
    fmt_dms.add_argument("--latlon", action="store_true", help="Include N/S suffix")

    fmt_lon = subparsers.add_parser(
        "format-longitude", help="Render a zodiacal longitude with sign labels"
    )
    fmt_lon.add_argument("value", type=float, help="Longitude in decimal degrees")

    graph = subparsers.add_parser(
        "aspect-components", help="Return connected components from positions"
    )
    graph.add_argument(
        "positions",
        metavar="NAME=DEGREES",
        nargs="+",
        help="Position mapping used to detect major aspect links",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "format-dms":
        print(format_dms(args.value, is_latlon=args.latlon, is_speed=args.speed))
    elif args.command == "format-longitude":
        print(format_longitude(args.value))
    elif args.command == "aspect-components":
        pos = _parse_positions(args.positions)
        components = [sorted(comp) for comp in build_aspect_graph(pos)]
        print(json.dumps(components))
    else:
        parser.error("No command specified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
