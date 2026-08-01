from __future__ import annotations

import inspect
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from photonic_workflow.adapters.comsol.recipes import (
    CIRCULAR_BEND_JAVA_HELPER,
    MAX_COMSOL_CIRCULAR_VERTICES,
    MAX_COMSOL_EULER_SAMPLES,
    MAX_COMSOL_FRAGMENT_BYTES,
    render_comsol_java_fragment,
    render_segmented_port_window_fragment,
    render_symmetric_euler_bend_fragment,
)
from photonic_workflow.exceptions import InvalidInputError, SecurityViolationError
from photonic_workflow.recipes.geometry import evaluate_symmetric_euler_bend


def _compile_java_fragment(content: str) -> subprocess.CompletedProcess[str]:
    source = """
class RecipeCompileSmoke {
  static class Selection { void set(Object value) {} }
  static class Feature {
    void set(String name, Object value) {}
    Selection selection(String name) { return new Selection(); }
  }
  static class G {
    void lengthUnit(String value) {}
    void create(String tag, String type) {}
    Feature feature(String tag) { return new Feature(); }
  }
  static void build(G g) {
""" + content + """
  }
}
"""
    with tempfile.TemporaryDirectory() as temporary:
        java_file = Path(temporary) / "RecipeCompileSmoke.java"
        java_file.write_text(source, encoding="utf-8")
        return subprocess.run(
            [shutil.which("javac") or "javac", "-encoding", "UTF-8", str(java_file)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )


class ComsolRecipeRendererTests(unittest.TestCase):
    def test_euler_renderer_is_fixed_numeric_and_nonexecuting(self) -> None:
        fragment = render_symmetric_euler_bend_fragment(
            90.0,
            5.0,
            0.5,
            64,
            instance_id="mzi-arm-1",
        )
        self.assertFalse(fragment.will_execute)
        self.assertEqual(fragment.instance_id, "mzi-arm-1")
        self.assertEqual(fragment.claim_level, "configuration-only-2d-eim")
        self.assertIn('_euler_bend", "InterpolationCurve")', fragment.content)
        self.assertIn('set("type", "solid")', fragment.content)
        self.assertIn('set("source", "table")', fragment.content)
        self.assertIn('set("rtol", 0.0)', fragment.content)
        self.assertIn("EulerBoundary", fragment.content)
        self.assertIn('g.lengthUnit("um")', fragment.content)
        self.assertNotIn("ModelUtil", fragment.content)
        self.assertNotIn(".run(", fragment.content)
        self.assertNotIn("D:\\", fragment.content)

    def test_port_renderer_uses_fixed_tags_and_scattering_difference(self) -> None:
        fragment = render_segmented_port_window_fragment(
            -30.0,
            30.0,
            -8.0,
            8.0,
            0.0,
            3.0,
            0.01,
            instance_id="port-window-main",
        )
        self.assertFalse(fragment.will_execute)
        self.assertEqual(fragment.content.count('"Rectangle"'), 3)
        self.assertIn('g.lengthUnit("um")', fragment.content)
        self.assertIn('_port_boundaries", "UnionSelection")', fragment.content)
        self.assertIn('_left_scattering", "DifferenceSelection")', fragment.content)
        self.assertIn('set("subtract", new String[]{"recipe_', fragment.content)
        self.assertIn('_port_boundaries"})', fragment.content)
        self.assertNotIn(".run(", fragment.content)

    def test_circular_renderer_emits_complete_straights_bends_and_union(self) -> None:
        straight = render_comsol_java_fragment(
            "circular-route",
            "1.0.0",
            {
                "vertices_um": [[0.0, 0.0], [10.0, 0.0]],
                "radius_um": 2.0,
                "width_um": 0.5,
            },
            instance_id="straight-1",
        )
        self.assertIn('g.lengthUnit("um")', straight.content)
        self.assertEqual(straight.content.count('"Polygon"'), 1)
        self.assertNotIn('"Circle"', straight.content)
        self.assertIn('_circular_route", "Union")', straight.content)

        routed = render_comsol_java_fragment(
            "circular-route",
            "1.0.0",
            {
                "vertices_um": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
                "radius_um": 2.0,
                "width_um": 0.5,
            },
            instance_id="route-1",
        )
        self.assertEqual(routed.content.count('"Polygon"'), 2)
        self.assertEqual(routed.content.count('"Circle"'), 2)
        self.assertEqual(routed.content.count('"Difference"'), 1)
        self.assertIn('_circular_straight_0"', routed.content)
        self.assertIn('_circular_bend_0"', routed.content)
        self.assertIn('_circular_straight_1"', routed.content)

    def test_unified_renderer_recomputes_and_confirms_output(self) -> None:
        parameters = {
            "turn_angle_deg": 90.0,
            "minimum_radius_um": 5.0,
            "width_um": 0.5,
            "samples": 64,
        }
        output = evaluate_symmetric_euler_bend(parameters)
        fragment = render_comsol_java_fragment(
            "symmetric-euler-bend",
            "1.0.0",
            parameters,
            output,
            instance_id="euler-a",
        )
        self.assertEqual(fragment.recipe_id, "symmetric-euler-bend")
        tampered = dict(output)
        tampered["cutback"] = 1.0
        with self.assertRaisesRegex(InvalidInputError, "does not match"):
            render_comsol_java_fragment(
                "symmetric-euler-bend",
                "1.0.0",
                parameters,
                tampered,
                instance_id="euler-a",
            )

    def test_instance_namespaces_are_safe_deterministic_and_disjoint(self) -> None:
        fragments = [
            render_symmetric_euler_bend_fragment(
                45.0,
                5.0,
                0.5,
                instance_id=instance_id,
            )
            for instance_id in ("upper-arm", "lower-arm")
        ]
        tags = [
            set(re.findall(r'g\.create\("([A-Za-z0-9_]+)"', fragment.content))
            for fragment in fragments
        ]
        self.assertTrue(tags[0])
        self.assertTrue(tags[1])
        self.assertTrue(tags[0].isdisjoint(tags[1]))
        prefix_match = re.search(
            r'g\.create\("(recipe_upper_arm_[0-9a-f]{10})_euler_bend"',
            fragments[0].content,
        )
        self.assertIsNotNone(prefix_match)
        prefix = prefix_match.group(1)
        self.assertNotIn(f"{prefix}_upper_arm_", fragments[0].content)
        self.assertTrue(all(tag.startswith(prefix) for tag in tags[0]))
        repeated = render_symmetric_euler_bend_fragment(
            45.0,
            5.0,
            0.5,
            instance_id="upper-arm",
        )
        self.assertEqual(fragments[0].content, repeated.content)
        with self.assertRaises(SecurityViolationError):
            render_symmetric_euler_bend_fragment(
                45.0,
                5.0,
                0.5,
                instance_id='bad"); g.run(); //',
            )

    def test_renderer_specific_size_limits_fail_closed(self) -> None:
        with self.assertRaisesRegex(InvalidInputError, str(MAX_COMSOL_EULER_SAMPLES)):
            render_symmetric_euler_bend_fragment(
                90.0,
                5.0,
                0.5,
                MAX_COMSOL_EULER_SAMPLES + 2,
                instance_id="too-many-euler-points",
            )

        vertices: list[list[float]] = [[0.0, 0.0]]
        x = 0.0
        y = 0.0
        for index in range(1, MAX_COMSOL_CIRCULAR_VERTICES + 1):
            if index % 2:
                x += 10.0
            else:
                y += 10.0
            vertices.append([x, y])
        with self.assertRaisesRegex(
            InvalidInputError,
            str(MAX_COMSOL_CIRCULAR_VERTICES),
        ):
            render_comsol_java_fragment(
                "circular-route",
                "1.0.0",
                {
                    "vertices_um": vertices,
                    "radius_um": 1.0,
                    "width_um": 0.5,
                },
                instance_id="too-many-route-points",
            )

    @unittest.skipUnless(shutil.which("javac"), "javac is unavailable")
    def test_maximum_supported_euler_fragment_compiles_as_java(self) -> None:
        fragment = render_symmetric_euler_bend_fragment(
            90.0,
            5.0,
            0.5,
            MAX_COMSOL_EULER_SAMPLES,
            instance_id="compile-limit",
        )
        completed = _compile_java_fragment(fragment.content)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    @unittest.skipUnless(shutil.which("javac"), "javac is unavailable")
    def test_maximum_supported_circular_fragment_compiles_as_java(self) -> None:
        vertices: list[list[float]] = [[0.0, 0.0]]
        x = 0.0
        y = 0.0
        for index in range(1, MAX_COMSOL_CIRCULAR_VERTICES):
            if index % 2:
                x += 10.0
            else:
                y += 10.0
            vertices.append([x, y])
        fragment = render_comsol_java_fragment(
            "circular-route",
            "1.0.0",
            {
                "vertices_um": vertices,
                "radius_um": 1.0,
                "width_um": 0.5,
            },
            instance_id="x" * 128,
        )
        self.assertLessEqual(len(fragment.content.encode("utf-8")), MAX_COMSOL_FRAGMENT_BYTES)
        completed = _compile_java_fragment(fragment.content)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_renderer_rejects_unknown_recipe_version_and_parameter_keys(self) -> None:
        parameters = {
            "turn_angle_deg": 90.0,
            "minimum_radius_um": 5.0,
            "width_um": 0.5,
        }
        with self.assertRaisesRegex(InvalidInputError, "unsupported COMSOL recipe id"):
            render_comsol_java_fragment(
                "arbitrary-java",
                "1.0.0",
                parameters,
                instance_id="safe",
            )
        with self.assertRaisesRegex(InvalidInputError, "unsupported COMSOL recipe version"):
            render_comsol_java_fragment(
                "symmetric-euler-bend",
                "2.0.0",
                parameters,
                instance_id="safe",
            )
        with self.assertRaisesRegex(InvalidInputError, "unknown symmetric-euler-bend"):
            render_comsol_java_fragment(
                "symmetric-euler-bend",
                "1.0.0",
                {**parameters, "tag": "caller-controlled"},
                instance_id="safe",
            )

    def test_public_renderers_accept_no_java_tag_or_expression_argument(self) -> None:
        for renderer in (
            render_comsol_java_fragment,
            render_segmented_port_window_fragment,
            render_symmetric_euler_bend_fragment,
        ):
            names = set(inspect.signature(renderer).parameters)
            self.assertFalse(names & {"java", "tag", "expression", "template"})

    def test_legacy_helper_constant_remains_available_from_one_implementation(self) -> None:
        self.assertIn("radius * Math.tan(0.5 * absTurn)", CIRCULAR_BEND_JAVA_HELPER)
        self.assertNotIn("Math.min(radius", CIRCULAR_BEND_JAVA_HELPER)
        self.assertIn(
            "tangent points do not lie on the requested-radius circle",
            CIRCULAR_BEND_JAVA_HELPER,
        )


if __name__ == "__main__":
    unittest.main()
