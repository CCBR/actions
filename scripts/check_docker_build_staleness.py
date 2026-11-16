"""Check registry tag freshness and write GitHub Actions outputs."""

import argparse
import os

from ccbr_actions.docker import evaluate_docker_build_staleness_and_set_outputs


def main() -> int:
    """Parse arguments and evaluate Docker build staleness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dockerfile_path", help="Path to the Dockerfile.")
    parser.add_argument("image_name", help="Docker image name and tag.")
    parser.add_argument("dockerhub_namespace", help="Docker Hub namespace.")
    parser.add_argument("repo_name", help="Image repository name.")
    parser.add_argument(
        "--registries",
        default="dockerhub",
        help="Comma-separated registries to check (dockerhub, ghcr).",
    )
    parser.add_argument(
        "--ghcr-namespace",
        default="",
        help="GHCR owner or organization. Defaults to GITHUB_REPOSITORY_OWNER.",
    )
    parser.add_argument(
        "--platforms",
        default="",
        help="Comma-separated platforms that each registry tag must include.",
    )
    args = parser.parse_args()
    force_build = os.environ.get("INPUT_FORCE_BUILD", "").lower() == "true"
    if force_build:
        from ccbr_actions.actions import set_output

        set_output("should_build", "true")
        set_output("reason", "force_build_requested")
        print("::notice::Force build requested. Skipping registry staleness check.")
    else:
        evaluate_docker_build_staleness_and_set_outputs(
            dockerfile_path=args.dockerfile_path,
            image_name=args.image_name,
            dockerhub_namespace=args.dockerhub_namespace,
            repo_name=args.repo_name,
            registries=args.registries,
            ghcr_namespace=args.ghcr_namespace
            or os.environ.get("GITHUB_REPOSITORY_OWNER", ""),
            platforms=args.platforms,
            github_token=os.environ.get("GITHUB_TOKEN", ""),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
