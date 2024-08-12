from sqletl_db.db import find_url_match, Credential


def test_find_url_match():
    data = {
        "a": Credential("a", "http://example.com", "type", "value"),
        "b": Credential("b", "http://example.com/long/path", "type", "value"),
        "c": Credential("c", "http://example.com/path", "type", "value"),
        "d": Credential("d", "http://example.com/path/*/sub", "type", "value"),
        "e": Credential("e", "http://example.com/other/*/sub/*/more", "type", "value"),
    }

    assert find_url_match(data, "http://example.com") == data["a"]
    assert find_url_match(data, "http://example.com/long/path") == data["b"]
    assert find_url_match(data, "http://example.com/long/path/more") == data["b"]
    assert find_url_match(data, "http://example.com/long/path/more/more/more/more/more/more/more") == data["b"]
    assert find_url_match(data, "http://example.com/path") == data["c"]
    assert find_url_match(data, "http://example.com/path/more") == data["c"]
    assert find_url_match(data, "http://example.com/path/hello/sub") == data["d"]
    assert find_url_match(data, "http://example.com/path/hello/sub/sub") == data["d"]
    assert find_url_match(data, "http://example.com/other/hello/sub/world/more") == data["e"]