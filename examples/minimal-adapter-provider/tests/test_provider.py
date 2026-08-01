from __future__ import annotations

import unittest

from photonic_example_adapter import provide_adapters
from photonic_workflow.adapters import validate_adapter_provider_contract


class ProviderContractTests(unittest.TestCase):
    def test_provider_contract(self) -> None:
        registrations = validate_adapter_provider_contract(
            provide_adapters,
            provider_name="reviewed-example",
        )
        self.assertEqual(
            [item.descriptor.adapter for item in registrations],
            ["reviewed-example"],
        )


if __name__ == "__main__":
    unittest.main()
