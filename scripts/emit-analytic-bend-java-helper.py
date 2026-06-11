from __future__ import annotations

import argparse
from pathlib import Path


HELPER = r'''// Analytic 2D circular-bend helper skeleton for COMSOL Java API.
// Paste into a model class that already imports com.comsol.model.* and uses a 2D GeomSequence.
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
static P unit(P v) { double n = norm(v); return new P(v.x / n, v.y / n); }
static P leftNormal(P v) { return new P(-v.y, v.x); }

static java.util.List<BendSpec> bendSpecs(java.util.List<P> vertices, double radius) {
  java.util.ArrayList<BendSpec> bends = new java.util.ArrayList<BendSpec>();
  for (int i = 1; i < vertices.size() - 1; i++) {
    P a = vertices.get(i - 1), b = vertices.get(i), c = vertices.get(i + 1);
    P din = unit(b.sub(a));
    P dout = unit(c.sub(b));
    double lin = norm(b.sub(a));
    double lout = norm(c.sub(b));
    double cross = din.x * dout.y - din.y * dout.x;
    double dot = din.x * dout.x + din.y * dout.y;
    if (Math.abs(cross) < 1e-10 || Math.abs(dot + 1.0) < 1e-10) continue;
    double r = Math.min(radius, 0.45 * Math.min(lin, lout));
    if (r < 1e-6) continue;
    P t1 = b.sub(din.mul(r));
    P t2 = b.add(dout.mul(r));
    P n = leftNormal(din);
    if (cross < 0) n = n.mul(-1.0);
    P center = t1.add(n.mul(r));
    double a0 = Math.atan2(t1.y - center.y, t1.x - center.x);
    double a1 = Math.atan2(t2.y - center.y, t2.x - center.x);
    if (cross > 0 && a1 < a0) a1 += 2.0 * Math.PI;
    if (cross < 0 && a1 > a0) a1 -= 2.0 * Math.PI;
    bends.add(new BendSpec(t1, t2, center, r, a0, a1));
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
