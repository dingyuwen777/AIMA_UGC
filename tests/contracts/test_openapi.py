from aima_ugc.entrypoints.api_main import create_app


def test_health_operation_id_is_stable() -> None:
    spec = create_app().openapi()

    assert spec["paths"]["/health/live"]["get"]["operationId"] == "healthLive"
