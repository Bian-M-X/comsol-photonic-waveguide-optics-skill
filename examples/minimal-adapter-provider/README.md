# Minimal descriptor provider

This package demonstrates the stable third-party boundary for adapter SPI
`1.0`. It publishes metadata only. It does not expose a runtime factory,
import a backend SDK, execute a solver, or claim backend/physics validity.

Provider versions are literals reviewed by the provider author. Do not derive
them from the host's current constants: a host upgrade must fail closed until
the provider is retested.

After installing `photonic-workflow` and this example in an isolated
environment, run:

```powershell
python -m unittest discover -s tests -v
```

An application may then place `reviewed-example` in
`adapter_entrypoint_allowlist` and explicitly run
`photonic doctor --load-configured-adapters`. That action authorizes importing
the provider's Python module for diagnosis; it is not solver-execution
authorization and is not a Python sandbox.
