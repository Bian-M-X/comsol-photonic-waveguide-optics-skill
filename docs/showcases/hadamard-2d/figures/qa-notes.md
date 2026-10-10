The discrete-wavelength figure uses all seven declared baseline wavelength
runs at core/cladding mesh 0.02/0.08 µm, without interpolation, smoothing or
exclusion. The 1550 nm spectral point is mesh020. There is one deterministic
simulation per configuration, so no statistical error bars or confidence
intervals are defined.

The figure contract is a quantitative grid: panel a checks worst-case logical
throughput, b checks conditional state/process overlap, and c checks both-input
balance for one locked mask. Blue hollow markers and smaller orange markers
keep nearly coincident fidelity measures visible. Circles mark training
wavelengths; diamonds mark the two holdouts. Dashed horizontal lines are frozen
engineering gates, not fitted trends. Each panel and the complete figure were
visually inspected after the final export.

Final dimensions are 183 × 160 mm. The final Matplotlib axes geometry passes
the 1.5 pt panel alignment and repeated-gutter checks with no exemptions.
The exported PDF has a 7 pt minimum text size and no text below 5 pt. The final
rendered collision audit reports zero FAIL and zero WARN findings.

The source preflight reports three reviewed warnings:

- PNG is a web/showcase preview; the editable PDF and SVG are the authoritative
  vector outputs. No TIFF publication raster was requested or shipped.
- The PNG preview uses 300 dpi. It is not described as a 600 dpi submission
  raster.
- The source width heuristic misreads `183 / 25.4` as an inch literal. The
  rendered alignment manifest records width 518.740157 pt, exactly 183 mm, and
  height 453.543307 pt, exactly 160 mm.

The design and linear-field previews are byte-for-byte copies verified against
the preview provenance. Their original visualizer interpolated the physical
display window and peak-normalized it after cropping PML/backing regions. No
new cropping, color adjustment or resampling was applied in this showcase.
Neither visual preview substitutes for matrix, power or convergence checks.

QA JSON path fields were normalized to public relative paths after inspection;
numerical QA findings and geometric measurements were preserved.
