"""Command line interface:  python -m studio <command>"""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from . import export as exporter
from .ai import AIClient
from .config import DIST, WORKSPACE, ConfigError, list_brands
from .project import Project


def _ai(args) -> AIClient:
    return AIClient.from_env(getattr(args, "ai", None))


def cmd_build(args) -> int:
    brands = list_brands() if args.all or not args.brand else [args.brand]
    for brand_id in brands:
        started = time.time()
        if args.from_workspace:
            project = Project.open(brand_id, _ai(args))
        else:
            # Pure build: a throwaway workspace so results depend only on the repository contents.
            with tempfile.TemporaryDirectory() as tmp:
                project = Project.open(brand_id, _ai(args), workspace=Path(tmp), fresh=True)
                zip_path = exporter.export(project, Path(args.out))
            print(f"{brand_id}: {zip_path} ({time.time() - started:.1f}s)")
            continue
        zip_path = exporter.export(project, Path(args.out))
        print(f"{brand_id}: {zip_path} ({time.time() - started:.1f}s)")
    return 0


def cmd_replace(args) -> int:
    project = Project.open(args.brand, _ai(args))
    kind, index = args.kind, args.slot - 1
    image_path = Path(args.image)
    image_id = project.add_upload(image_path.read_bytes(), image_path.name) if image_path.exists() else args.image
    project.replace(kind, index, image_id)
    print(f"{kind} {args.slot} now uses {image_id} (locked). Run `build --from-workspace` to export.")
    return 0


def cmd_serve(args) -> int:
    from .app import create_app
    app = create_app(_ai(args))
    print(f"Noomoo Studio running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


def cmd_brands(_args) -> int:
    print("\n".join(list_brands()))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="studio", description="Brand-to-Instagram asset generator")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="curate, render and export a brand kit")
    b.add_argument("--brand", help="brand folder name (default: all brands)")
    b.add_argument("--all", action="store_true", help="build every brand")
    b.add_argument("--out", default=str(DIST), help="output folder (default: dist/)")
    b.add_argument("--ai", choices=["none", "openai_compat"], help="caption provider (default: AI_PROVIDER or none)")
    b.add_argument("--from-workspace", action="store_true", help="export the state saved by the web UI / replace command")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("replace", help="swap the image in one slot (1-based) and lock it")
    r.add_argument("--brand", required=True)
    r.add_argument("--kind", choices=["post", "story"], required=True)
    r.add_argument("--slot", type=int, required=True)
    r.add_argument("--image", required=True, help="path to a new image, or an existing image id")
    r.add_argument("--ai", choices=["none", "openai_compat"])
    r.set_defaults(func=cmd_replace)

    s = sub.add_parser("serve", help="start the web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=5000)
    s.add_argument("--ai", choices=["none", "openai_compat"])
    s.set_defaults(func=cmd_serve)

    sub.add_parser("brands", help="list available brands").set_defaults(func=cmd_brands)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, ValueError, KeyError, IndexError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
