from __future__ import annotations

import argparse
import math
from pathlib import Path


ANGLE_EPS_RAD = 1e-9
LENGTH_EPS = 1e-12


def compute_circular_bend(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    radius: float,
) -> dict[str, object]:
    """Reference implementation for one tangent circular fillet.

    The emitted Java uses the same construction.  The turn angle is the signed
    change from ``a -> b`` to ``b -> c``; each tangent point is set back from
    ``b`` by ``radius * tan(abs(turn) / 2)``.
    """
    coordinates = (*a, *b, *c, radius)
    if not all(math.isfinite(value) for value in coordinates):
        raise ValueError("bend coordinates and radius must be finite")
    if radius <= 0.0:
        raise ValueError("bend radius must be positive")

    incoming = (b[0] - a[0], b[1] - a[1])
    outgoing = (c[0] - b[0], c[1] - b[1])
    incoming_length = math.hypot(*incoming)
    outgoing_length = math.hypot(*outgoing)
    if incoming_length <= LENGTH_EPS or outgoing_length <= LENGTH_EPS:
        raise ValueError("corner has a zero-length incoming or outgoing segment")

    din = (incoming[0] / incoming_length, incoming[1] / incoming_length)
    dout = (outgoing[0] / outgoing_length, outgoing[1] / outgoing_length)
    cross = din[0] * dout[1] - din[1] * dout[0]
    dot = max(-1.0, min(1.0, din[0] * dout[0] + din[1] * dout[1]))
    turn = math.atan2(cross, dot)
    abs_turn = abs(turn)
    if abs_turn <= ANGLE_EPS_RAD:
        raise ValueError("turn angle is zero or too close to 0 radians")
    if math.pi - abs_turn <= ANGLE_EPS_RAD:
        raise ValueError("turn angle is too close to 180 degrees")

    cutback = radius * math.tan(0.5 * abs_turn)
    fit_tolerance = LENGTH_EPS * max(1.0, incoming_length, outgoing_length, cutback)
    if not math.isfinite(cutback) or cutback > incoming_length + fit_tolerance or cutback > outgoing_length + fit_tolerance:
        raise ValueError(
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
        "radius": radius,
        "cutback": cutback,
        "turn": turn,
        "a0": a0,
        "a1": a1,
    }


HELPER = r'''// Analytic 2D circular-bend helper skeleton for COMSOL Java API.
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
    if (!Double.isFinite(lin) || !Double.isFinite(lout) || lin <= BEND_LENGTH_EPS || lout <= BEND_LENGTH_EPS) {
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
      throw new IllegalStateException("corner " + i + " tangent points do not lie on the requested-radius circle");
    }
    double a0 = Math.atan2(t1.y - center.y, t1.x - center.x);
    double a1 = Math.atan2(t2.y - center.y, t2.x - center.x);
    if (turn > 0.0 && a1 < a0) a1 += 2.0 * Math.PI;
    if (turn < 0.0 && a1 > a0) a1 -= 2.0 * Math.PI;
    bends.add(new BendSpec(t1, t2, center, radius, a0, a1));
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit a COMSOL Java helper skeleton for analytic annular-sector bends.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(HELPER, encoding="utf-8")
        print(f"WROTE {args.output}")
    else:
        print(HELPER)


if __name__ == "__main__":
    main()
