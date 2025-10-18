from sqlify.db import find_url_match, Credential


def test_find_url_match():
    data = {c.url: c for c in [
        Credential("a", "http://example.com", "type", "value"),
        Credential("b", "http://example.com/long/path", "type", "value"),
        Credential("c", "http://example.com/path", "type", "value"),
        Credential("d", "http://example.com/path/*/sub", "type", "value"),
        Credential("e", "http://example.com/other/*/sub/*/more", "type", "value"),
    ]}

    assert find_url_match(data, "http://example.com") == data["http://example.com"]
    assert find_url_match(data, "http://example.com/long/path") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/long/path/more") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/long/path/more/more/more/more/more/more/more") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/path") == data["http://example.com/path"]
    assert find_url_match(data, "http://example.com/path/more") == data["http://example.com/path"]
    assert find_url_match(data, "http://example.com/path/hello/sub") == data["http://example.com/path/*/sub"]
    assert find_url_match(data, "http://example.com/path/hello/sub/sub") == data["http://example.com/path/*/sub"]
    assert find_url_match(data, "http://example.com/other/hello/sub/world/more") == data["http://example.com/other/*/sub/*/more"]