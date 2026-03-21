from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from agent_factory.app import create_app
from agent_factory.installer import install_twin
from agent_factory.kernel_sync import compose_twin_from_kernel_source, sync_kernel_artifacts
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime
from agent_factory.smoke import run_smoke_suite


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-factory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install a twin package into a registry root")
    install_parser.add_argument("source_dir")
    install_parser.add_argument("destination_root")
    install_parser.add_argument("--overwrite", action="store_true")

    list_parser = subparsers.add_parser("list", help="List installed twins")
    list_parser.add_argument("--registry-root", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the agent-factory API")
    serve_parser.add_argument("--registry-root", required=True)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)

    smoke_parser = subparsers.add_parser("smoke-test", help="Run smoke suites for installed twins")
    smoke_parser.add_argument("--registry-root", required=True)

    sync_parser = subparsers.add_parser(
        "sync-kernel",
        help="Sync a twin package from a local agent-kernel source tree",
    )
    sync_parser.add_argument("--source-root", required=True)
    sync_parser.add_argument("--twin-root", required=True)

    import_parser = subparsers.add_parser(
        "import-kernel",
        help="Compose a twin package from a local agent-kernel folder or git URL",
    )
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--twin-root", required=True)
    import_parser.add_argument("--seed-root", default="twin_seeds/principal-operator")
    import_parser.add_argument("--overwrite", action="store_true")
    import_parser.add_argument("--git-ref")
    import_parser.add_argument("--twin-id")
    import_parser.add_argument("--name")
    import_parser.add_argument("--owner")
    import_parser.add_argument("--description")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "install":
        target = install_twin(args.source_dir, args.destination_root, overwrite=args.overwrite)
        print(target)
        return

    if args.command == "list":
        registry = TwinRegistry(args.registry_root)
        payload = [
            {
                "twin_id": twin.manifest.twin_id,
                "name": twin.manifest.name,
                "default_model_profile": twin.manifest.default_model_profile,
            }
            for twin in registry.list()
        ]
        print(json.dumps(payload, indent=2))
        return

    if args.command == "serve":
        app = create_app(Path(args.registry_root))
        uvicorn.run(app, host=args.host, port=args.port)
        return

    if args.command == "smoke-test":
        registry = TwinRegistry(args.registry_root)
        runtime = TwinRuntime(registry)
        all_results = []
        for twin in registry.list():
            all_results.extend(run_smoke_suite(runtime, twin))

        failures = [result for result in all_results if not result.passed]
        for result in all_results:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} {result.case_name}: {result.details}")

        if failures:
            raise SystemExit(1)
        return

    if args.command == "sync-kernel":
        copied = sync_kernel_artifacts(args.source_root, args.twin_root)
        print(json.dumps({"copied": copied}, indent=2))
        return

    if args.command == "import-kernel":
        copied = compose_twin_from_kernel_source(
            source=args.source,
            twin_root=args.twin_root,
            seed_root=args.seed_root,
            overwrite=args.overwrite,
            git_ref=args.git_ref,
            manifest_overrides={
                "twin_id": args.twin_id,
                "name": args.name,
                "owner": args.owner,
                "description": args.description,
            },
        )
        print(json.dumps({"copied": copied, "twin_root": str(Path(args.twin_root).resolve())}, indent=2))
        return


if __name__ == "__main__":
    main()
