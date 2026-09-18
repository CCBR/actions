"""Prepare Docker build variables for a GitHub Actions step."""

import argparse
import os

from ccbr_actions.docker import prepare_docker_build_variables


def main() -> int:
    """Parse arguments and prepare Docker build variables."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dockerfile", help="Path to the Dockerfile.")
    parser.add_argument("suffix", help="Image tag suffix.")
    parser.add_argument("dockerhub_account", help="Docker Hub namespace.")
    args = parser.parse_args()
    prepare_docker_build_variables(
        dockerfile=args.dockerfile,
        suffix=args.suffix,
        dockerhub_account=args.dockerhub_account,
        github_env=os.environ.get("GITHUB_ENV"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
