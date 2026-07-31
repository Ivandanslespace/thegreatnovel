import pytest
import sys

# Run single test with verbose output
result = pytest.main([
    "tests/test_ranking_config.py::TestEdgeCases::test_single_dimension_weight",
    "-v",
    "--tb=long"
])

sys.exit(result)
