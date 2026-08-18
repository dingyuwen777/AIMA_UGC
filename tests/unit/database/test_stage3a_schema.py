from aima_ugc.database_schema import metadata


def test_stage3a_tables_have_explicit_write_owners() -> None:
    expected = {
        "artifacts": "operations",
        "audit_events": "system",
        "system_settings": "system",
    }
    actual = {name: metadata.tables[name].info["owner"] for name in expected}
    assert actual == expected
