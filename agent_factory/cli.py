from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from agent_factory.app import create_app
from agent_factory.builder import build_twin
from agent_factory.deploy import deploy_twin
from agent_factory.improvement import DryRunPRPublisher, reflect_and_propose
from agent_factory.persistence import build_store_from_env
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

    twin_parser = subparsers.add_parser("twin", help="Twin-builder pipeline (build/deploy)")
    twin_sub = twin_parser.add_subparsers(dest="twin_command", required=True)

    build_parser = twin_sub.add_parser("build", help="Build an immutable twin artifact from a bridge twin.yaml")
    build_parser.add_argument("twin_yaml")
    build_parser.add_argument("--output-root", default="twins/artifacts")
    build_parser.add_argument("--auth-token", help="Token for private kernel repo auth (or set KERNEL_AUTH_TOKEN)")
    build_parser.add_argument("--overwrite", action="store_true")

    deploy_parser = twin_sub.add_parser("deploy", help="Deploy a built artifact to a cloud target")
    deploy_parser.add_argument("artifact_dir")
    deploy_parser.add_argument("--cloud", required=True, choices=["gcp", "aws", "local"])
    deploy_parser.add_argument("--registry-root", help="Install the artifact into this registry root")

    reflect_parser = subparsers.add_parser(
        "reflect",
        help="Run the improvement loop: score recent traces and propose kernel edits (dry-run PRs)",
    )
    reflect_parser.add_argument("--registry-root", required=True)
    reflect_parser.add_argument("--twin-id", required=True)
    reflect_parser.add_argument("--output-dir", default=None, help="Where to write dry-run PR artifacts")

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

    if args.command == "twin":
        if args.twin_command == "build":
            result = build_twin(
                twin_yaml=args.twin_yaml,
                output_root=args.output_root,
                auth_token=args.auth_token,
                overwrite=args.overwrite,
            )
            print(
                json.dumps(
                    {
                        "twin_name": result.twin_name,
                        "artifact_hash": result.artifact_hash,
                        "artifact_dir": str(result.artifact_dir),
                        "kernel": {"source": result.kernel_source, "version": result.kernel_version},
                        "files": result.files,
                    },
                    indent=2,
                )
            )
            return

        if args.twin_command == "deploy":
            result = deploy_twin(
                artifact_dir=args.artifact_dir,
                cloud=args.cloud,
                registry_root=args.registry_root,
            )
            print(
                json.dumps(
                    {
                        "twin_name": result.twin_name,
                        "artifact_hash": result.artifact_hash,
                        "cloud": result.cloud,
                        "blob_uri": result.blob_uri,
                        "registry_path": result.registry_path,
                        "deploy_record": result.deploy_record_path,
                    },
                    indent=2,
                )
            )
            return

    if args.command == "reflect":
        registry = TwinRegistry(args.registry_root)
        twin = registry.get(args.twin_id)
        store = build_store_from_env()
        output_dir = args.output_dir or str(Path(args.registry_root) / ".improvements")
        result = reflect_and_propose(twin, store, DryRunPRPublisher(output_dir))
        print(
            json.dumps(
                {
                    "twin_id": result.twin_id,
                    "scored_traces": result.scored_traces,
                    "candidates": len(result.candidates),
                    "published": result.published,
                },
                indent=2,
            )
        )
        return


if __name__ == "__main__":
    main()
