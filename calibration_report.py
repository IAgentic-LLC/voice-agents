"""Chapter 24: does Chapter 8's own scorer agree with a human, on
answers labeled before the scorer's own verdict is read.

    uv run calibration_report.py
"""

from voicelab.calibration import PROBES, scorer_verdict


def main() -> None:
    bad = [p for p in PROBES if scorer_verdict(p) != p.human_says_right]
    print(f"probes: {len(PROBES)}  disagreements: {len(bad)}")
    for p in PROBES:
        scorer = scorer_verdict(p)
        flag = "" if scorer == p.human_says_right else "  MISCALIBRATED"
        print(f"{p.task:8s} human={p.human_says_right!s:5s} "
              f"scorer={scorer!s:5s}{flag}")


if __name__ == "__main__":
    main()
