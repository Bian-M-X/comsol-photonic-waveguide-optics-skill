"""Fail-closed COMSOL Java fragment renderers for reviewed numeric recipes.

Rendering never starts COMSOL, writes a file, or evaluates caller-supplied Java.
Feature-tag templates, Java variable shapes, and expressions are fixed in this
module. The public entry point accepts only an allowlisted recipe id/version,
numeric recipe parameters, and a validated instance namespace from which
collision-resistant identifiers are derived.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.geometry import (
    evaluate_circular_route,
    evaluate_symmetric_euler_bend,
)
from photonic_workflow.recipes.ports import evaluate_segmented_port_window
from photonic_workflow.recipes.renderers import (
    COMSOL_INTERNAL_RECIPE_IDS,
    MAX_COMSOL_CIRCULAR_VERTICES,
    MAX_COMSOL_EULER_SAMPLES,
    MAX_COMSOL_FRAGMENT_BYTES,
)
from photonic_workflow.security import validate_safe_label


@dataclass(frozen=True)
class ComsolJavaRecipeFragment:
    """A deterministic source fragment that is explicitly not executable here."""

    recipe_id: str
    recipe_version: str
    instance_id: str
    java_fragment: str
    claim_level: str
    will_execute: Literal[False] = field(default=False, init=False)

    @property
    def content(self) -> str:
        return self.java_fragment

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "recipe_id": self.recipe_id,
            "recipe_version": self.recipe_version,
            "instance_id": self.instance_id,
            "java_fragment": self.java_fragment,
            "claim_level": self.claim_level,
            "will_execute": self.will_execute,
        }


def _java_number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError("renderer received a non-numeric coordinate")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise InvalidInputError("renderer received an unrepresentable coordinate") from exc
    if not math.isfinite(number):
        raise InvalidInputError("renderer received a non-finite coordinate")
    if number == 0.0:
        return "0.0"
    rendered = format(number, ".17g")
    if "." not in rendered and "e" not in rendered.lower():
        rendered += ".0"
    return rendered


def _normalized(value: object) -> object:
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    return value


def _confirm_output(expected: dict[str, object], output: object) -> None:
    if output is None:
        return
    if not isinstance(output, dict) or _normalized(output) != _normalized(expected):
        raise InvalidInputError("provided recipe output does not match a fresh evaluation")


def _instance_prefix(instance_id: str) -> str:
    label = validate_safe_label(instance_id)
    java_safe = re.sub(r"[^A-Za-z0-9_]", "_", label)
    digest = hashlib.sha256(label.encode("ascii")).hexdigest()[:10]
    return f"recipe_{java_safe[:48]}_{digest}"


def _apply_instance_namespace(fragment: str, instance_id: str) -> str:
    prefix = _instance_prefix(instance_id)
    namespaced = fragment.replace("recipe_", f"{prefix}_").replace(
        "recipeEulerBoundary",
        f"{prefix}EulerBoundary",
    )
    if len(namespaced.encode("utf-8")) > MAX_COMSOL_FRAGMENT_BYTES:
        raise InvalidInputError(
            "COMSOL Java fragment exceeds the reviewed source-size limit"
        )
    return namespaced


def _rectangle_feature(tag: str, bounds: tuple[float, float, float, float]) -> list[str]:
    x_min, x_max, y_min, y_max = bounds
    position = f"{_java_number(x_min)}, {_java_number(y_min)}"
    size = f"{_java_number(x_max - x_min)}, {_java_number(y_max - y_min)}"
    return [
        f'g.create("{tag}", "Rectangle");',
        f'g.feature("{tag}").set("base", "corner");',
        f'g.feature("{tag}").set("pos", new double[]{{{position}}});',
        f'g.feature("{tag}").set("size", new double[]{{{size}}});',
    ]


def _straight_feature(
    tag: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
) -> list[str]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= 1e-12:
        raise InvalidInputError("circular-route straight segment is degenerate")
    offset_x = -0.5 * width * dy / length
    offset_y = 0.5 * width * dx / length
    points = (
        (start[0] + offset_x, start[1] + offset_y),
        (end[0] + offset_x, end[1] + offset_y),
        (end[0] - offset_x, end[1] - offset_y),
        (start[0] - offset_x, start[1] - offset_y),
    )
    rows = ",\n".join(
        f"  {{{_java_number(point[0])}, {_java_number(point[1])}}}"
        for point in points
    )
    return [
        f'double[][] {tag}Table = new double[][]{{\n{rows}\n}};',
        f'g.create("{tag}", "Polygon");',
        f'g.feature("{tag}").set("source", "table");',
        f'g.feature("{tag}").set("table", {tag}Table);',
    ]


def _box_selection_feature(
    tag: str,
    bounds: tuple[float, float, float, float],
    *,
    entity_dimension: int,
) -> list[str]:
    x_min, x_max, y_min, y_max = bounds
    return [
        f'g.create("{tag}", "BoxSelection");',
        f'g.feature("{tag}").set("entitydim", {entity_dimension});',
        f'g.feature("{tag}").set("xmin", {_java_number(x_min)});',
        f'g.feature("{tag}").set("xmax", {_java_number(x_max)});',
        f'g.feature("{tag}").set("ymin", {_java_number(y_min)});',
        f'g.feature("{tag}").set("ymax", {_java_number(y_max)});',
        f'g.feature("{tag}").set("condition", "inside");',
        f'g.feature("{tag}").set("selkeep", "on");',
    ]


def _render_circular_route(output: dict[str, object]) -> str:
    bends = output["bends"]
    if not isinstance(bends, (list, tuple)):
        raise InvalidInputError("circular-route output has invalid bends")
    vertices = output["vertices_um"]
    if not isinstance(vertices, (list, tuple)) or len(vertices) < 2:
        raise InvalidInputError("circular-route output has invalid vertices")
    if len(vertices) > MAX_COMSOL_CIRCULAR_VERTICES:
        raise InvalidInputError(
            "COMSOL circular-route renderer supports at most "
            f"{MAX_COMSOL_CIRCULAR_VERTICES} vertices"
        )
    width = float(output["width_um"])
    lines = [
        "// photonic-workflow circular-route recipe; analytic geometry configuration only",
        "// will_execute=false; no solver or physics claim is made by this fragment",
        "// target must be a fresh 2D geometry or already use lengthUnit=um",
        'g.lengthUnit("um");',
    ]
    inputs: list[str] = []
    cursor = tuple(vertices[0])
    for index, bend in enumerate(bends):
        if not isinstance(bend, dict):
            raise InvalidInputError("circular-route output contains an invalid bend")
        tangent_in = bend["t1"]
        tangent_out = bend["t2"]
        if (
            not isinstance(tangent_in, (list, tuple))
            or len(tangent_in) != 2
            or not isinstance(tangent_out, (list, tuple))
            or len(tangent_out) != 2
        ):
            raise InvalidInputError("circular-route output contains invalid tangent points")
        tangent_in_pair = (float(tangent_in[0]), float(tangent_in[1]))
        if math.dist(cursor, tangent_in_pair) > 1e-12:
            straight = f"recipe_circular_straight_{index}"
            lines.extend(_straight_feature(straight, cursor, tangent_in_pair, width))
            inputs.append(straight)
        center = bend["center"]
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            raise InvalidInputError("circular-route output contains an invalid bend center")
        radius = float(bend["radius"])
        sweep = math.degrees(float(bend["a1"]) - float(bend["a0"]))
        rotation = math.degrees(float(bend["a0"]))
        if sweep < 0.0:
            rotation = math.degrees(float(bend["a1"]))
            sweep = -sweep
        outer = f"recipe_circular_outer_{index}"
        inner = f"recipe_circular_inner_{index}"
        result = f"recipe_circular_bend_{index}"
        center_literal = f"{_java_number(center[0])}, {_java_number(center[1])}"
        lines.extend(
            (
                f'g.create("{outer}", "Circle");',
                f'g.feature("{outer}").set("type", "solid");',
                f'g.feature("{outer}").set("r", {_java_number(radius + 0.5 * width)});',
                f'g.feature("{outer}").set("pos", new double[]{{{center_literal}}});',
                f'g.feature("{outer}").set("angle", {_java_number(sweep)});',
                f'g.feature("{outer}").set("rot", {_java_number(rotation)});',
                f'g.create("{inner}", "Circle");',
                f'g.feature("{inner}").set("type", "solid");',
                f'g.feature("{inner}").set("r", {_java_number(radius - 0.5 * width)});',
                f'g.feature("{inner}").set("pos", new double[]{{{center_literal}}});',
                f'g.feature("{inner}").set("angle", {_java_number(sweep)});',
                f'g.feature("{inner}").set("rot", {_java_number(rotation)});',
                f'g.create("{result}", "Difference");',
                f'g.feature("{result}").selection("input").set(new String[]{{"{outer}"}});',
                f'g.feature("{result}").selection("input2").set(new String[]{{"{inner}"}});',
                f'g.feature("{result}").set("intbnd", "off");',
            )
        )
        inputs.append(result)
        cursor = (float(tangent_out[0]), float(tangent_out[1]))
    final_point = tuple(vertices[-1])
    if math.dist(cursor, final_point) > 1e-12:
        straight = f"recipe_circular_straight_{len(bends)}"
        lines.extend(_straight_feature(straight, cursor, final_point, width))
        inputs.append(straight)
    if not inputs:
        raise InvalidInputError("circular-route renderer produced no geometry features")
    input_literal = ", ".join(f'"{tag}"' for tag in inputs)
    lines.extend(
        (
            'g.create("recipe_circular_route", "Union");',
            'g.feature("recipe_circular_route").selection("input").set('
            f"new String[]{{{input_literal}}});",
            'g.feature("recipe_circular_route").set("intbnd", "off");',
        )
    )
    return "\n".join(lines) + "\n"


def _render_symmetric_euler(output: dict[str, object]) -> str:
    samples = output.get("samples")
    if (
        isinstance(samples, bool)
        or not isinstance(samples, int)
        or samples > MAX_COMSOL_EULER_SAMPLES
    ):
        raise InvalidInputError(
            "COMSOL Euler renderer requires an integer sample count no greater than "
            f"{MAX_COMSOL_EULER_SAMPLES}"
        )
    boundary = output["boundary_table"]
    if not isinstance(boundary, (list, tuple)) or not boundary:
        raise InvalidInputError("Euler output has an invalid boundary table")
    rows: list[str] = []
    for point in boundary:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise InvalidInputError("Euler boundary row must contain two coordinates")
        rows.append(f"  {{{_java_number(point[0])}, {_java_number(point[1])}}}")
    table = ",\n".join(rows)
    return (
        "// photonic-workflow symmetric Euler recipe; 2D EIM configuration only\n"
        "// will_execute=false; this numeric fragment does not run a solver\n"
        "// target must be a fresh 2D geometry or already use lengthUnit=um\n"
        'g.lengthUnit("um");\n'
        "double[][] recipeEulerBoundary = new double[][]{\n"
        f"{table}\n"
        "};\n"
        'g.create("recipe_euler_bend", "InterpolationCurve");\n'
        'g.feature("recipe_euler_bend").set("type", "solid");\n'
        'g.feature("recipe_euler_bend").set("source", "table");\n'
        'g.feature("recipe_euler_bend").set("table", recipeEulerBoundary);\n'
        'g.feature("recipe_euler_bend").set("rtol", 0.0);\n'
    )


def _render_segmented_ports(output: dict[str, object]) -> str:
    slabs = output["background_slabs"]
    windows = output["port_windows"]
    if not isinstance(slabs, (list, tuple)) or len(slabs) != 3:
        raise InvalidInputError("segmented-port output must contain three slabs")
    if not isinstance(windows, (list, tuple)) or len(windows) != 2:
        raise InvalidInputError("segmented-port output must contain two windows")

    lines = [
        "// photonic-workflow segmented port-window recipe; 2D EIM configuration only",
        "// will_execute=false; entity counts and zero port/scattering overlap remain mandatory",
        "// target must be a fresh 2D geometry or already use lengthUnit=um",
        'g.lengthUnit("um");',
    ]
    slab_tags = ("recipe_bg_lower", "recipe_bg_port", "recipe_bg_upper")
    for tag, slab in zip(slab_tags, slabs, strict=True):
        if not isinstance(slab, dict):
            raise InvalidInputError("segmented-port output contains an invalid slab")
        lines.extend(_rectangle_feature(tag, tuple(slab["bounds_um"])))

    window_tags = ("recipe_port_1_boundary", "recipe_port_2_boundary")
    for tag, window in zip(window_tags, windows, strict=True):
        if not isinstance(window, dict):
            raise InvalidInputError("segmented-port output contains an invalid window")
        lines.extend(_box_selection_feature(tag, tuple(window["bounds_um"]), entity_dimension=1))

    left_x = float(windows[0]["bounds_um"][0])
    right_x = float(windows[1]["bounds_um"][1])
    tolerance = 0.5 * (
        float(windows[0]["bounds_um"][1]) - float(windows[0]["bounds_um"][0])
    )
    y_min = float(slabs[0]["bounds_um"][2])
    y_max = float(slabs[-1]["bounds_um"][3])
    x_min = left_x + tolerance
    x_max = right_x - tolerance
    exterior = {
        "recipe_exterior_top": (x_min - tolerance, x_max + tolerance, y_max - tolerance, y_max + tolerance),
        "recipe_exterior_bottom": (x_min - tolerance, x_max + tolerance, y_min - tolerance, y_min + tolerance),
        "recipe_exterior_left": (x_min - tolerance, x_min + tolerance, y_min - tolerance, y_max + tolerance),
        "recipe_exterior_right": (x_max - tolerance, x_max + tolerance, y_min - tolerance, y_max + tolerance),
    }
    for tag, bounds in exterior.items():
        lines.extend(_box_selection_feature(tag, bounds, entity_dimension=1))
    lines.extend(
        (
            'g.create("recipe_port_boundaries", "UnionSelection");',
            'g.feature("recipe_port_boundaries").set("entitydim", 1);',
            'g.feature("recipe_port_boundaries").set("input", new String[]{'
            '"recipe_port_1_boundary", "recipe_port_2_boundary"});',
            'g.create("recipe_left_scattering", "DifferenceSelection");',
            'g.feature("recipe_left_scattering").set("entitydim", 1);',
            'g.feature("recipe_left_scattering").set("add", new String[]{"recipe_exterior_left"});',
            'g.feature("recipe_left_scattering").set("subtract", new String[]{"recipe_port_boundaries"});',
            'g.create("recipe_right_scattering", "DifferenceSelection");',
            'g.feature("recipe_right_scattering").set("entitydim", 1);',
            'g.feature("recipe_right_scattering").set("add", new String[]{"recipe_exterior_right"});',
            'g.feature("recipe_right_scattering").set("subtract", new String[]{"recipe_port_boundaries"});',
            'g.create("recipe_scattering_boundaries", "UnionSelection");',
            'g.feature("recipe_scattering_boundaries").set("entitydim", 1);',
            'g.feature("recipe_scattering_boundaries").set("input", new String[]{'
            '"recipe_exterior_top", "recipe_exterior_bottom", '
            '"recipe_left_scattering", "recipe_right_scattering"});',
        )
    )
    return "\n".join(lines) + "\n"


def render_comsol_java_fragment(
    recipe_id: str,
    recipe_version: str,
    parameters: dict[str, Any],
    output: dict[str, object] | None = None,
    *,
    instance_id: str,
) -> ComsolJavaRecipeFragment:
    """Render one allowlisted numeric recipe with fixed Java identifiers."""

    if recipe_version != "1.0.0":
        raise InvalidInputError(
            f"unsupported COMSOL recipe version: {recipe_version!r}"
        )
    if recipe_id not in COMSOL_INTERNAL_RECIPE_IDS:
        raise InvalidInputError(f"unsupported COMSOL recipe id: {recipe_id!r}")
    if recipe_id == "circular-route":
        evaluated = evaluate_circular_route(parameters)
        _confirm_output(evaluated, output)
        fragment = _render_circular_route(evaluated)
        claim_level = "analytic-geometry-configuration"
    elif recipe_id == "symmetric-euler-bend":
        evaluated = evaluate_symmetric_euler_bend(parameters)
        _confirm_output(evaluated, output)
        fragment = _render_symmetric_euler(evaluated)
        claim_level = "configuration-only-2d-eim"
    elif recipe_id == "segmented-port-window":
        evaluated = evaluate_segmented_port_window(parameters)
        _confirm_output(evaluated, output)
        fragment = _render_segmented_ports(evaluated)
        claim_level = "configuration-only-2d-eim"
    else:
        raise RuntimeError(f"registered COMSOL recipe has no renderer: {recipe_id}")
    return ComsolJavaRecipeFragment(
        recipe_id=recipe_id,
        recipe_version=recipe_version,
        instance_id=instance_id,
        java_fragment=_apply_instance_namespace(fragment, instance_id),
        claim_level=claim_level,
    )


def render_symmetric_euler_bend_fragment(
    turn_angle_deg: float,
    minimum_radius_um: float,
    width_um: float,
    samples: int = 64,
    *,
    instance_id: str,
) -> ComsolJavaRecipeFragment:
    parameters = {
        "turn_angle_deg": turn_angle_deg,
        "minimum_radius_um": minimum_radius_um,
        "width_um": width_um,
        "samples": samples,
    }
    return render_comsol_java_fragment(
        "symmetric-euler-bend",
        "1.0.0",
        parameters,
        instance_id=instance_id,
    )


def render_segmented_port_window_fragment(
    x_min_um: float,
    x_max_um: float,
    y_min_um: float,
    y_max_um: float,
    port_center_y_um: float,
    port_half_height_um: float,
    selection_tolerance_um: float = 0.008,
    *,
    instance_id: str,
) -> ComsolJavaRecipeFragment:
    parameters = {
        "x_min_um": x_min_um,
        "x_max_um": x_max_um,
        "y_min_um": y_min_um,
        "y_max_um": y_max_um,
        "port_center_y_um": port_center_y_um,
        "port_half_height_um": port_half_height_um,
        "selection_tolerance_um": selection_tolerance_um,
    }
    return render_comsol_java_fragment(
        "segmented-port-window",
        "1.0.0",
        parameters,
        instance_id=instance_id,
    )


# Compatibility artifact for the historical helper-emitter script.  The active
# renderers above never accept a caller-provided tag or Java expression.
CIRCULAR_BEND_JAVA_HELPER = r'''// Analytic 2D circular-bend helper skeleton for COMSOL Java API.
// Paste into a model class that already imports com.comsol.model.* and uses a 2D GeomSequence.
static final double BEND_ANGLE_EPS_RAD = 1e-9;
static final double BEND_LENGTH_EPS = 1e-12;

static class P {
  final double x, y;
  P(double x, double y) { this.x = x; this.y = y; }
  P add(P o) { return new P(x + o.x, y + o.y); }
  P sub(P o) { return new P(x - o.x, y - o.y); }
  P mul(double s) { return new P(x * s, y * s); }
}

static class BendSpec {
  final P t1, t2, center;
  final double radius, a0, a1;
  BendSpec(P t1, P t2, P center, double radius, double a0, double a1) {
    this.t1 = t1; this.t2 = t2; this.center = center;
    this.radius = radius; this.a0 = a0; this.a1 = a1;
  }
}

static P p(double x, double y) { return new P(x, y); }
static double norm(P v) { return Math.hypot(v.x, v.y); }
static P unit(P v) {
  double n = norm(v);
  if (!Double.isFinite(n) || n <= BEND_LENGTH_EPS) {
    throw new IllegalArgumentException("cannot normalize a zero-length or non-finite vector");
  }
  return new P(v.x / n, v.y / n);
}
static P leftNormal(P v) { return new P(-v.y, v.x); }

static java.util.List<BendSpec> bendSpecs(java.util.List<P> vertices, double radius) {
  if (vertices == null || vertices.size() < 2) {
    throw new IllegalArgumentException("bend polyline must contain at least two vertices");
  }
  if (!Double.isFinite(radius) || radius <= 0.0) {
    throw new IllegalArgumentException("bend radius must be finite and positive");
  }
  java.util.ArrayList<BendSpec> bends = new java.util.ArrayList<BendSpec>();
  for (int i = 1; i < vertices.size() - 1; i++) {
    P a = vertices.get(i - 1), b = vertices.get(i), c = vertices.get(i + 1);
    double lin = norm(b.sub(a));
    double lout = norm(c.sub(b));
    if (!Double.isFinite(lin) || !Double.isFinite(lout)
        || lin <= BEND_LENGTH_EPS || lout <= BEND_LENGTH_EPS) {
      throw new IllegalArgumentException("corner " + i + " has a zero-length or non-finite adjacent segment");
    }
    P din = unit(b.sub(a));
    P dout = unit(c.sub(b));
    double cross = din.x * dout.y - din.y * dout.x;
    double dot = Math.max(-1.0, Math.min(1.0, din.x * dout.x + din.y * dout.y));
    double turn = Math.atan2(cross, dot);
    double absTurn = Math.abs(turn);
    if (absTurn <= BEND_ANGLE_EPS_RAD) {
      throw new IllegalArgumentException("corner " + i + " turn angle is zero or too close to 0 radians");
    }
    if (Math.PI - absTurn <= BEND_ANGLE_EPS_RAD) {
      throw new IllegalArgumentException("corner " + i + " turn angle is too close to 180 degrees");
    }
    double cutback = radius * Math.tan(0.5 * absTurn);
    double fitTolerance = BEND_LENGTH_EPS * Math.max(1.0, Math.max(Math.max(lin, lout), cutback));
    if (!Double.isFinite(cutback) || cutback > lin + fitTolerance || cutback > lout + fitTolerance) {
      throw new IllegalArgumentException(
          "corner " + i + " requested radius " + radius + " requires tangent cutback " + cutback
          + ", which does not fit the adjacent segments");
    }
    P t1 = b.sub(din.mul(cutback));
    P t2 = b.add(dout.mul(cutback));
    P n = leftNormal(din);
    if (turn < 0.0) n = n.mul(-1.0);
    P center = t1.add(n.mul(radius));
    double circleTolerance = 1e-9 * Math.max(1.0, radius);
    if (Math.abs(norm(t1.sub(center)) - radius) > circleTolerance
        || Math.abs(norm(t2.sub(center)) - radius) > circleTolerance) {
      throw new IllegalStateException("corner " + i
          + " tangent points do not lie on the requested-radius circle");
    }
    double a0 = Math.atan2(t1.y - center.y, t1.x - center.x);
    double a1 = Math.atan2(t2.y - center.y, t2.x - center.x);
    if (turn > 0.0 && a1 < a0) a1 += 2.0 * Math.PI;
    if (turn < 0.0 && a1 > a0) a1 -= 2.0 * Math.PI;
    bends.add(new BendSpec(t1, t2, center, radius, a0, a1));
  }
  for (int i = 0; i + 1 < bends.size(); i++) {
    P direction = unit(vertices.get(i + 2).sub(vertices.get(i + 1)));
    double remaining = bends.get(i + 1).t1.sub(bends.get(i).t2).x * direction.x
        + bends.get(i + 1).t1.sub(bends.get(i).t2).y * direction.y;
    if (!Double.isFinite(remaining) || remaining <= BEND_LENGTH_EPS) {
      throw new IllegalArgumentException("adjacent bend cutbacks overlap on shared segment " + (i + 1));
    }
  }
  return bends;
}

static double roundedExactLength(java.util.List<P> vertices, double radius) {
  java.util.List<BendSpec> bends = bendSpecs(vertices, radius);
  double sum = 0.0;
  P cursor = vertices.get(0);
  for (BendSpec b : bends) {
    sum += norm(b.t1.sub(cursor));
    sum += Math.abs(b.a1 - b.a0) * b.radius;
    cursor = b.t2;
  }
  sum += norm(vertices.get(vertices.size() - 1).sub(cursor));
  return sum;
}

static String addAnalyticBendCore(GeomSequence g, String tag, BendSpec b, double width) {
  if (!Double.isFinite(width) || width <= 0.0 || width >= 2.0 * b.radius) {
    throw new IllegalArgumentException(
      "waveguide width must be finite, positive, and smaller than twice the bend radius"
    );
  }
  double h = 0.5 * width;
  double sweepDeg = Math.toDegrees(b.a1 - b.a0);
  double rotDeg = Math.toDegrees(b.a0);
  double angleDeg = sweepDeg;
  if (sweepDeg < 0.0) {
    rotDeg = Math.toDegrees(b.a1);
    angleDeg = -sweepDeg;
  }
  String outer = tag + "_outer";
  String inner = tag + "_inner";
  g.create(outer, "Circle");
  g.feature(outer).set("type", "solid");
  g.feature(outer).set("r", b.radius + h);
  g.feature(outer).set("pos", new double[]{b.center.x, b.center.y});
  g.feature(outer).set("angle", angleDeg);
  g.feature(outer).set("rot", rotDeg);
  g.create(inner, "Circle");
  g.feature(inner).set("type", "solid");
  g.feature(inner).set("r", b.radius - h);
  g.feature(inner).set("pos", new double[]{b.center.x, b.center.y});
  g.feature(inner).set("angle", angleDeg);
  g.feature(inner).set("rot", rotDeg);
  g.create(tag, "Difference");
  g.feature(tag).selection("input").set(new String[]{outer});
  g.feature(tag).selection("input2").set(new String[]{inner});
  g.feature(tag).set("intbnd", "off");
  return tag;
}
'''


__all__ = [
    "CIRCULAR_BEND_JAVA_HELPER",
    "ComsolJavaRecipeFragment",
    "render_comsol_java_fragment",
    "render_segmented_port_window_fragment",
    "render_symmetric_euler_bend_fragment",
]
