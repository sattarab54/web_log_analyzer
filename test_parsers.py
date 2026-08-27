from app import (
    detect_log_format,
    parse_json_log_line,
    parse_apache_log_line
)

def test_detect_standard_format():
    line = "ERROR Database connection failed"
    assert detect_log_format(line) == "standard"

def test_detect_json_format():
    line = '{"level":"INFO", "message":"User logged in"}'
    assert detect_log_format(line) == "json"

def test_detect_apache_format():
    line = '127.0.0.1 - - [26/Aug/2026:10:30:00] "Get / login HTTP/1.1" 404 123'
    assert detect_log_format(line) == "apache"

def test_detect_unknown_format():
    line = "This is just random text"
    assert detect_log_format(line) == "unknown"

def test_parse_valid_json_line():
    line = '{"level":"INFO", "message":"User logged in"}'
    assert parse_json_log_line(line) == "INFO User logged in"

def test_parse_invalid_json_line():
    line = '{"level":"INFO", "message":'
    assert parse_json_log_line(line) == ""

def test_parse_valid_apache_line():
    line = '127.0.0.1 - - [26/Aug/2026:10:30:00] "GET /login HTTP/1.1" 404 123'
    assert parse_apache_log_line(line) == "WARNING GET /login HTTP/1.1 404"

def test_parse_invalid_apache_line():
    line = '127.0.0.1 - - [26/Aug/2026:10:30:00] "GET /login HTTP/1.1"'
    assert parse_apache_log_line(line) == ""

def test_detect_empty_format():
    line = ""
    assert detect_log_format(line) == "empty"

def test_parse_json_missing_message():
    line = '{"level":"ERROR"}'
    assert parse_json_log_line(line) == ""
    

    
    
    

