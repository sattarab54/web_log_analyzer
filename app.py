
from flask import Flask, render_template, request, send_file, redirect
from utils import load_history, save_history
from markupsafe import Markup
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
import re
import csv
import json

app = Flask(__name__)

latest_results_text = ""
latest_results_rows = []

HISTORY_FILE = "history.json"
history = load_history()
latest_filtered_history = []

def parse_log_datetime(line):
    try:
        text = line[:19]
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None 

def highlight_keyword(line, keyword, case_sensitive=False):
    if not keyword:
        return line

    flags = 0 if case_sensitive else re.IGNORECASE

    pattern = re.compile(re.escape(keyword), flags)

    highlighted = pattern.sub(
        lambda match: f"<mark>{match.group(0)}</mark>",
        line
    )

    return Markup(highlighted)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        log_text = request.form.get("log_text", "")
        uploaded_file = request.files.get("log_file")
        source_name = "Pasted text"
        keyword = request.form.get("keyword", "")
        selected_levels = request.form.getlist("levels")
        case_sensitive = "case_sensitive" in request.form
        start_datetime_text = request.form.get("start_datetime", "")
        end_datetime_text = request.form.get("end_datetime", "")

        # 1. split lines
        if uploaded_file and uploaded_file.filename:
            source_name = uploaded_file.filename
            log_text = uploaded_file.read().decode("utf-8")

        if not log_text.strip():
            return render_template(
                "index.html",
                error_message="Please paste log text or upload a log file.",
            )

        lines = log_text.splitlines()
        

        start_datetime = None
        end_datetime = None

        if start_datetime_text:
            try:
                start_datetime = datetime.strptime(start_datetime_text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return render_template(
                    "index.html",
                    error_message="Start datetime must be in format YYYY-MM-DD HH:MM:SS.",
                )

        if end_datetime_text:
            try:
                end_datetime = datetime.strptime(end_datetime_text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return render_template(
                    "index.html",
                    error_message="End datetime must be in format YYYY-MM-DD HH:MM:SS.",
                )
            
        if start_datetime or end_datetime:
            filtered_lines = []

            for line in lines:
                line_datetime = parse_log_datetime(line)

                if line_datetime is None:
                    continue

                if start_datetime and line_datetime < start_datetime:
                    continue

                if end_datetime and line_datetime > end_datetime:
                    continue

                filtered_lines.append(line)

            lines = filtered_lines

        # 2. selected level filter
        if selected_levels:
            lines = [
                line for line in lines
                if any(level in line for level in selected_levels)
            ]

        # 3. keyword filter
        if keyword:
            if case_sensitive:                
                results = [
                    line for line in lines
                    if keyword in line
                ]
            else:
                results = [
                    line for line in lines
                    if keyword.lower() in line.lower()
                ]
        else:
            results = lines

        if keyword:
            results = [
                highlight_keyword(line, keyword, case_sensitive)
                for line in results
            ]
                              
        # 4. summary from final results
        summary = {
            "CRITICAL": 0,
            "ERROR": 0,
            "WARNING": 0,
            "INFO": 0,
            "DEBUG": 0,
            "TRACE": 0,
        }

        for line in results:
            for level in summary:
                if level in line:
                    summary[level] += 1

        global latest_results_text, latest_results_rows, history

        plain_results = [
            str(line).replace("<mark>", "").replace("</mark>", "")
            for line in results
        ]

        latest_results_text = "\n".join(plain_results)

        latest_results_rows =[]

        for line in plain_results:
            parts = line.split(" ", 3)

            if len(parts) == 4:
                timestamp = parts[0] + " " + parts[1]
                level = parts[2]
                message = parts[3]
            else:
                timestamp = ""
                level = ""
                message = line

            latest_results_rows.append([timestamp, level, message])

        if len(results) > 0:
            history.append({
                "keyword": keyword,
                "levels": ", ".join(selected_levels),       
                "matches": len(results),
                "searched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            if len(history) > 5:
                history.pop(0)

            save_history(history)
            
            level_stats = {
                "CRITICAL": 0,
                "ERROR": 0,
                "WARNING": 0,
                "INFO": 0,
                "DEBUG": 0,
                "TRACE": 0,
            }

            for item in history:
                levels_text = item.get("levels", "")

                for level in level_stats:
                    if level in levels_text:
                        level_stats[level] += 1

            total_searches = len(history)

            history_search = request.args.get("history_search", "")
            history_sort = request.args.get("history_sort", "newest")

            display_history = history

            if history_search:
                display_history = [
                    item for item in history
                    if (
                        history_search.lower() in item["keyword"].lower()
                        or
                        history_search.lower() in item["levels"].lower()
                    )                        
                ]

            if history_sort == "newest":
                display_history = list(reversed(display_history))

            elif history_sort == "oldest":
                display_history = display_history

            elif history_sort == "keyword":
                display_history = sorted(
                    display_history,
                    key=lambda item: item["keyword"].lower()
                )
                
            successful_searches = sum(
                1 for item in history if item["matches"] > 0
            )

            most_keyword = "N/A"

            if history:
                keyword_counts = {}

                for item in history:
                    key = item["keyword"]
                    keyword_counts[key] = keyword_counts.get(key, 0) + 1

                most_keyword = max(
                    keyword_counts,
                    key=keyword_counts.get
                )
                                        
        return render_template(
            "results.html",
            keyword=keyword,
            results=results,
            total=len(results),
            selected_levels=selected_levels,
            summary=summary,
            case_sensitive=case_sensitive,
            source_name=source_name,
            start_datetime_text=start_datetime_text,
            end_datetime_text=end_datetime_text,
            history=display_history,
            history_search=history_search,
            total_searches=total_searches,
            successful_searches=successful_searches,
            most_keyword=most_keyword,
            level_stats=level_stats,
            history_sort=history_sort,
        )

    return render_template("index.html")

@app.route("/delete-history/<int:index>", methods=["POST"])
def delete_history(index):

    reversed_history = history[::-1]

    if 0 <= index < len(reversed_history):

        item_to_remove = reversed_history[index]

        history.remove(item_to_remove)

        save_history(history)

    return redirect("/")

@app.route("/filter-history")
def filter_history():
    global latest_filtered_history
    history_search = request.args.get("history_search", "")

    display_history = history

    if history_search:
        display_history = [
            item for item in history
            if history_search.lower() in item["keyword"].lower()
        ]
    latest_filtered_history = display_history

    level_stats = {
        "CRITICAL": 0,
        "ERROR": 0,
        "WARNING": 0,
        "INFO": 0,
        "DEBUG": 0,
        "TRACE": 0,
    }

    for item in history:
        levels_text = item.get("levels", "")

        for level in level_stats:
            if level in levels_text:
                level_stats[level] += 1

    return render_template(
        "results.html",
        keyword="",
        results=[],
        total=0,
        selected_levels=[],
        summary={"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0},
        case_sensitive=False,
        source_name="History filter",
        start_datetime_text="",
        end_datetime_text="",
        history=display_history,
        history_search=history_search,
        total_searches=len(history),
        successful_searches=sum(1 for item in history if item["matches"] > 0),
        level_stats=level_stats,
        most_keyword="N/A",
    )

@app.route("/download")
def download_results():
    file_data = BytesIO()

    file_data.write(latest_results_text.encode("utf-8"))

    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.txt",
        mimetype="text/plain"
    )

@app.route("/download-csv")
def download_csv():
    file_data = BytesIO()

    text_stream = "\n".join(
        [",".join(["Timestamp", "Level", "Message"])] +
        [",".join(row) for row in latest_results_rows]
    )

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.csv",
        mimetype="text/csv"
    )

@app.route("/clear-history", methods=["POST"])
def clear_hisrory():
    global history

    history.clear()
    save_history(history)

    return redirect("/")

@app.route("/download-history")
def download_history():
    return send_file(
        "history.json",
        as_attachment=True,
        download_name="history.json"
    )

@app.route("/download-filtered-history")
def download_filtered_history():
    file_data = BytesIO()

    export_data = {
        "total_searches": len(latest_filtered_history),
        "successful_searches": sum(
            1 for item in latest_filtered_history
            if item["matches"] > 0
        ),
        "most_searched_keyword": (
            latest_filtered_history[0]["keyword"]
            if latest_filtered_history
            else "N/A"
        ),
        "history": latest_filtered_history
    }

    text_stream = json.dumps(
        export_data,
        indent=2
        
    )

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="filtered_history.json",
        mimetype="application/json"
    )

@app.route("/download-filtered-history-csv")
def download_filtered_history_csv():
    file_data = BytesIO()

    rows = ["Keyword,Levels,Matches,Searched At"]

    for item in latest_filtered_history:
        rows.append(
            f'"{item.get("keyword", "")}","{item.get("levels", "")}","{item.get("matches", "")}","{item.get("searched_at", "")}"'
        )

    text_stream = "\n".join(rows)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="filtered_history.csv",
        mimetype="text/csv"
    )

@app.route("/download-stats")
def download_stats():
    file_data = BytesIO()

    stats_data = {
        "total_searches": len(history),
        "successful_searches": sum(
            1 for item in history
            if item["matches"] > 0
        ),
        "most_searched_keyword": "N/A",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if history:
        keyword_counts = {}

        for item in history:
            key = item["keyword"]
            keyword_counts[key] = keyword_counts.get(key, 0) + 1

        stats_data["most_searched_keyword"] = max(
            keyword_counts,
            key=keyword_counts.get
        )

    text_stream = json.dumps(stats_data, indent=2)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history_stats.json",
        mimetype="application/json"
    )

@app.route("/download-history-excel")
def download_history_excel():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "History"

    sheet.append(["Keyword", "Levels", "Matches", "Searched At"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for item in history:
        sheet.append([
            item.get("keyword", ""),
            item.get("levels", ""),
            item.get("matches", ""),
            item.get("searched_at", "")
        ])

    stats_sheet = workbook.create_sheet("Stats")

    stats_sheet.append(["Metric", "Value"])
    for cell in stats_sheet[1]:
        cell.font = Font(bold=True)

    stats_sheet.append(["Total searches", len(history)])

    stats_sheet.append([
        "Successful searches",
        sum(1 for item in history if item.get("matches", 0) > 0)
    ])
    
    most_keyword = "N/A"

    if history:
        keyword_counts = {}

        for item in history:
            key = item.get("keyword", "").strip()
            if not key:
                key = "Not set"

            keyword_counts[key] = keyword_counts.get(key, 0) + 1

        most_keyword = max(keyword_counts, key=keyword_counts.get)

    stats_sheet.append(["Most searched keyword", most_keyword])

    stats_sheet.append([])

    stats_sheet.append(["Level", "Count"])
    for cell in stats_sheet[6]:
        cell.font = Font(bold=True)

    for level in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"]:
        count = 0

        for item in history:
            if level in item.get("levels", ""):
                count += 1

        stats_sheet.append([level, count])

    for worksheet in workbook.worksheets:
        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column_cells[0].column)

            for cell in column_cells:
                cell_value = str(cell.value) if cell.value is not None else ""
                max_length = max(max_length, len(cell_value))

            worksheet.column_dimensions[column_letter].width = max_length + 2

    file_data = BytesIO()
    workbook.save(file_data)
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    

if __name__ == "__main__":
    app.run(debug=True)









