import app as app_module
from app import app
from io import BytesIO
from openpyxl import load_workbook
from pypdf import PdfReader

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

def test_download_results_csv():
    client = app.test_client()

    response = client.get("/download-csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "analysis_results.csv" in response.headers["Content-Disposition"]

def test_download_history_csv():
    client = app.test_client()

    response = client.get("/download-history-csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    
def test_download_filtered_history_csv(monkeypatch):
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
        "/download-history-csv?history_search=login"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data
    
def test_download_filtered_history_csv_level_filter(monkeypatch):
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
        "/download-history-csv?history_level=ERROR"
    )

    assert response.status_code == 200
    assert b"login" in response.data
    assert b"payment" not in response.data

def test_download_filtered_history_csv_date_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "old",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-10 10:00:00",
        },
        {
            "keyword": "middle",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-20 10:00:00",
        },
        {
            "keyword": "new",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-30 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-history-csv?"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200
    assert b"middle" in response.data
    assert b"old" not in response.data
    assert b"new" not in response.data

def test_download_filtered_history_csv_combined_filters(monkeypatch):
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
            "searched_at": "2026-08-20 11:00:00",
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 4,
            "searched_at": "2026-08-20 12:00:00",
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-30 10:00:00",
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-history-csv?"
        "history_search=login&"
        "history_level=ERROR&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200
    assert b"login,Unknown,ERROR,3" in response.data
    assert b"login,WARNING,2" not in response.data
    assert b"payment,ERROR,4" not in response.data
    assert b"login,ERROR,5" not in response.data

def test_download_history_excel():
    client = app.test_client()

    response = client.get("/download-history-excel")

    assert response.status_code == 200
    assert response.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "history.xlsx" in response.headers["Content-Disposition"]

def test_download_filtered_history_excel():
    client = app.test_client()

    response = client.get("/download-filtered-history-excel")

    assert response.status_code == 200
    assert response.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
def test_filtered_history_excel_keyword_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=login"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value
        for row in range(2, sheet.max_row + 1)
    ]

    assert "login" in keywords
    assert "payment" not in keywords

def test_filtered_history_excel_level_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=ERROR"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value
        for row in range(2, sheet.max_row + 1)
    ]

    assert "ERROR" in levels
    assert "WARNING" not in levels

def test_filtered_history_excel_date_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "old",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-10 10:00:00",
            "results": [],
        },
        {
            "keyword": "middle",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "new",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        }
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value
        for row in range(2, sheet.max_row + 1)
    ]

    assert "middle" in keywords
    assert "oldt" not in keywords
    assert "new" not in keywords

def test_filtered_history_excel_combined_filters(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-20 11:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 4,
            "searched_at": "2026-08-20 12:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=login&"
        "history_level=ERROR&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=2).value,
            sheet.cell(row=row, column=3).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert ("login", "ERROR", 3) in rows
    assert ("login", "WARNING", 2) not in rows
    assert ("payment", "ERROR", 4) not  in rows
    assert ("login", "ERROR", 5) not in rows
    
def test_filtered_history_excel_sort_newest(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "older",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "newer",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 11:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=newest"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert keywords == ["newer", "older"]
    
def test_filtered_history_excel_sort_oldest(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "older",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "newer",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-25 11:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=oldest"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert keywords == ["older", "newer"]

def test_filtered_history_excel_sort_keyword_az(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "error",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=keyword_asc"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert keywords == ["error", "login", "payment"]

def test_filtered_history_excel_sort_keyword_desc(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "apple",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "zebra",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=keyword_desc"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert keywords == ["zebra", "login", "apple"]

def test_filtered_history_excel_sort_levels_high(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "info-item",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "critical-item",
            "levels": "CRITICAL",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "warning-item",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=levels_high"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert levels == ["CRITICAL", "WARNING", "INFO"]

def test_filtered_history_excel_sort_levels_low(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "critical-item",
            "levels": "CRITICAL",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "info-item",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
        {
            "keyword": "trace-item",
            "levels": "TRACE",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=levels_low"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert levels == ["TRACE", "INFO", "CRITICAL"]
    
def test_filtered_history_excel_sort_matches_high(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "low",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "high",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
        {
            "keyword": "middle",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=matches_high"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    matches = [
        sheet.cell(row=row, column=3).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert matches == [5, 3, 1]

def test_filtered_history_excel_sort_matches_low(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "high",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "low",
            "levels": "INFO",
            "matches": 1,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
        {
            "keyword": "middle",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_sort=matches_low"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    matches = [
        sheet.cell(row=row, column=3).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert matches == [1, 3, 5]

def test_filtered_history_excel_empty_result(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=not-found"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    assert sheet.max_row == 1

    headers = [
        sheet.cell(row=1, column=column).value            
        for column in range(1, 5)
    ]

    assert headers == [
        "Keyword",
        "Levels",
        "Matches",
        "Searched At",
    ]

def test_filtered_history_excel_keyword_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=LOGIN"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert "login" in keywords
    assert "payment" not in keywords

def test_filtered_history_excel_partial_keyword_search(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=log"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert "login" in keywords
    assert "payment" not in keywords
    
def test_filtered_history_excel_middle_keyword_search(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=gin"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert "login" in keywords
    assert "payment" not in keywords

def test_filtered_history_excel_partial_keyword_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_search=GIN"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert "login" in keywords
    assert "payment" not in keywords

def test_filtered_history_excel_level_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=error"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value            
        for row in range(2, sheet.max_row + 1)
    ]

    assert "ERROR" in levels
    assert "WARNING" not in levels

def test_filtered_history_excel_keyword_and_level_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=2).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert ("login", "ERROR") in rows
    assert ("payment", "ERROR") not in rows

def test_filtered_history_excel_level_case_insensitive_with_date_range(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 4,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
        {
            "keyword": "warning-item",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },                
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=2).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert ("login", "ERROR") in rows    
    assert ("payment", "ERROR") not in rows
    assert ("warning-item", "WARNING") not in rows

def test_filtered_history_excel_combined_filters_and_sort(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-old",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-new",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)
    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=matches_high"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=3).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert  rows == [
        ("login-new", 5),
        ("login-old", 2),
    ]

def test_filtered_history_excel_combined_filters_and_matches_low(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-old",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-new",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=matches_low"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=3).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert  rows == [
        ("login-old", 2),
        ("login-new", 5),        
    ]

def test_filtered_history_excel_combined_filters_and_newest_sort(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-old",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-new",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=newest"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=4).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert  rows == [
        ("login-new", "2026-08-24 10:00:00"),
        ("login-old", "2026-08-18 10:00:00"),                
    ]

def test_filtered_history_excel_combined_filters_and_oldest_sort(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-old",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-new",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=oldest"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    rows = [
        (
            sheet.cell(row=row, column=1).value,
            sheet.cell(row=row, column=4).value,
        )
        for row in range(2, sheet.max_row + 1)
    ]

    assert  rows == [
        ("login-old", "2026-08-18 10:00:00"),
        ("login-new", "2026-08-24 10:00:00"),
    ]
                        
def test_filtered_history_excel_combined_filters_and_keyword_asc(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-zebra",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-apple",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=keyword_asc"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value                    
        for row in range(2, sheet.max_row + 1)
    ]

    assert  keywords == [
        "login-apple",
        "login-zebra",
    ]

def test_filtered_history_excel_combined_filters_and_keyword_desc(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-zebra",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-apple",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=keyword_desc"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    keywords = [
        sheet.cell(row=row, column=1).value                    
        for row in range(2, sheet.max_row + 1)
    ]

    assert  keywords == [
        "login-zebra",
        "login-apple",        
    ]

def test_filtered_history_excel_combined_filters_and_levels_high(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-info",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-critical",
            "levels": "CRITICAL",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"        
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=levels_high"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value                    
        for row in range(2, sheet.max_row + 1)
    ]

    assert levels == [
        "CRITICAL",
        "WARNING",
        "INFO",
    ]

def test_filtered_history_excel_combined_filters_and_levels_low(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login-info",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-18 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-critical",
            "levels": "CRITICAL",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-warning",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 6,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login-outside",
            "levels": "ERROR",
            "matches": 8,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"        
        "history_from=2026-08-15&"
        "history_to=2026-08-25&"
        "history_sort=levels_low"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    levels = [
        sheet.cell(row=row, column=2).value                    
        for row in range(2, sheet.max_row + 1)
    ]

    assert levels == [
        "INFO",
        "WARNING",        
        "CRITICAL",                
    ]

def test_filtered_history_excel_summary_uses_filtered_rows(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 7,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=login&"        
        "history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    summary_sheet = workbook["Summary"]

    summary_values = {
        summary_sheet.cell(row=row, column=1).value:
        summary_sheet.cell(row=row, column=2).value
        for row in range(1, summary_sheet.max_row + 1)
    }

    assert summary_values["Total searches"] == 2
    assert summary_values["Total matches found"] == 8 
        
def test_filtered_history_excel_summary_successful_searches(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 0,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=login&"        
        "history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    summary_sheet = workbook["Summary"]

    summary_values = {
        summary_sheet.cell(row=row, column=1).value:
        summary_sheet.cell(row=row, column=2).value
        for row in range(1, summary_sheet.max_row + 1)
    }

    assert summary_values["Total searches"] == 2
    assert summary_values["Successful searches"] == 1 

def test_filtered_history_excel_summary_most_searched_keyword(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 6,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    summary_sheet = workbook["Summary"]

    summary_values = {
        summary_sheet.cell(row=row, column=1).value:
        summary_sheet.cell(row=row, column=2).value
        for row in range(1, summary_sheet.max_row + 1)
    }

    assert summary_values["Most searched keyword"] == "login"
    
def test_filtered_history_excel_summary_most_common_level(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 6,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_search=login"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    summary_sheet = workbook["Summary"]

    summary_values = {
        summary_sheet.cell(row=row, column=1).value:
        summary_sheet.cell(row=row, column=2).value
        for row in range(1, summary_sheet.max_row + 1)
    }

    assert summary_values["Most common log level"] == "ERROR"

def test_filtered_history_excel_summary_empty_result(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },        
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_search=not-found"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    summary_sheet = workbook["Summary"]

    summary_values = {
        summary_sheet.cell(row=row, column=1).value:
        summary_sheet.cell(row=row, column=2).value
        for row in range(1, summary_sheet.max_row + 1)
    }

    assert summary_values["Total searches"] == 0
    assert summary_values["Successful searches"] == 0
    assert summary_values["Total matches found"] == 0
    assert summary_values["Most searched keyword"] == "N/A"
    assert summary_values["Most common log level"] == "N/A"

def test_filtered_history_excel_charts_use_filtered_rows(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_search=login"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 1
    
def test_filtered_history_excel_charts_all_levels(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "CRITICAL",
            "matches": 1,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 3,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "INFO",
            "matches": 4,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "DEBUG",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "TRACE",
            "matches": 6,
            "searched_at": "2026-08-25 10:00:00",
            "results": [],
        },    
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 7,
            "searched_at": "2026-08-26 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_search=login"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 1
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    assert chart_values["DEBUG"] == 1
    assert chart_values["TRACE"] == 1

def test_filtered_history_excel_charts_empty_result(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },        
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_search=not-found"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 0
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_level_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },        
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "logout",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 0
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_keyword_and_level(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 0
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_keyword_level_and_date(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 4,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
        {
            "keyword": "login",
            "levels": "WARNING",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "ERROR",
            "matches": 5,
            "searched_at": "2026-08-22 10:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_search=LOGIN&"
        "history_level=error&"
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 0
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_date_range(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-10 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "log0ut",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "debug-item",
            "levels": "DEBUG",
            "matches": 4,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
                
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_from=2026-08-15&"
        "history_to=2026-08-25"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_from_date_only(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-10 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "log0ut",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "debug-item",
            "levels": "DEBUG",
            "matches": 4,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
                
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                
        "history_from=2026-08-20"        
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    assert chart_values["DEBUG"] == 1
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_to_date_only(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-10 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "log0ut",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "debug-item",
            "levels": "DEBUG",
            "matches": 4,
            "searched_at": "2026-08-30 10:00:00",
            "results": [],
        },
                
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                        
        "history_to=2026-08-24"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_to_date_inclusive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-23 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-24 10:00:00",
            "results": [],
        },
        {
            "keyword": "log0ut",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-25 10:00:00",
            "results": [],
        },                        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                        
        "history_to=2026-08-24"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    
    assert chart_values["ERROR"] == 1
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 0
    
def test_filtered_history_excel_charts_from_date_inclusive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-19 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "log0ut",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },                        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"                        
        "history_from=2026-08-20"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1

def test_filtered_history_excel_charts_single_day_range(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-19 10:00:00",
            "results": [],
        },
        {
            "keyword": "morning",
            "levels": "WARNING",
            "matches": 5,
            "searched_at": "2026-08-20 09:00:00",
            "results": [],
        },
        {
            "keyword": "evening",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-20 18:00:00",
            "results": [],
        },
        {
            "keyword": "after",
            "levels": "DEBUG",
            "matches": 4,
            "searched_at": "2026-08-21 10:00:00",
            "results": [],
        },
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?"
        "history_from=2026-08-20&"
        "history_to=2026-08-20"
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    assert chart_values["DEBUG"] == 0

def test_filtered_history_excel_charts_level_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-20 11:00:00",
            "results": [],
        },
        {
            "keyword": "server",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 09:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=ERROR"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    assert chart_values["ERROR"] == 2
    assert chart_values["WARNING"] == 0
    
def test_filtered_history_excel_charts_level_filter_case_insensitive(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-20 11:00:00",
            "results": [],
        },
        {
            "keyword": "server",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 09:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=error"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    assert chart_values["ERROR"] == 2
    assert chart_values["WARNING"] == 0

def test_filtered_history_excel_charts_level_filter_no_matches(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "WARNING",
            "matches": 4,
            "searched_at": "2026-08-20 11:00:00",
            "results": [],
        },
        {
            "keyword": "server",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-21 09:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=CRITICAL"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0    
    assert chart_values["WARNING"] == 0
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_multiple_levels_in_one_row(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR, WARNING",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },        
        {
            "keyword": "server",
            "levels": "INFO",
            "matches": 2,
            "searched_at": "2026-08-21 09:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel"               
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }
    
    assert chart_values["ERROR"] == 1    
    assert chart_values["WARNING"] == 1
    assert chart_values["INFO"] == 1
    
def test_filtered_history_excel_charts_multiple_levels_with_level_filter(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR, WARNING",
            "matches": 3,
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "server",
            "levels": "ERROR",
            "matches": 2,
            "searched_at": "2026-08-21 09:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "levels": "INFO",
            "matches": 4,
            "searched_at": "2026-08-22 11:00:00",
            "results": [],
        },        
    ]
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel?history_level=WARNING"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["WARNING"] == 1
    assert chart_values["ERROR"] == 0        
    assert chart_values["INFO"] == 0

def test_filtered_history_excel_charts_missing_levels(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 0            
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_filtered_history_excel_charts_empty_levels(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "",
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 0            
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0
    
def test_filtered_history_excel_charts_whitespace_levels(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "  ",
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-filtered-history-excel"                
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    charts_sheet = workbook["Charts"]

    chart_values = {
        charts_sheet.cell(row=row, column=1).value:
        charts_sheet.cell(row=row, column=2).value
        for row in range(2, charts_sheet.max_row + 1)
    }

    assert chart_values["CRITICAL"] == 0
    assert chart_values["ERROR"] == 0
    assert chart_values["WARNING"] == 0            
    assert chart_values["INFO"] == 0
    assert chart_values["DEBUG"] == 0
    assert chart_values["TRACE"] == 0

def test_history_stores_pasted_text_source(monkeypatch):
    client = app.test_client()

    test_history = []
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.post(
        "/",
        data={
            "log_text": "2026-08-20 10:00:00 ERROR Login failed",
            "keyword": "login",
            "levels": "ERROR",
        },
    )

    assert response.status_code == 200
    assert len(test_history) == 1
    assert test_history[0]["source"] == "Pasted text"

def test_history_stores_uploaded_file_source(monkeypatch):
    client = app.test_client()

    test_history = []
    monkeypatch.setattr(app_module, "history", test_history)

    response = client.post(
        "/",
        data={
            "log_file": (
                BytesIO(b"2026-08-20 10:00:00 ERROR Login failed"),
                "sample.log",
            ),
            "keyword": "login",
            "levels": "ERROR",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert len(test_history) == 1
    assert test_history[0]["source"] == "sample.log"

def test_filtered_history_table_displays_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",
            "source": "sample.log",
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/filter-history")

    assert response.status_code == 200
    assert b"sample.log" in response.data
        
def test_history_table_displays_unknown_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/filter-history")

    assert response.status_code == 200
    assert b"Unknown" in response.data

def test_download_filtered_history_csv_includes_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/download-history-csv")

    assert response.status_code == 200
    assert b"Keyword,Source,Levels,Matches,Searched At" in response.data
    assert b"login,sample.log,ERROR,3" in response.data

def test_download_history_excel_includes_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/download-history-excel")

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["History"]

    assert sheet.cell(row=1, column=6).value == "Source"
    assert sheet.cell(row=2, column=6).value == "sample.log"
    
def test_download_filtered_history_excel_includes_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/download-filtered-history-excel")

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    sheet = workbook["Filtered History"]

    assert sheet.cell(row=1, column=5).value == "Source"
    assert sheet.cell(row=2, column=5).value == "sample.log"

def test_export_history_pdf_with_history_details(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/export-history-pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")

def test_export_history_pdf_missing_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",            
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get("/export-history-pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")

def test_export_history_pdf_filtered_with_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "source": "apache.log",
            "levels": "WARNING",            
            "matches": 2,            
            "searched_at": "2026-08-21 11:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/export-history-pdf?"
        "history_search=login&"
        "history_level=ERROR"
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")

def test_filter_history_by_source(monkeypatch):
    client = app.test_client()

    test_history = [
        {
            "keyword": "login",
            "source": "sample.log",
            "levels": "ERROR",            
            "matches": 3,            
            "searched_at": "2026-08-20 10:00:00",
            "results": [],
        },
        {
            "keyword": "payment",
            "source": "apache.log",
            "levels": "WARNING",            
            "matches": 2,            
            "searched_at": "2026-08-21 11:00:00",
            "results": [],
        },
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history?history_source=sample.log"        
    )

    assert response.status_code == 200
    assert b"sample.log" in response.data
    assert b"apache.log" not in response.data
    
def test_filter_history_combined_filters(monkeypatch):
    client = app.test_client()

    base_entry = {        
        "source": "sample.log",
        "levels": "ERROR",            
        "matches": 3,            
        "searched_at": "2026-08-20 10:00:00",
        "results": [],
    }

    test_history = [
        {**base_entry, "keyword": "login_keep"},
        {
            **base_entry,
            "keyword": "login_other_source",
            "source": "apache.log",
        },
        {
            **base_entry,
            "keyword": "login_other_level",
            "levels": "WARNING",
        },
        {**base_entry, "keyword": "payment_other_keyword"},        
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/filter-history",
        query_string={
            "history_search": "login",
            "history_source": "sample.log",
            "history_level": "ERROR",
        },
    )

    assert response.status_code == 200
    assert b"login_keep" in response.data
    assert b"login_other_source" not in response.data
    assert b"login_other_level" not in response.data
    assert b"payment_other_keyword" not in response.data

def test_history_csv_filters_by_source(monkeypatch):
    client = app.test_client()

    base_entry = {                
        "levels": "ERROR",            
        "matches": 1,            
        "searched_at": "2026-09-16 10:00:00",
        "results": [],
    }

    test_history = [        
        {
            **base_entry,
            "keyword": "keep_source_marker",
            "source": "sample.log",
        },
        {
            **base_entry,
            "keyword": "exclude_source_marker",
            "source": "apache.log",
        },                
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/download-history-csv",
        query_string={"history_source": "SAMPLE.LOG"},                                            
    )

    assert response.status_code == 200
    assert b"keep_source_marker" in response.data
    assert b"exclude_source_marker" not in response.data
    
def test_history_excel_filters_by_source(monkeypatch):
    client = app.test_client()

    base_entry = {                
        "levels": "ERROR",            
        "matches": 1,            
        "searched_at": "2026-09-16 10:00:00",
        "results": [],
    }

    test_history = [        
        {
            **base_entry,
            "keyword": "keep_excel_marker",
            "source": "sample.log",
        },
        {
            **base_entry,
            "keyword": "exclude_excel_marker",
            "source": "apache.log",
        },                
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/export-history-xlsx",
        query_string={"history_source": "SAMPLE.LOG"},                                            
    )

    assert response.status_code == 200

    workbook = load_workbook(BytesIO(response.data))
    values = [
        cell.value
        for sheet in workbook.worksheets
        for row in sheet
        for cell in row
    ]
    workbook.close()
    
    assert "keep_excel_marker" in values
    assert "exclude_excel_marker" not in values

def test_history_pdf_filters_by_source(monkeypatch):
    client = app.test_client()

    base_entry = {                
        "levels": "ERROR",            
        "matches": 1,            
        "searched_at": "2026-09-16 10:00:00",
        "results": [],
    }

    test_history = [        
        {
            **base_entry,
            "keyword": "keep_pdf_marker",
            "source": "sample.log",
        },
        {
            **base_entry,
            "keyword": "exclude_pdf_marker",
            "source": "apache.log",
        },                
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    response = client.get(
        "/export-history-pdf",
        query_string={"history_source": "SAMPLE.LOG"},                                            
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"

    reader = PdfReader(BytesIO(response.data))
    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )
        
    assert "keep_pdf_marker" in text
    assert "exclude_pdf_marker" not in text

def test_history_pagination_preserves_source(monkeypatch):
    from html.parser import HTMLParser
    from urllib.parse import parse_qs, urlsplit

    class LinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                href = dict(attrs).get("href")
                if href:
                    self.links.append(href)

    test_history = [
        {
            "keyword": f"login_{i:02d}",
            "source": "sample.log",
            "levels": "ERROR",
            "matches": 1,
            "searched_at": "2026-09-19 10:00:00",
            "results": [],
        }
        for i in range(21)
    ]

    monkeypatch.setattr(app_module, "history", test_history)

    client = app.test_client()
    response = client.get(
        "/filter-history",
        query_string={
            "history_source": "sample.log",
            "history_sort": "newest",
            "page": 2,
        }
    )

    assert response.status_code == 200

    parser = LinkParser()
    parser.feed(response.get_data(as_text=True))

    pagination_links = []
    for href in parser.links:
        parts = urlsplit(href)
        query = parse_qs(parts.query)
        if parts.path == "/filter-history" and "page" in query:
            pagination_links.append((parts, query))

    assert len(pagination_links) == 4
    assert {
        query["page"][0] for _, query in pagination_links
    } == {"1", "3"}

    for parts, query in pagination_links:
        assert query["history_source"] == ["sample.log"]
        assert query["history_sort"] == ["newest"]
        assert parts.fragment == "history-sort"















































