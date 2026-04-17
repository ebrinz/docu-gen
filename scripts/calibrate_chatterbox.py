"""Sweep Chatterbox MLX across (word_count, exaggeration) to find the distortion cliff.

Generates WAVs into projects/<name>/build/calibration/, computes objective
distortion proxies, and writes an HTML contact sheet for listening.

Usage:
    python scripts/calibrate_chatterbox.py projects/parse-evols-yeast
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from docugen.config import load_config
from docugen.tools.narrate import _generate_chatterbox

# Semantically neutral texts, ascending word count.
TEXTS = {
    1: "Nucleotides.",
    2: "Zero pipettes.",
    3: "Two orthogonal pathways.",
    4: "The algorithm did this.",
    5: "Predicted effect, significant and robust.",
    6: "Sir two activation combined with TOR inhibition.",
    8: "The computational heavy lifting is largely done today.",
    10: "Induces autophagy via IP three receptor antagonism across the cell.",
    15: "All code is open, all eleven analyses regenerate from source, and the pipeline runs cleanly.",
}

EXAGGERATIONS = [0.15, 0.25, 0.35, 0.45, 0.55, 0.70]


def compute_metrics(wav_path: Path) -> dict:
    sr, data = wavfile.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    x = data.astype(np.float64)
    peak = np.abs(x).max()
    if peak == 0:
        return {"duration": 0.0, "peak_clip_pct": 0.0, "jump_rms": 0.0,
                "rms": 0.0, "silence_frac": 1.0}
    x_norm = x / peak

    # Peak clipping: fraction of samples at or near full scale.
    peak_clip_pct = float(np.mean(np.abs(x_norm) > 0.99) * 100.0)

    # Inter-sample jump RMS: high when waveform has discontinuities / glitches.
    diffs = np.diff(x_norm)
    jump_rms = float(np.sqrt(np.mean(diffs ** 2)))

    # Overall RMS energy.
    rms = float(np.sqrt(np.mean(x_norm ** 2)))

    # Silence fraction: 20 ms frames below -40 dB.
    frame_len = int(sr * 0.020)
    if frame_len > 0 and len(x_norm) >= frame_len:
        n_frames = len(x_norm) // frame_len
        frames = x_norm[: n_frames * frame_len].reshape(n_frames, frame_len)
        frame_rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
        silence_frac = float(np.mean(frame_rms < 0.01))
    else:
        silence_frac = 0.0

    return {
        "duration": float(len(x) / sr),
        "peak_clip_pct": peak_clip_pct,
        "jump_rms": jump_rms,
        "rms": rms,
        "silence_frac": silence_frac,
    }


def build_html(results: list[dict], out_dir: Path) -> None:
    # Sort so the grid renders with word_count rows x exaggeration cols.
    word_counts = sorted({r["word_count"] for r in results})
    exaggs = sorted({r["exaggeration"] for r in results})
    by_key = {(r["word_count"], r["exaggeration"]): r for r in results}

    def flag(r: dict) -> str:
        if r["jump_rms"] > 0.05 or r["peak_clip_pct"] > 1.0:
            return "bad"
        if r["jump_rms"] > 0.03 or r["peak_clip_pct"] > 0.3:
            return "warn"
        return "ok"

    rows = []
    for wc in word_counts:
        cells = [f"<th>{wc} words<br><small>{TEXTS[wc]!r}</small></th>"]
        for e in exaggs:
            r = by_key.get((wc, e))
            if r is None:
                cells.append("<td></td>")
                continue
            cls = flag(r)
            cells.append(
                f"<td class='{cls}'>"
                f"<audio controls src='{r['wav']}'></audio><br>"
                f"<code>peak {r['peak_clip_pct']:.2f}%<br>"
                f"jump {r['jump_rms']:.4f}<br>"
                f"rms {r['rms']:.3f}<br>"
                f"sil {r['silence_frac']:.2f}</code>"
                f"</td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    header = "<tr><th></th>" + "".join(
        f"<th>exagg {e}</th>" for e in exaggs
    ) + "</tr>"

    html = f"""<!doctype html>
<meta charset='utf-8'>
<title>Chatterbox calibration grid</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #111; color: #ddd; padding: 24px; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #333; padding: 8px; vertical-align: top; font-size: 12px; }}
td.ok {{ background: #143; }}
td.warn {{ background: #542; }}
td.bad {{ background: #622; }}
code {{ color: #9cf; }}
audio {{ width: 180px; }}
small {{ color: #888; font-weight: normal; }}
</style>
<h1>Chatterbox MLX distortion sweep</h1>
<p>Green = clean. Yellow = borderline. Red = likely distortion.
Thresholds: jump_rms &gt; 0.03 / 0.05, peak_clip_pct &gt; 0.3 / 1.0.</p>
<table>{header}{''.join(rows)}</table>
"""
    (out_dir / "index.html").write_text(html)


def main(project_path: str) -> None:
    project = Path(project_path)
    out_dir = project / "build" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(project)
    voice_config = dict(config["voice"])  # copy; we override exaggeration per cell

    results = []
    total = len(TEXTS) * len(EXAGGERATIONS)
    done = 0
    for wc, text in TEXTS.items():
        for exagg in EXAGGERATIONS:
            done += 1
            wav_name = f"wc{wc:02d}_exagg{int(exagg * 100):03d}.wav"
            wav_path = out_dir / wav_name
            print(f"[{done}/{total}] {wav_name}  text={text!r}", flush=True)
            if not wav_path.exists():
                _generate_chatterbox(voice_config, text, wav_path, exaggeration=exagg)
            metrics = compute_metrics(wav_path)
            results.append({
                "word_count": wc,
                "exaggeration": exagg,
                "text": text,
                "wav": wav_name,
                **metrics,
            })

    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    build_html(results, out_dir)
    print(f"\nDone. Open {out_dir / 'index.html'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: calibrate_chatterbox.py <project_path>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
