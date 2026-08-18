"""Record the availability of the independent qualitative critic.

GitHub Models was retired in 2026 and its inference endpoint now returns HTTP
410. The deterministic site/browser audits remain authoritative. This module
keeps the evidence bundle explicit and emits a GitHub Actions warning instead
of silently publishing an empty "successful" critic section.
"""
from __future__ import annotations

import argparse
from pathlib import Path


RETIREMENT_MESSAGE = (
    "Independent AI criticism is unavailable because GitHub Models has been "
    "retired. Deterministic route, layout, image, coverage, and ranking audits "
    "still ran; configure a replacement provider before re-enabling qualitative criticism."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", type=Path, default=Path("audit-output"))
    args = parser.parse_args()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    print(f"::warning title=Independent site critic unavailable::{RETIREMENT_MESSAGE}")
    output = [
        "# Independent critic reviews",
        "",
        "## Availability",
        "",
        RETIREMENT_MESSAGE,
        "",
        "The deterministic report and captured mobile/desktop screenshots are the review evidence for this run.",
        "",
    ]
    (args.audit_dir / "critique.md").write_text("\n".join(output))


if __name__ == "__main__":
    main()
