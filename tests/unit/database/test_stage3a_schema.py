from aima_ugc.database_schema import metadata


def test_stage3a_tables_have_explicit_write_owners() -> None:
    expected = {
        "artifacts": "platform",
        "audit_events": "system",
        "system_settings": "system",
    }
    assert set(metadata.tables) == set(expected)
    actual = {name: table.info["owner"] for name, table in metadata.tables.items()}
    assert actual == expected
