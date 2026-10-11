"""Draw the documented Hadamard workflow, not a measured performance plot."""

from pathlib import Path

import matplotlib


def main():
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "photonic-workflow-0.6.0"
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    output = Path(__file__).resolve().parents[1] / "images" / "showcase" / "hadamard-workflow"
    output.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5.8), layout="constrained")
    ax.set(xlim=(0, 12), ylim=(0, 5.8))
    ax.axis("off")
    fig.patch.set_facecolor("#f7f9fc")
    ax.text(0.2, 5.48, "A budgeted path from physics to a checked binary design", fontsize=17,
            weight="bold", color="#17324d")
    ax.text(0.2, 5.08, "Native COMSOL adjoint/MMA example  |  2D bulk-index surrogate", fontsize=11,
            color="#50647a")
    boxes = [
        (0.25, 3.05, "1  Freeze the problem", "Ports, modes, phase basis\nTarget U and engineering gates", "#17324d"),
        (4.35, 3.05, "2  Check the gradient",
         "6 native jobs / 12 FD comparisons\nFilter + projection + Maxwell", "#177e89"),
        (8.45, 3.05, "3  Optimize over 5 wavelengths",
         "5 continuation jobs; MMA\nbeta 2 -> 4 -> 8 -> 16 -> 32", "#177e89"),
        (8.45, 0.8, "4  Rebuild binary geometry",
         "At most 6 threshold trials\nNew solves for every contour", "#a85b18"),
        (4.35, 0.8, "5  Lock and qualify",
         "19 reserved runs / 13 pairs\nMesh, PML, domain, readout, holdouts", "#17324d"),
        (0.25, 0.8, "6  Audit and share",
         "Raw A/B, signed flux, receipts\nPublic numerical replay + figures", "#17324d"),
    ]
    width, height = 3.35, 1.45
    for x, y, title, detail, color in boxes:
        ax.add_patch(FancyBboxPatch((x, y), width, height,
                                   boxstyle="round,pad=0.08,rounding_size=0.1",
                                   facecolor="white", edgecolor=color, linewidth=1.5))
        ax.text(x + 0.16, y + 1.07, title, fontsize=10.5, weight="bold", color=color)
        ax.text(x + 0.16, y + 0.68, detail, fontsize=9.5, va="top", linespacing=1.7, color="#34495e")
    for start, end in [((3.68, 3.78), (4.2, 3.78)), ((7.78, 3.78), (8.3, 3.78)),
                       ((10.12, 2.94), (10.12, 2.4)), ((8.3, 1.53), (7.8, 1.53)),
                       ((4.2, 1.53), (3.7, 1.53))]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=15,
                                     linewidth=1.5, color="#73859a"))
    ax.text(0.2, 0.22,
            "Maximum budget: 6 + 5 + 6 + 19 = 36 native jobs. "
            "A job can contain many frequency and linear solves.",
            fontsize=10, color="#50647a")
    for suffix in ("png", "svg"):
        metadata = {"Creator": "photonic-workflow"}
        if suffix == "svg":
            metadata["Date"] = None
        fig.savefig(output / f"workflow.{suffix}", dpi=180, facecolor=fig.get_facecolor(),
                    metadata=metadata)
        if suffix == "svg":
            path = output / "workflow.svg"
            text = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())
            path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    plt.close(fig)


if __name__ == "__main__":
    main()
