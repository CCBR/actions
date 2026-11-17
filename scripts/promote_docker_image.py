"""Check and promote registry tags for a Docker image."""

import os
import subprocess
import sys


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run Docker and include command output in errors."""
    try:
        return subprocess.run(
            ["docker", *args], check=check, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Docker {' '.join(args)} failed: {message}") from error


def image_exists(reference: str) -> bool:
    """Return false only when the registry reports a missing manifest."""
    result = docker("buildx", "imagetools", "inspect", reference, check=False)
    if result.returncode == 0:
        return True

    message = f"{result.stderr}\n{result.stdout}".strip()
    lowered = message.lower()
    if any(
        marker in lowered
        for marker in ("manifest unknown", "no such manifest", "not found", "404")
    ):
        return False
    raise RuntimeError(f"Cannot inspect image {reference}: {message}")


def refs_from_environment(name: str) -> list[str]:
    """Read registry references from a multiline action environment value."""
    refs = [
        reference.strip()
        for reference in os.environ.get(name, "").splitlines()
        if reference.strip()
    ]
    if not refs:
        raise ValueError(f"{name} must contain at least one image reference.")
    return refs


def write_output(**values: str) -> None:
    """Write GitHub Actions step outputs."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise ValueError("GITHUB_OUTPUT is required.")
    with open(output_path, "a", encoding="utf-8") as output:
        for name, value in values.items():
            print(f"{name}={value}", file=output)


def check() -> None:
    """Check that the requested source tag exists in every target registry."""
    results = [
        image_exists(reference) for reference in refs_from_environment("SOURCE_REFS")
    ]
    available = all(results)
    write_output(available=str(available).lower())
    if not available:
        print("::notice::Source image tag is missing; the image will be built.")


def promote() -> None:
    """Retag source images as the stable build tags."""
    sources = refs_from_environment("SOURCE_REFS")
    targets = refs_from_environment("TARGET_REFS")
    if len(sources) != len(targets):
        raise ValueError("SOURCE_REFS and TARGET_REFS must have matching lengths.")
    results = [image_exists(reference) for reference in sources]
    if not all(results):
        write_output(promoted="false")
        print("::notice::Source image disappeared; the image will be built.")
        return

    for source, target in zip(sources, targets, strict=True):
        docker("buildx", "imagetools", "create", "--tag", target, source)
    write_output(promoted="true")


def main() -> int:
    """Run the requested operation and report failures to GitHub Actions."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"check", "promote"}:
        print("Usage: promote_docker_image.py {check|promote}", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "check":
            check()
        else:
            promote()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"::error::Cannot promote Docker image: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
