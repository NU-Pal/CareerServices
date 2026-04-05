"""Deterministic posture notes merged into LLM feedback (ported from NUPAL lib/interview)."""

from typing import Any


def merge_posture_into_feedback(feedback: dict[str, Any], metrics: Any) -> None:
    if not metrics or not isinstance(metrics, object):
        return
    if not isinstance(metrics, dict):
        return
    m = metrics
    if not isinstance(m.get("frameCount"), int):
        return
    feedback["postureObjectiveNotes"] = build_objective_posture_notes(m)


def build_objective_posture_notes(agg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    frame_count = int(agg.get("frameCount") or 0)
    if frame_count == 0:
        out.append(
            "No pose frames were captured — posture feedback is not available for this session."
        )
        return out

    if frame_count < 25:
        out.append(
            f"Only {frame_count} pose frames were analyzed — treat posture insights as approximate."
        )

    avg_symmetry = float(agg.get("avgSymmetry") or 0)
    std_symmetry = float(agg.get("stdSymmetry") or 0)
    pct_symmetry_below = float(agg.get("pctSymmetryBelow58") or 0)
    avg_facing = float(agg.get("avgFacing") or 0)
    std_facing = float(agg.get("stdFacing") or 0)
    pct_facing_below = float(agg.get("pctFacingBelow58") or 0)
    avg_head_pitch = float(agg.get("avgHeadPitch") or 0)
    pct_head_pitch_below = float(agg.get("pctHeadPitchBelow58") or 0)
    avg_trunk = agg.get("avgTrunk")
    trunk_frame_ratio = float(agg.get("trunkFrameRatio") or 0)

    if avg_symmetry < 62:
        out.append(
            f"Shoulder level averaged {avg_symmetry:.0f}/100 (uneven or slouched shoulders likely)."
        )
    if std_symmetry >= 14:
        out.append(
            f"Shoulder alignment fluctuated noticeably across the session (variability {std_symmetry:.1f})."
        )
    if pct_symmetry_below >= 38:
        out.append(f"{pct_symmetry_below:.0f}% of frames showed low shoulder symmetry.")

    if avg_facing < 65:
        out.append(
            f"Facing the camera averaged {avg_facing:.0f}/100 — you were often off-center or turned sideways relative to the lens."
        )
    if std_facing >= 17:
        out.append(
            f"Head position moved side-to-side a lot (stdev {std_facing:.1f}) — try steadier head position when answering."
        )
    if pct_facing_below >= 38:
        out.append(f"{pct_facing_below:.0f}% of frames had weak “facing camera” alignment.")

    if avg_head_pitch < 60:
        out.append(
            f"Head angle vs shoulders averaged {avg_head_pitch:.0f}/100 — likely looking down at screen or notes; raise the camera to eye level if possible."
        )
    if pct_head_pitch_below >= 35:
        out.append(f"In {pct_head_pitch_below:.0f}% of frames the head appeared tilted downward.")

    if avg_trunk is not None and float(avg_trunk) < 55 and trunk_frame_ratio >= 0.35:
        out.append(
            f"Upper-body openness (shoulder–hip span) averaged {float(avg_trunk):.0f}/100 — consider sitting taller and slightly back from the camera."
        )

    only_thin = (
        len(out) == 1
        and "Only " in out[0]
        and "pose frames were analyzed" in out[0]
    )
    has_concrete = any(
        "Only " not in line and "No pose frames were captured" not in line for line in out
    )

    if frame_count >= 25 and not has_concrete and not only_thin:
        out.append(
            "Pose metrics stayed in a neutral-to-good band — no major red flags from the automated check (this is not a substitute for human observation)."
        )

    return out
