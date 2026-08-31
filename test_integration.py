import app as app_module
from app import app

def test_standard_log_submission():
    client = app.test_client()

    response = client.post(
        "/",
        data={
            "log_text": "ERROR Database connection failed",
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Detected Log Format:" in response.data
    assert b"Standard" in response.data
    assert b"Total matching lines:" in response.data
    assert b"1" in response.data

def test_json_log_submission():
    client = app.test_client()

    response = client.post(
        "/",
        data={
            "log_text": '{"level":"INFO","message":"User logged in"}',
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Detected Log Format:" in response.data
    assert b"JSON" in response.data
    assert b"Total matching lines:" in response.data
    assert b"1" in response.data

def test_apache_log_submission():
    client = app.test_client()

    response = client.post(
        "/",
        data={
            "log_text": '127.0.0.1 - - [26/Aug/2026:10:30:00] "GET /login HTTP/1.1" 404 123',
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Detected Log Format:" in response.data
    assert b"Apache" in response.data
    assert b"Total matching lines:" in response.data
    assert b"1" in response.data

def test_mixed_log_submission():
    client = app.test_client()

    log_text = "\n".join([
        "ERROR Database connection failed",
        '{"level":"INFO","message":"User logged in"}',
        '127.0.0.1 - - [26/Aug/2026:10:30:00] "Get /login HTTP/1.1" 404 123',
    ])

    response = client.post(
        "/",
        data={
            "log_text": log_text,
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Detected Log Format:" in response.data
    assert b"Mixed" in response.data
    assert b"Processed Lines:" in response.data
    assert b"3" in response.data

def test_ignored_line_diagnostics():
    client = app.test_client()

    log_text = "\n".join([
        "ERROR Database connection failed",
        "",
        '{"level":"INFO","message":',
        '127.0.0.1 - - [26/Aug/2026:10:30:00] "GET /login HTTP/1.1"',
        "this is not a recognized log line",
    ])

    response = client.post(
        "/",
        data={
            "log_text": log_text,
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Ignored Lines:" in response.data
    assert b"4" in response.data
    assert b"Blank Lines:" in response.data
    assert b"Invalid JSON Lines:" in response.data
    assert b"Invalid Apache Lines:" in response.data
    assert b"Unknown Lines:" in response.data

def test_processing_rate():
    client = app.test_client()

    log_text = "\n".join([
        "ERROR Database connection failed",
        '{"level":"INFO","message":"User logged in"}',
        "",                
        "this is not a recognized log line",
    ])

    response = client.post(
        "/",
        data={
            "log_text": log_text,
            "keyword": "",
            "levels": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Total Input Lines:" in response.data
    assert b"4" in response.data
    assert b"Processed Lines:" in response.data
    assert b"2" in response.data
    assert b"Processing Rate:" in response.data
    assert b"50.0%" in response.data

def test_history_keyword_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_search=login"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data

def test_history_level_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_level=ERROR"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data

def test_history_from_date_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_from=2026-08-22"
    )

    assert response.status_code == 200
    assert b"payment" in response.data
    assert b"login" not in response.data
    
def test_history_to_date_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_to=2026-08-22"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data
    
def test_history_combined_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-23 10:00:00",
        },        
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 4,
            "searched_at": "2026-08-24 10:00:00",
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?"
        "history_search=login&"
        "history_level=ERROR&"
        "history_from=2026-08-19&"
        "history_to=2026-08-21"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data
    assert b"2026-08-23 10:00:00" not in response.data

def test_history_no_filters(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/filter-history")

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" in response.data

def test_history_sort_newest(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "older",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "newer",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=newest"
    )

    assert response.status_code == 200
    page =  response.data.decode()
    assert page.find("newer") != -1
    assert page.find("older") != -1
    assert page.find("newer") < page.find("older")

def test_history_sort_oldest(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "older",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "newer",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=oldest"
    )

    assert response.status_code == 200
    page =  response.data.decode()
    assert page.find("newer") != -1
    assert page.find("older") != -1
    assert page.find("older") < page.find("newer")

def test_history_sort_keyword_asc(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "zebra",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "apple",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=keyword_asc"
    )

    assert response.status_code == 200
    page =  response.data.decode()
    assert page.find("apple") != -1
    assert page.find("zebra") != -1
    assert page.find("apple") < page.find("zebra")

def test_history_sort_keyword_desc(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "apple",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "zebra",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=keyword_desc"
    )

    assert response.status_code == 200
    page =  response.data.decode()
    assert page.find("zebra") != -1
    assert page.find("apple") != -1    
    assert page.find("zebra") < page.find("apple")

def test_history_pagination_page_1(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": f"item{i}",
            "levels": "INFO",
            "matches": i,
            "searched_at": f"2026-08-{i:02d} 10:00:00",
        }
        for i in range(1, 13)        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=oldest&page=1"
    )

    assert response.status_code == 200

    page =  response.data.decode()
    assert "<td>item2</td>" in page
    assert "<td>item10</td>" in page
    assert "<td>item11</td>" not in page
    assert "<td>item12</td>" not in page
    
def test_history_pagination_page_2(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": f"item{i}",
            "levels": "INFO",
            "matches": i,
            "searched_at": f"2026-08-{i:02d} 10:00:00",
        }
        for i in range(1, 13)        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=oldest&page=2"
    )

    assert response.status_code == 200

    page =  response.data.decode()
    assert "<td>item11</td>" in page
    assert "<td>item12</td>" in page
    assert "<td>item10</td>" not in page
    
def test_history_pagination_out_of_range(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": f"item{i}",
            "levels": "INFO",
            "matches": i,
            "searched_at": f"2026-08-{i:02d} 10:00:00",
        }
        for i in range(1, 13)        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_sort=oldest&page=99"
    )

    assert response.status_code == 200

    page =  response.data.decode()   

    assert "<td>item11</td>" not in page
    assert "<td>item12</td>" not in page




















    
