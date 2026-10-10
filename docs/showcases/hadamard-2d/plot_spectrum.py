"""Plot seven computed wavelength points from the verified compact bundle.

No interpolation, fitting, smoothing, confidence intervals or stochastic
replicates are inferred. The 1550 nm spectrum point uses mesh020, matching the
other six spectral runs; the separately displayed nominal center is mesh025.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import verify
from matplotlib.lines import Line2D

SPECTRAL_RUNS = (
    "wave1520",
    "wave1536",
    "holdout1543_3",
    "mesh020",
    "wave1565",
    "holdout1572_3",
    "wave1580",
)


def normalize_derived_text(path):
    """Keep derived text portable without changing plotted numerical values."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if path.suffix == ".svg":
        text = "\n".join(line.rstrip(" \t") for line in text.splitlines()) + "\n"
    path.write_bytes(text.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).parent / "evidence")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "figures")
    parser.add_argument("--qa-helper-dir", type=Path)
    args = parser.parse_args()
    result = verify.verify(args.evidence)
    if result["full_numerical_suite_pass"] is not True:
        raise ValueError("Plotting requires a complete, numerically consistent bundle")
    bundle = verify.read_json(args.evidence / "bundle.json")
    all_rows = {row["name"]: row for row in bundle["runs"]}
    rows = [all_rows[name] for name in SPECTRAL_RUNS]
    points = []
    for row in rows:
        config, report = row["config"], row["report"]
        verify.exact(config["mesh_um"], 0.02, "spectral core mesh")
        verify.exact(config["cladding_mesh_um"], 0.08, "spectral cladding mesh")
        points.append(
            {
                "run": row["name"],
                "wavelength_nm": config["wavelength_nm"],
                "role": "holdout" if row["name"].startswith("holdout") else "training_wavelength",
                "eta_all": report["minimum_target_throughput_all_inputs"],
                "F6": report["min_six_state_conditional_fidelity"],
                "conditional_choi_overlap": report["conditional_choi_overlap"],
                "split_ratio_input_1": report["both_input_split_ratios"][0],
                "split_ratio_input_2": report["both_input_split_ratios"][1],
                "original_receipt_sha256": row["original_receipt_sha256"],
            }
        )
    wavelengths = [point["wavelength_nm"] for point in points]
    if len(points) != 7 or wavelengths != sorted(set(wavelengths)):
        raise ValueError("Seven unique ordered spectral points required")
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "spectrum-source-data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(points[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(points)

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "text.usetex": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
            "lines.linewidth": 1,
        }
    )
    # Figure contract: primary all-input throughput, independent conditional
    # state/process overlap, then both-input balance. These are distinct gates
    # on one fixed mask. Seven single deterministic solves; no error bars.
    fig, axes = plt.subplots(3, 1, figsize=(183 / 25.4, 160 / 25.4), sharex=True)
    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.10, top=0.88, hspace=0.32)
    colors = ("#0072B2", "#D55E00")

    def point_series(ax, key, color):
        for role, marker, size in (("training_wavelength", "o", 27), ("holdout", "D", 32)):
            selected = [point for point in points if point["role"] == role]
            scatter_style = {"color": color, "edgecolors": "white", "linewidths": 0.4}
            if key == "F6":
                size *= 1.6
                scatter_style = {"facecolors": "none", "edgecolors": color, "linewidths": 1.0}
            elif key == "conditional_choi_overlap":
                size *= 0.4
            ax.scatter(
                [p["wavelength_nm"] for p in selected],
                [p[key] for p in selected],
                marker=marker,
                s=size,
                **scatter_style,
                zorder=3,
            )

    point_series(axes[0], "eta_all", colors[0])
    axes[0].axhline(0.9, color="#555555", ls="--", lw=0.8)
    axes[0].set(ylabel="Minimum throughput", ylim=(0.89, 1.005), yticks=[0.9, 0.95, 1.0])
    point_series(axes[1], "F6", colors[0])
    point_series(axes[1], "conditional_choi_overlap", colors[1])
    axes[1].axhline(0.987, color="#555555", ls="--", lw=0.8)
    axes[1].set(ylabel="Conditional overlap", ylim=(0.983, 1.002), yticks=[0.987, 0.995, 1.0])
    axes[1].legend(
        handles=[
            Line2D([], [], color=colors[0], marker="o", ls="", label="Six-state minimum"),
            Line2D([], [], color=colors[1], marker="o", ls="", label="Choi overlap"),
        ],
        loc="lower right",
        bbox_to_anchor=(1, 1.02),
        ncol=2,
        fontsize=7,
    )
    point_series(axes[2], "split_ratio_input_1", colors[0])
    point_series(axes[2], "split_ratio_input_2", colors[1])
    for gate in (0.9, 1.1):
        axes[2].axhline(gate, color="#555555", ls="--", lw=0.8)
    axes[2].set(
        ylabel="Output power ratio",
        xlabel="Wavelength (nm)",
        ylim=(0.87, 1.13),
        yticks=[0.9, 1.0, 1.1],
        xlim=(1517, 1583),
        xticks=[1520, 1530, 1540, 1550, 1560, 1570, 1580],
    )
    axes[2].legend(
        handles=[
            Line2D([], [], color=colors[0], marker="o", ls="", label="Input 1"),
            Line2D([], [], color=colors[1], marker="o", ls="", label="Input 2"),
        ],
        loc="lower right",
        bbox_to_anchor=(1, 1.02),
        fontsize=7,
        ncol=2,
    )
    for label, ax in zip("abc", axes, strict=True):
        ax.annotate(
            label,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(-32, 6),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
            ha="left",
            va="bottom",
        )
        ax.tick_params(direction="out", length=3, width=0.8)
    fig.suptitle("One locked mask · seven discrete wavelength checks", y=0.985, fontsize=11)
    fig.legend(
        handles=[
            Line2D([], [], color="#555555", marker="o", ls="", label="Training wavelength"),
            Line2D([], [], color="#555555", marker="D", ls="", label="Held-out wavelength"),
            Line2D([], [], color="#555555", ls="--", label="Frozen acceptance gate"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.55, 0.955),
        ncol=3,
        fontsize=7,
    )
    stem = args.output / "spectrum-discrete"
    fig.canvas.draw()
    if args.qa_helper_dir:
        spec = importlib.util.spec_from_file_location(
            "panel_alignment", args.qa_helper_dir / "audit_panel_alignment.py"
        )
        alignment = importlib.util.module_from_spec(spec)
        import sys

        sys.modules[spec.name] = alignment
        spec.loader.exec_module(alignment)
        alignment.require_matplotlib_panel_alignment(
            fig,
            json_out=str(stem) + ".alignment.json",
            overlay_svg=str(stem) + ".alignment.svg",
            tolerance_pt=1.5,
            gutter_tolerance_pt=1.5,
            strict=True,
        )
    fig.savefig(str(stem) + ".png", dpi=300)
    fig.savefig(str(stem) + ".svg")
    fig.savefig(str(stem) + ".pdf")
    plt.close(fig)
    artifacts = [
        args.output / "spectrum-source-data.csv",
        Path(str(stem) + ".png"),
        Path(str(stem) + ".svg"),
        Path(str(stem) + ".pdf"),
    ]
    if args.qa_helper_dir:
        artifacts.extend([Path(str(stem) + ".alignment.json"), Path(str(stem) + ".alignment.svg")])
    for path in artifacts:
        if path.suffix in {".svg", ".json", ".csv"}:
            normalize_derived_text(path)
    (args.output / "spectrum-provenance.json").write_text(
        json.dumps(
            {
                "bundle_sha256": verify.digest(args.evidence / "bundle.json"),
                "script_sha256": verify.digest(Path(__file__)),
                "artifacts_sha256": {path.name: verify.digest(path) for path in artifacts},
                "text_normalization": "Generated text uses LF; SVG trailing spaces/tabs are removed before hashing",
                "points": 7,
                "source_runs": list(SPECTRAL_RUNS),
                "interpolation": False,
                "replicates": "One deterministic run per configuration; no statistical uncertainty inferred",
                "mesh_um": 0.02,
                "cladding_mesh_um": 0.08,
                "scope": "Seven discrete wavelength checks, not a continuous spectrum or bandwidth proof",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
