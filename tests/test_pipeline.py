"""Pipeline integration smoke tests."""

from pathlib import Path

from bitegraph.adapters.ubereats import UberEatsAdapter
from bitegraph.core.classify_rules import RuleBasedClassifier
from bitegraph.core.consume_infer import DefaultConsumptionInference
from bitegraph.core.map_templates import TemplateIngredientMapper
from bitegraph.core.pipeline import PipelineRunner


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bitegraph"
    / "adapters"
    / "ubereats"
    / "fixtures"
    / "simple_order.csv"
)


def test_pipeline_end_to_end() -> None:
    adapter = UberEatsAdapter()
    runner = PipelineRunner(
        adapters=[adapter],
        classifier=RuleBasedClassifier(),
        mapper=TemplateIngredientMapper(),
        inference_engine=DefaultConsumptionInference(),
    )
    results = runner.run_pipeline(FIXTURE.read_bytes(), {"source": "uber_eats"})
    assert results
    assert results[0].interpretation is not None
    assert results[0].classification is not None
    assert results[0].mapping is not None
    assert results[0].consumption is not None
