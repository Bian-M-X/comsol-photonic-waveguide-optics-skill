"""Pure geometry recipes for deterministic 2D photonic model construction.

The functions in this module do not import, start, or call a solver.  They
produce finite numeric geometry only.  Solver-specific renderers may consume
the returned tables, but the resulting evidence remains configuration-level
until an independently verified solver gate passes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from numbers import Real
from typing import Any, TypeAlias

from photonic_workflow.exceptions import InvalidInputError

Point2D: TypeAlias = tuple[float, float]

ANGLE_EPS_RAD = 1e-9
LENGTH_EPS = 1e-12
MIN_EULER_SAMPLES = 8
MAX_EULER_SAMPLES = 4096


def _finite_real(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidInputError(f"{name} must be a real number")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise InvalidInputError(f"{name} must be representable as a finite number") from exc
    if not math.isfinite(result):
        raise InvalidInputError(f"{name} must be finite")
    return result


def _finite_point(name: str, point: object) -> Point2D:
    if (
        isinstance(point, (str, bytes, bytearray))
        or not isinstance(point, Sequence)
        or len(point) != 2
    ):
        raise InvalidInputError(f"{name} must contain exactly two finite coordinates")
    return (
        _finite_real(f"{name}[0]", point[0]),
        _finite_real(f"{name}[1]", point[1]),
    )


def compute_circular_bend(
    a: Point2D,
    b: Point2D,
    c: Point2D,
    radius: float,
) -> dict[str, object]:
    """Compute one exact-radius tangent circular fillet.

    The signed turn is measured from ``a -> b`` to ``b -> c``.  The requested
    radius is never silently reduced: a corner that cannot contain the
    required tangent cutback fails closed.
    """

    a = _finite_point("a", a)
    b = _finite_point("b", b)
    c = _finite_point("c", c)
    radius = _finite_real("radius", radius)
    if radius <= 0.0:
        raise InvalidInputError("bend radius must be positive")

    incoming = (b[0] - a[0], b[1] - a[1])
    outgoing = (c[0] - b[0], c[1] - b[1])
    incoming_length = math.hypot(*incoming)
    outgoing_length = math.hypot(*outgoing)
    if incoming_length <= LENGTH_EPS or outgoing_length <= LENGTH_EPS:
        raise InvalidInputError("corner has a zero-length incoming or outgoing segment")

    din = (incoming[0] / incoming_length, incoming[1] / incoming_length)
    dout = (outgoing[0] / outgoing_length, outgoing[1] / outgoing_length)
    cross = din[0] * dout[1] - din[1] * dout[0]
    dot = max(-1.0, min(1.0, din[0] * dout[0] + din[1] * dout[1]))
    turn = math.atan2(cross, dot)
    abs_turn = abs(turn)
    if abs_turn <= ANGLE_EPS_RAD:
        raise InvalidInputError("turn angle is zero or too close to 0 radians")
    if math.pi - abs_turn <= ANGLE_EPS_RAD:
        raise InvalidInputError("turn angle is too close to 180 degrees")

    cutback = radius * math.tan(0.5 * abs_turn)
    fit_tolerance = LENGTH_EPS * max(1.0, incoming_length, outgoing_length, cutback)
    if (
        not math.isfinite(cutback)
        or cutback > incoming_length + fit_tolerance
        or cutback > outgoing_length + fit_tolerance
    ):
        raise InvalidInputError(
            f"requested radius {radius:g} requires tangent cutback {cutback:g}, "
            "which does not fit the adjacent segments"
        )

    t1 = (b[0] - cutback * din[0], b[1] - cutback * din[1])
    t2 = (b[0] + cutback * dout[0], b[1] + cutback * dout[1])
    normal = (-din[1], din[0])
    if turn < 0.0:
        normal = (-normal[0], -normal[1])
    center = (t1[0] + radius * normal[0], t1[1] + radius * normal[1])
    a0 = math.atan2(t1[1] - center[1], t1[0] - center[0])
    a1 = math.atan2(t2[1] - center[1], t2[0] - center[0])
    if turn > 0.0 and a1 < a0:
        a1 += 2.0 * math.pi
    if turn < 0.0 and a1 > a0:
        a1 -= 2.0 * math.pi

    return {
        "t1": t1,
        "t2": t2,
        "center": center,
        "radius": float(radius),
        "cutback": cutback,
        "turn": turn,
        "a0": a0,
        "a1": a1,
    }


def compute_circular_route(
    vertices: Sequence[Point2D],
    radius: float,
    width: float,
) -> dict[str, object]:
    """Compute exact circular bends and centerline length for a routed path."""

    if isinstance(vertices, (str, bytes, bytearray)) or not isinstance(vertices, Sequence):
        raise InvalidInputError("route vertices must be a sequence of 2D points")
    if len(vertices) < 2:
        raise InvalidInputError("route must contain at least two vertices")
    normalized_vertices = tuple(
        _finite_point(f"vertices[{index}]", point) for index, point in enumerate(vertices)
    )
    for index, (left, right) in enumerate(pairwise(normalized_vertices)):
        if math.dist(left, right) <= LENGTH_EPS:
            raise InvalidInputError(
                f"route segment {index} has zero or near-zero length"
            )
    width = _finite_real("width", width)
    radius = _finite_real("radius", radius)
    if width <= 0.0:
        raise InvalidInputError("waveguide width must be positive")
    if radius <= 0.0:
        raise InvalidInputError("bend radius must be positive")
    if width >= 2.0 * radius:
        raise InvalidInputError("width must be smaller than twice the bend radius")

    bends = tuple(
        compute_circular_bend(
            normalized_vertices[index - 1],
            normalized_vertices[index],
            normalized_vertices[index + 1],
            radius,
        )
        for index in range(1, len(normalized_vertices) - 1)
    )
    for index in range(len(bends) - 1):
        segment_start = normalized_vertices[index + 1]
        segment_end = normalized_vertices[index + 2]
        segment_length = math.dist(segment_start, segment_end)
        required = float(bends[index]["cutback"]) + float(bends[index + 1]["cutback"])
        tolerance = LENGTH_EPS * max(1.0, segment_length, required)
        if required >= segment_length - tolerance:
            raise InvalidInputError(
                f"adjacent cutbacks require {required:g} on shared segment of length "
                f"{segment_length:g}"
            )

    original_length = sum(math.dist(left, right) for left, right in pairwise(normalized_vertices))
    removed = 2.0 * sum(float(bend["cutback"]) for bend in bends)
    arc_length = sum(abs(float(bend["turn"])) * radius for bend in bends)
    return {
        "vertices": normalized_vertices,
        "radius": float(radius),
        "width": float(width),
        "bends": bends,
        "centerline_length": original_length - removed + arc_length,
    }


def _validate_euler_parameters(
    turn_angle_deg: float,
    minimum_radius_um: float,
    width_um: float,
    samples: int,
) -> tuple[float, float, float, int]:
    turn_angle = _finite_real("turn_angle_deg", turn_angle_deg)
    radius = _finite_real("minimum_radius_um", minimum_radius_um)
    width = _finite_real("width_um", width_um)
    turn_radians = math.radians(turn_angle)
    abs_turn = abs(turn_radians)
    if abs_turn <= ANGLE_EPS_RAD:
        raise InvalidInputError("Euler turn angle is zero or too close to 0 degrees")
    if math.pi - abs_turn <= ANGLE_EPS_RAD or abs_turn > math.pi:
        raise InvalidInputError("Euler turn angle must have magnitude strictly below 180 degrees")
    if radius <= 0.0:
        raise InvalidInputError("Euler minimum radius must be positive")
    if width <= 0.0:
        raise InvalidInputError("Euler waveguide width must be positive")
    if width >= 2.0 * radius:
        raise InvalidInputError("Euler width must be smaller than twice the minimum radius")
    if isinstance(samples, bool) or not isinstance(samples, int):
        raise InvalidInputError("Euler samples must be an even integer")
    if samples < MIN_EULER_SAMPLES or samples > MAX_EULER_SAMPLES or samples % 2:
        raise InvalidInputError(
            f"Euler samples must be an even integer from {MIN_EULER_SAMPLES} "
            f"through {MAX_EULER_SAMPLES}"
        )
    return turn_radians, radius, width, samples


def _symmetric_euler_heading(abs_turn: float, radius: float, distance: float) -> float:
    half_length = radius * abs_turn
    if distance <= half_length:
        return distance * distance / (2.0 * radius * half_length)
    remaining = distance - half_length
    return (
        0.5 * abs_turn
        + remaining / radius
        - remaining * remaining / (2.0 * radius * half_length)
    )


def compute_symmetric_euler_bend(
    turn_angle_deg: float,
    minimum_radius_um: float,
    width_um: float,
    samples: int = 64,
) -> dict[str, object]:
    """Return a symmetric Euler bend in a fixed local coordinate frame.

    The bend starts at ``(0, 0)`` with tangent ``(+x)``.  Positive angles turn
    left and negative angles turn right.  Curvature rises linearly from zero to
    ``1 / minimum_radius_um`` at the midpoint and then falls linearly to zero.

    ``boundary_table`` is ordered as the left offset forward followed by the
    right offset in reverse.  It is suitable as numeric input to a solver
    interpolation-curve *configuration*, but it is not solver or physics
    validation.
    """

    turn, radius, width, samples = _validate_euler_parameters(
        turn_angle_deg,
        minimum_radius_um,
        width_um,
        samples,
    )
    direction = 1.0 if turn > 0.0 else -1.0
    abs_turn = abs(turn)
    length = 2.0 * radius * abs_turn
    step = length / samples

    centerline: list[Point2D] = [(0.0, 0.0)]
    tangents: list[Point2D] = [(1.0, 0.0)]
    for index in range(samples):
        midpoint_distance = (index + 0.5) * step
        midpoint_heading = direction * _symmetric_euler_heading(
            abs_turn,
            radius,
            midpoint_distance,
        )
        previous = centerline[-1]
        centerline.append(
            (
                previous[0] + step * math.cos(midpoint_heading),
                previous[1] + step * math.sin(midpoint_heading),
            )
        )
        endpoint_heading = direction * _symmetric_euler_heading(
            abs_turn,
            radius,
            (index + 1) * step,
        )
        tangents.append((math.cos(endpoint_heading), math.sin(endpoint_heading)))

    endpoint = centerline[-1]
    outgoing = (math.cos(turn), math.sin(turn))
    virtual_corner_vector = (1.0 + outgoing[0], outgoing[1])
    denominator = (
        virtual_corner_vector[0] * virtual_corner_vector[0]
        + virtual_corner_vector[1] * virtual_corner_vector[1]
    )
    cutback = (
        endpoint[0] * virtual_corner_vector[0]
        + endpoint[1] * virtual_corner_vector[1]
    ) / denominator
    if not math.isfinite(cutback) or cutback <= 0.0:
        raise InvalidInputError(
            "Euler cutback calculation produced a non-finite or non-positive result"
        )

    half_width = 0.5 * width
    left: list[Point2D] = []
    right: list[Point2D] = []
    for point, tangent in zip(centerline, tangents, strict=True):
        normal = (-tangent[1], tangent[0])
        left.append((point[0] + half_width * normal[0], point[1] + half_width * normal[1]))
        right.append((point[0] - half_width * normal[0], point[1] - half_width * normal[1]))
    boundary_table = tuple((*left, *reversed(right)))
    if not all(math.isfinite(value) for point in boundary_table for value in point):
        raise InvalidInputError("Euler boundary calculation produced a non-finite coordinate")

    centerline_result = tuple(centerline)
    tangent_result = tuple(tangents)
    return {
        "turn_angle_deg": float(turn_angle_deg),
        "minimum_radius_um": radius,
        "width_um": width,
        "samples": samples,
        "centerline": centerline_result,
        "tangent": tangent_result,
        "tangents": tangent_result,
        "boundary_table": boundary_table,
        "length": length,
        "centerline_length": length,
        "cutback": cutback,
        "length_unit": "um",
        "claim_level": "configuration-only-2d-eim",
    }


compute_euler_bend = compute_symmetric_euler_bend

_CIRCULAR_ROUTE_PARAMETER_KEYS = frozenset({"vertices_um", "radius_um", "width_um"})
_SYMMETRIC_EULER_PARAMETER_KEYS = frozenset(
    {"turn_angle_deg", "minimum_radius_um", "width_um", "samples"}
)


def _validated_parameter_dict(
    recipe_name: str,
    parameters: Mapping[str, Any],
    allowed: frozenset[str],
    required: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(parameters, Mapping):
        raise InvalidInputError("parameters must be an object")
    unknown = set(parameters) - allowed
    if unknown:
        raise InvalidInputError(f"unknown {recipe_name} parameter(s): {sorted(unknown)}")
    missing = required - set(parameters)
    if missing:
        raise InvalidInputError(f"missing {recipe_name} parameter(s): {sorted(missing)}")
    return parameters


def evaluate_circular_route(parameters: Mapping[str, Any]) -> dict[str, object]:
    """Catalog-facing circular-route evaluator with a closed parameter schema."""

    values = _validated_parameter_dict(
        "circular-route",
        parameters,
        _CIRCULAR_ROUTE_PARAMETER_KEYS,
        _CIRCULAR_ROUTE_PARAMETER_KEYS,
    )
    vertices = values["vertices_um"]
    if not isinstance(vertices, (list, tuple)):
        raise InvalidInputError("vertices_um must be a list or tuple of 2D points")
    computed = compute_circular_route(
        list(vertices),
        radius=values["radius_um"],
        width=values["width_um"],
    )
    return {
        "vertices_um": computed["vertices"],
        "radius_um": computed["radius"],
        "width_um": computed["width"],
        "bends": computed["bends"],
        "centerline_length_um": computed["centerline_length"],
        "length_unit": "um",
    }


def evaluate_symmetric_euler_bend(parameters: Mapping[str, Any]) -> dict[str, object]:
    """Catalog-facing Euler evaluator with a closed parameter schema."""

    values = _validated_parameter_dict(
        "symmetric-euler-bend",
        parameters,
        _SYMMETRIC_EULER_PARAMETER_KEYS,
        _SYMMETRIC_EULER_PARAMETER_KEYS - {"samples"},
    )
    return compute_symmetric_euler_bend(
        turn_angle_deg=values["turn_angle_deg"],
        minimum_radius_um=values["minimum_radius_um"],
        width_um=values["width_um"],
        samples=values.get("samples", 64),
    )

__all__ = [
    "ANGLE_EPS_RAD",
    "LENGTH_EPS",
    "MAX_EULER_SAMPLES",
    "MIN_EULER_SAMPLES",
    "Point2D",
    "compute_circular_bend",
    "compute_circular_route",
    "compute_euler_bend",
    "compute_symmetric_euler_bend",
    "evaluate_circular_route",
    "evaluate_symmetric_euler_bend",
]
