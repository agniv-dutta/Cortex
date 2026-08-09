from app.services.jsonutil import parse_json_object


def test_parse_clean_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_code_fence():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_stray_prose():
    text = "Here you go:\n{\"a\": 1}\nThanks!"
    assert parse_json_object(text) == {"a": 1}
