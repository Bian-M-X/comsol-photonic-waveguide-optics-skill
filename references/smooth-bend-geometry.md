# Smooth Bend Geometry Notes

Use this reference when a task involves replacing polygonal bend approximations with truly smooth waveguide bends, auditing bend loss, or scanning bend radius while preserving an interferometer path-length difference.

## Preferred 2D COMSOL Construction

For a routed 2D effective-index waveguide with circular bends:

1. Represent the centerline as vertices.
2. For each non-collinear corner, compute two tangent points at distance `R` from the vertex along the incoming and outgoing segments.
3. Replace the corner by an analytic circular arc with center, start angle, and end angle.
4. Build straight core sections as rectangles between tangent points.
5. Build each bend core as an analytic annular sector:
   - create an outer `Circle` sector with radius `R + w/2`;
   - create an inner `Circle` sector with radius `R - w/2`;
   - create a `Difference` with `input = outer`, `input2 = inner`;
   - set `intbnd = off` where internal boundaries are not physically meaningful.
6. Union all straight and bend pieces into one routed waveguide object and contribute it to the cumulative core selection.

This route avoids representing the physical bend edge as many short straight segments. It also makes the centerline length analytic:

```text
L = sum(straight tangent-to-tangent lengths) + sum(abs(delta_angle) * R)
```

For MZI/aMZI/LT-aMZI, recompute detour depth or arm geometry after changing the bend model so that `DeltaL = L2 - L1` remains the target value.

## COMSOL Java API Primitives

Useful documented primitives:

- `Circle` in 2D can create solid disks and circular sectors; `angle` is the sector angle and `rot` is the rotation angle.
- `Difference` subtracts `input2` objects from `input` objects.
- `Fillet` can round selected vertices in 2D, but it depends on reliable vertex selections and may skip or fail if a fillet intersects an edge.
- `ParametricCurve` creates a curve, not a waveguide domain; it is useful for references and diagnostics, but a physical core still needs a domain construction.

## Minimal Java Pattern

```java
g.create(outer, "Circle");
g.feature(outer).set("type", "solid");
g.feature(outer).set("r", radius + 0.5 * width);
g.feature(outer).set("pos", new double[]{cx, cy});
g.feature(outer).set("angle", angleDeg);
g.feature(outer).set("rot", rotDeg);

g.create(inner, "Circle");
g.feature(inner).set("type", "solid");
g.feature(inner).set("r", radius - 0.5 * width);
g.feature(inner).set("pos", new double[]{cx, cy});
g.feature(inner).set("angle", angleDeg);
g.feature(inner).set("rot", rotDeg);

g.create(tag, "Difference");
g.feature(tag).selection("input").set(new String[]{outer});
g.feature(tag).selection("input2").set(new String[]{inner});
g.feature(tag).set("intbnd", "off");
```

See `scripts/emit-analytic-bend-java-helper.py` for a reusable helper skeleton that emits centerline, tangent-point, and annular-sector helper code.

## Validation Sequence

Run a staged comparison before treating the smooth model as the new baseline:

1. Single isolated bend: compare low-step polygon, high-step polygon, and analytic annular sector.
2. Full device single point: preserve the original optical targets such as `DeltaL`, `gap_dc`, `Lc`, and `R_bend`.
3. Full device wavelength sweep: compare `T21`, `S11`, `S11 + T21`, peak positions, approximate FSR, valleys, and weak/strong peak ratio.
4. Only after the smooth model is stable, scan `R_bend`.

Recent LT-aMZI Design4 lesson: analytic smooth bends are a better geometry baseline, but they do not automatically increase `T21`. A true smooth model may reduce geometry discretization error while revealing that the main loss/imbalance is instead from couplers, boundaries, mesh, or the 2D EIM approximation.

## Reporting Rules

- State whether the geometry is polygonal, high-sampling polygonal, analytic circular-arc, filleted, or parametric.
- Report centerline lengths, not only coordinate differences.
- For interferometers, explicitly report `L1`, `L2`, `DeltaL`, and the FSR formula used.
- Do not claim that more arc steps or smoother geometry necessarily means lower loss; verify it with the same port, mesh, boundary, and sweep settings.

## Sources

- COMSOL Java API geometry documentation: `Circle` supports sector angle and rotation properties; `Difference` supports `input` and `input2` Boolean selections.
- Local project evidence: LT-aMZI Design4 true-smooth conversion, single-point check, and 1518-1521 nm dense sweep from 2026-06-09.
