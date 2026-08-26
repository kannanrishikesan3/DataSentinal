"""Phase 4 tests: every parser extracts real content, and a malformed file
never raises out of `safe_extract` (it must never abort a scan)."""

from datasentinel_agent.parsers.registry import get_parser, safe_extract
from datasentinel_agent.parsers.csv_parser import CSVParser
from datasentinel_agent.parsers.json_parser import JSONParser
from datasentinel_agent.parsers.text_parser import TextParser
from datasentinel_agent.parsers.xml_parser import XMLParser


def test_get_parser_dispatches_by_extension(tmp_path):
    assert isinstance(get_parser(tmp_path / "a.txt"), TextParser)
    assert isinstance(get_parser(tmp_path / "a.csv"), CSVParser)
    assert isinstance(get_parser(tmp_path / "a.json"), JSONParser)
    assert isinstance(get_parser(tmp_path / "a.xml"), XMLParser)
    assert get_parser(tmp_path / "a.exe") is None


def test_text_parser_line_numbers(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Employee: Jane Synthetic\nEmail: jane.synthetic@example.com\n")
    units, error = safe_extract(f)
    assert error is None
    assert [u.line_number for u in units] == [1, 2]
    assert "jane.synthetic@example.com" in units[1].text


def test_csv_parser_rows(tmp_path):
    f = tmp_path / "records.csv"
    f.write_text("name,email\nJohn Synthetic,john.synthetic@example.com\n")
    units, error = safe_extract(f)
    assert error is None
    assert any("john.synthetic@example.com" in u.text for u in units)


def test_json_parser_flattens_nested_structure(tmp_path):
    f = tmp_path / "data.json"
    f.write_text('{"user": {"name": "Synthetic User", "contact": {"email": "u@example.com"}}}')
    units, error = safe_extract(f)
    assert error is None
    joined = " ".join(u.text for u in units)
    assert "user.name" in joined
    assert "u@example.com" in joined


def test_xml_parser_extracts_text_and_attributes(tmp_path):
    f = tmp_path / "record.xml"
    f.write_text('<record id="42"><email>synthetic@example.com</email></record>')
    units, error = safe_extract(f)
    assert error is None
    joined = " ".join(u.text for u in units)
    assert "synthetic@example.com" in joined
    assert "id: 42" in joined


def test_malformed_json_never_raises(tmp_path):
    f = tmp_path / "broken.json"
    f.write_text("{not valid json!!")
    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_malformed_xml_never_raises(tmp_path):
    f = tmp_path / "broken.xml"
    f.write_text("<unclosed><tag>")
    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_xml_billion_laughs_is_rejected_not_expanded(tmp_path):
    """A classic entity-expansion bomb must fail safely, not consume memory."""
    bomb = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<root>&lol2;</root>"""
    f = tmp_path / "bomb.xml"
    f.write_text(bomb)
    units, error = safe_extract(f)
    # defusedxml must refuse this outright rather than expand it.
    assert error is not None


def test_empty_file_produces_no_units_and_no_error(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    units, error = safe_extract(f)
    assert units == []
    assert error is None


def test_unicode_filename_and_content(tmp_path):
    f = tmp_path / "résumé_日本語.txt"
    f.write_text("candidat: François Müller\n")
    units, error = safe_extract(f)
    assert error is None
    assert "François Müller" in units[0].text
