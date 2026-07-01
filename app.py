
from flask import Flask, render_template, request, send_file, redirect
from utils import load_history, save_history
from markupsafe import Markup
from io import BytesIO, StringIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Font
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

def clean_export_results(results):
    cleaned = []

    for line in results:
        line = line.replace("<mark>", "")
        line = line.replace("</mark>", "")
        cleaned.append(line)

    return cleaned

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
        
        history.append({
            "keyword": keyword.strip() or "Not set",
            "levels": ", ".join(selected_levels),       
            "matches": len(results),
            "searched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
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
                        history_search.lower() in item.get("keyword", "").lower()
                        
                        or history_search.lower() in item.get("levels", "").lower()
                    )                        
                ]

            if history_sort == "newest":
                display_history = list(reversed(display_history))

            elif history_sort == "oldest":
                display_history = display_history

            elif history_sort == "keyword":
                display_history = sorted(
                    display_history,
                    key=lambda item: item.get("keyword", "").lower()
                )
                
            successful_searches = sum(
                1 for item in history
                if item.get("matches", 0) > 0
            )

            total_matches_found = sum(
                item.get("matches", 0)
                for item in history
            )

            success_rate = 0

            if total_searches > 0:
                success_rate = round((successful_searches / total_searches) * 100)

            average_matches = 0

            if total_searches > 0:
                average_matches = round(total_matches_found / total_searches, 1)                    
                                    
            last_search_time = "N/A"

            if history:
                last_search_time = history[-1].get("searched_at") or "N/A"

            latest_keyword = "Not set"

            if history:
                latest_keyword = history[-1].get("keyword", "").strip()

                if not latest_keyword:
                    latest_keyword = "Not set"

            most_keyword = "N/A"

            if history:
                keyword_counts = {}

                for item in history:
                    key = item.get("keyword", "").strip()

                    if not key:
                        continue

                    keyword_counts[key] = keyword_counts.get(key, 0) + 1

                if keyword_counts:
                    most_keyword = max(
                        keyword_counts,
                        key=keyword_counts.get
                    )
                else:
                    most_keyword = "Not set"

        history_search = request.args.get("history_search", "")
        history_sort = request.args.get("history_sort", "newest")

        display_history = history

        if history_search:
            display_history = [
                item for item in history
                if history_search.lower() in item.get("keyword", "").lower()
            ]

        if history_sort == "oldest":
            display_history = list(reversed(display_history))

        total_searches = len(history)

        chart_labels = []
        chart_values = []

        for item in history:
            label = item.get("keyword", "").strip()
            if not label:
                label = "Not set"

            chart_labels.append(label)
            chart_values.append(item.get("matches", 0))
                                        
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
            total_matches_found=total_matches_found,
            average_matches=average_matches,
            success_rate=success_rate,
            most_keyword=most_keyword,
            latest_keyword=latest_keyword,
            last_search_time=last_search_time,
            level_stats=level_stats,
            history_sort=history_sort,
            chart_labels=chart_labels,
            chart_values=chart_values,
        )

    return render_template("index.html")

@app.route("/view-history/<int:index>")
def view_history(index):
    if index < 0 or index >= len(history):
        return redirect("/filter-history")

    item = history[index]

    level_stats = {
        "CRITICAL": 0,
        "ERROR": 0,
        "WARNING": 0,
        "INFO": 0,
        "DEBUG": 0,
        "TRACE": 0,
    }

    for x in history:
        levels_text = x.get("levels", "")

        for level in level_stats:
            if level in levels_text:
                level_stats[level] += 1

    total_searches = len(history)
    successful_searches = sum(
        1 for x in history if x.get("matches", 0) > 0
    )

    total_matches_found = sum(
        x.get("matches", 0) for x in history
    )

    success_rate = 0
    if total_searches > 0:
        success_rate = round((successful_searches / total_searches) * 100)

    average_matches = 0
    if total_searches > 0:
        average_matches = round(total_matches_found / total_searches, 1)

    chart_labels = []
    chart_values = []

    for x in history:
        label = x.get("keyword", "").strip()

        if not label:
            label = "Not set"

        chart_labels.append(label)
        chart_values.append(x.get("matches", 0))

    most_keyword = "Not set"

    if history:
        keyword_counts = {}

        for x in history:
            key = x.get("keyword", "").strip()

            if not key:
                continue

            keyword_counts[key] = keyword_counts.get(key, 0) + 1

        if keyword_counts:
            most_keyword = max(
                keyword_counts,
                key=keyword_counts.get
            )
        
    return render_template(
        "results.html",
        keyword=item.get("keyword", ""),
        results=item.get("results", []),
        total=item.get("matches", 0),
        selected_levels=item.get("levels", "").split(", "),
        summary={},
        case_sensitive=False,
        source_name="History View",
        start_datetime_text="",
        end_datetime_text="",
        history=history,
        history_search="",
        total_searches=total_searches,
        successful_searches=successful_searches,        
        total_matches_found=total_matches_found,
        success_rate=success_rate,
        average_matches=average_matches,
        latest_keyword=item.get("keyword", ""),
        last_search_time=item.get("searched_at", ""),
        level_stats=level_stats,
        most_keyword=most_keyword,
        history_sort="newest",
        chart_labels=chart_labels,
        chart_values=chart_values,
    )

@app.route("/delete-history/<int:index>", methods=["POST"])
def delete_history(index):
    if 0 <= index < len(history):
        history.pop(index)
        save_history(history)
        
    return redirect("/filter-history")

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

    total_matches_found = sum(
        item.get("matches", 0)
        for item in history
    )

    success_rate = 0
    if len(history) > 0:
        success_rate = round((sum(1 for item in history if item["matches"] > 0) / len(history)) * 100)

    average_matches = 0
    if len(history) > 0:
        average_matches = round(total_matches_found / len(history), 1)

    latest_keyword = "Not set"
    if history:
        latest_keyword = history[-1].get("keyword", "").strip()
        if not latest_keyword:
            latest_keyword = "Not set"

    last_searh_time = "N/A"
    if history:
        last_search_time = history[-1].get("searched_at") or "N/A"

    most_keyword = "Not set"

    keyword_counts = {}

    for item in history:
        key = item.get("keyword", "").strip()

        if not key:
            continue

        keyword_counts[key] = keyword_counts.get(key, 0) + 1

    if keyword_counts:
        most_keyword = max(
            keyword_counts,
            key=keyword_counts.get
        )

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
        total_matches_found=total_matches_found,
        success_rate=success_rate,
        average_matches=average_matches,
        latest_keyword=latest_keyword,
        last_search_time=last_search_time,
        level_stats=level_stats,
        most_keyword=most_keyword,
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

@app.route("/download-history-csv")
def download_history_csv():
    file_data = BytesIO()

    rows = ["Keyword,Levels,Matches,Searched At"]

    for item in history:
        rows.append(
            f'"{item.get("keyword", "")}",'
            f'"{item.get("levels", "")}",'
            f'"{item.get("matches", "")}",'
            f'"{item.get("searched_at", "")}",'
        )

    text_stream = "\n".join(rows)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history.csv",
        mimetype="text/csv"
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

@app.route("/download-stats")
def download_stats():
    file_data = BytesIO()

    stats_data = {
        "total_searches": len(history),
        "successful_searches": sum(
            1 for item in history
            if item["matches"] > 0
        ),
        "total_matches_found": sum(
            item["matches"] for item in history
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
@app.route("/download-stats-csv")
def download_stats_csv():

    csv_data = StringIO()

    csv_data.write("Metric,Value\n")
    csv_data.write(f"Total searches,{len(history)}\n")

    successful_searches = sum(
        1 for item in history
        if item.get("matches", 0) > 0
    )

    csv_data.write(f"Successful searches,{successful_searches}\n")

    total_matches = sum(
        item.get("matches", 0)
        for item in history
    )

    csv_data.write(f"Total matches found,{total_matches}\n")

    csv_data.write("Most searched keyword,Not set\n")

    file_data = BytesIO()
    file_data.write(csv_data.getvalue().encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history_stats.csv",
        mimetype="text/csv"
    )
                                                                    
@app.route("/download-history-excel")
def download_history_excel():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "History"
    sheet.freeze_panes = "A2"

    sheet.append(["Keyword", "Levels", "Matches", "Searched At"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for cell in sheet[1]:
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="D9EAD3",
            end_color="D9EAD3"
        )

    for item in history:
        sheet.append([
            item.get("keyword", ""),
            item.get("levels", ""),
            item.get("matches", ""),
            item.get("searched_at", "")
        ])

    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter

        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass

        sheet.column_dimensions[column_letter].width = max_length + 2

    summary_sheet = workbook.create_sheet("summary")
    summary_sheet.freeze_panes = "A2"

    

    summary_sheet.append(["Summary Metric", "value"])

    for cell in summary_sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="D9EAD3",
            end_color="D9EAD3"
        )
            

    stats_sheet = workbook.create_sheet("Stats")
    stats_sheet.freeze_panes = "A2"

    stats_sheet.append(["Metric", "Value"])
    for cell in stats_sheet[1]:
        cell.font = Font(bold=True)

    for cell in stats_sheet[1]:
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="D9EAD3",
            end_color="D9EAD3",
        )

    
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

        summary_sheet.append(["Total searches", len(history)])

        summary_sheet.append([
            "Successful searches",
            sum(1 for item in history if item.get("matches", 0) > 0)
        ])

        summary_sheet.append([
            "Total matches found",
            sum(item.get("matches", 0) for item in history)
        ])

        summary_sheet.append([
            "Most searched keyword",
            most_keyword
        ])

    stats_sheet.append(["Most searched keyword", most_keyword])

    stats_sheet.append([])

    stats_sheet.append(["Level", "Count"])
    for cell in stats_sheet[6]:
        cell.font = Font(bold=True)

    for cell in stats_sheet[6]:
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="D9EAD3",
            end_color="D9EAD3",
        )
    
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

    stripe_fill = PatternFill(
        fill_type="solid",
        start_color="F2F2F2",
        end_color="F2F2F2",
    )
    critical_fill = PatternFill(
        start_color="FF9999",
        end_color="FF9999",
        fill_type="solid",
    )

    error_fill = PatternFill(
        start_color="FFCC99",
        end_color="FFCC99",
        fill_type="solid",
    )

    warning_fill = PatternFill(
        start_color="FFFF99",
        end_color="FFFF99",
        fill_type="solid",
    )

    info_fill = PatternFill(
        start_color="CCFFFF",
        end_color="CCFFFF",
        fill_type="solid",
    )

    debug_fill = PatternFill(
        start_color="DDDDDD",
        end_color="DDDDDD",
        fill_type="solid",
    )

    trcae_fill = PatternFill(
        start_color="CCFFCC",
        end_color="CCFFCC",
        fill_type="solid",
    )

    for row in sheet.iter_rows(min_row=2):
        if row[0].row % 2 ==0:
            for cell in row:
                cell.fill = stripe_fill

    for row in sheet.iter_rows(min_row=2):
        levels_cell = row[1]
        levels_text = str(levels_cell.value or "")

        if "CRITICAL" in levels_text:
            levels_cell.fill = critical_fill
        elif "ERROR" in levels_text:
            levels_cell.fill = error_fill
        elif "WARNING" in levels_text:
            levels_cell.fill = warning_fill
        elif "INFO" in levels_text:
            levels_cell.fill = info_fill
        elif "DEBUG" in levels_text:
            levels_cell.fill = debug_fill
        elif "TRACE" in levels_text:
            levels_cell.fill = trace_fill

    summary_sheet.auto_filter.ref = summary_sheet.dimensions            
    stats_sheet.auto_filter.ref = stats_sheet.dimensions
    
    file_data = BytesIO()
    workbook.save(file_data)
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/download-filtered-history-excel")
def download_filtered_history_excel():
    history_search = request.args.get("history_search", "")
    history_sort = request.args.get("history_sort", "newest")

    display_history = history

    if history_search:
        display_history = [
            item for item in history
            if (
                history_search.lower() in item.get("keyword", "").lower()
                or history_search.lower() in item.get("levels", "").lower()
            )
        ]

    if history_sort == "newest":
        display_history = list(reversed(display_history))

    elif history_sort == "oldest":
        display_history = display_history

    elif history_sort == "keyword":
        display_history = sorted(
            display_history,
            key=lambda item: item.get("keyword", "").lower()
        )

    # return "Filtered Excel route ready"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Filtered History"

    sheet.append(["Keyword", "Levels", "Matches", "Searched At"])

    for item in display_history:
        sheet.append([
            item.get("keyword", ""),
            item.get("levels", ""),
            item.get("matches", ""),
            item.get("searched_at", "")
        ])

    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter

        for cell in column:
            cell_value = str(cell.value) if cell.value is not None else ""
            max_length = max(max_length, len(cell_value))

    sheet.column_dimensions["A"].width = 15
    sheet.column_dimensions["B"].width = 45
    sheet.column_dimensions["C"].width = 12
    sheet.column_dimensions["D"].width = 25

    for cell in sheet[1]:
        cell.font =Font(bold=True)
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="D9EAD3",
            end_color="D9EAD3",
        )
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
            
    file_data = BytesIO()
    workbook.save(file_data)
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="filtered_history.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/download-filtered-history-csv")
def download_filtered_history_csv():
    history_search = request.args.get("history_search", "")
    history_sort = request.args.get("history_sort", "newest")

    display_history = history

    if history_search:
        display_history = [
            item for item in history
            if (
                history_search.lower() in item.get("keyword", "").lower()
                or history_search.lower() in item.get("levels", "").lower()
            )
        ]
    if history_sort == "newest":
        display_history = list(reversed(display_history))

    elif history_sort == "oldest":
        display_history = display_history

    elif history_sort == "keyword":
        display_history = sorted(
            display_history,
            key=lambda item: item.get("keyword", "").lower()
        )

    file_data = BytesIO()

    rows = ["Keyword,Levels,Matches,Searched At"]

    for item in display_history:
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
    
@app.route("/download-filtered-history-json")
def download_filtered_history_json():
    history_search = request.args.get("history_search", "")
    history_sort = request.args.get("history_sort", "newest")

    display_history = history

    if history_search:
        display_history = [
            item for item in history
            if (
                history_search.lower() in item.get("keyword", "").lower()
                or history_search.lower() in item.get("levels", "").lower()
            )
        ]

    if history_sort == "newest":
        display_history = list(reversed(display_history))

    elif history_sort == "oldest":
        dispaly_history = display_history

    elif history_sort == "keyword":
        display_history = sorted(
            display_history,
            key=lambda item: item.get("keword", "").lower()
        )
    file_data = BytesIO()

    export_history = []

    for item in display_history:
        new_item = item.copy()

        if not new_item.get("keyword", "").strip():
            new_item["keyword"] = "Not set"

        new_item["results"] = clean_export_results(
            new_item.get("results", [])
        )

        export_history.append(new_item)
        
    text_stream = json.dumps(export_history, indent=2)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="filtered_history.json",
        mimetype="application/json"
    )

@app.route("/download-stats-json")
def download_stats_json():
    print(history)

    top_kayword = "Not set"
    keyword_counts = {}

    for item in history:
        key = item.get("keyword", "").strip()

        if not key:
            key = "Not set"

        keyword_counts[key] = keyword_counts.get(key, 0) + 1

    if keyword_counts:
        top_keyword = max(
            keyword_counts,
            key=keyword_counts.get
        )

    latest_keyword = "Not set"
    last_search = "Not set"

    if history:
        latest = history[-1]
        latest_keyword = latest.get("keyword", "").strip()

        if not latest_keyword:
            latest_keyword = "Not set"

        last_search =latest.get("searched_at", "Not set")

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
                level_stats[level] +=1
        
    stats = {
        "total_searches": len(history),
        "successful_searches": sum(
            1 for item in history if item.get("matches", 0) > 0
        ),
        "success_rate": round(
            (sum(1 for item in history if item.get("matches", 0) > 0) / len(history)) * 100
        ) if history else 0,
        "total_matches": sum(
            item.get("matches", 0) for item in history
        ),
        "average_matches": round(
            sum(item.get("matches", 0) for item in history) / len(history),
            1
        ) if history else 0,
        "top_keyword": top_keyword,
        "latest_keyword": latest_keyword,
        "last_search": last_search,
        "level_stats": level_stats
    }

    file_data = BytesIO()
    text_stream = json.dumps(stats, indent=2)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="history_stats.json",
        mimetype="application/json"
    )

@app.route("/download-analysis-txt")
def download_analysis_txt():
    lines = []
    if history:
        latest = history[-1]

        lines.append(f"Keyword: {latest.get('keyword', 'Not set')}")
        lines.append(f"Levels: {latest.get('levels', 'All')}")
        lines.append(f"Matches: {latest.get('matches', 0)}")
        lines.append("")
        lines.append("-" * 40)

        for line in latest.get("results", []):
            line = line.replace("<msrks>", "")
            line = line.replace("</marks>", "")
            lines.append(line)

    text = "\n".join(lines)
                
    file_data = BytesIO()
    file_data.write(text.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.txt",
        mimetype="text/plain"
    )

@app.route("/download-analysis-csv")
def download_analysis_csv():
    file_data = BytesIO()
    text_stream = StringIO()
    writer = csv.writer(text_stream)

    writer.writerow(["Level", "Message"])

    if history:
        latest = history[-1]

        for line in latest.get("results", []):
            line = line.replace("<marks>", "")
            line = line.replace("</marks>", "")

            parts = line.split(" ", 1)

            if len(parts) == 2:
                level = parts[0]
                message = parts[1]
            else:
                level = "UNKNOWN"
                message = line

            writer.writerow([level, message])
    file_data.write(text_stream.getvalue().encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.csv",
        mimetype="text/csv"
    )

@app.route("/download-analysis-json")
def download_analysis_json():
    latest = history[-1] if history else {}

    results = []

    for line in latest.get("results", []):
        line = line.replace("<mark>", "")
        line = line.replace("</mark>", "")

        parts = line.split(" ", 1)

        if len(parts) == 2:
            level = parts[0]
            message = parts[1]
        else:
            level = "UNKNOWN"
            message = line

        results.append({
            "level": level,
            "message": message
        })
        print("JSON results count:", len(results))

    data = {
        "keyword": latest.get("keyword", "Not set"),
        "levels": latest.get("levels", ""),
        "matches": latest.get("matches", 0),
        "results": results
    }
        
             
    file_data = BytesIO()
    text_stream = json.dumps(data, indent=2)

    file_data.write(text_stream.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.json",
        mimetype="application/json"
    )

@app.route("/download-analysis-html")
def download_analysis_html():
    latest = history[-1] if history else {}

    keyword = latest.get("keyword", "Not set")
    levels = latest.get("levels", "")
    matches = latest.get("matches", 0)

    result_lines = ""
    for line in latest.get("results", []):
        line = line.replace("<marks>", "")
        line = line.replace("</marks>", "")
        if line.startswith("CRITICAL"):
            css_class = "critical-report"
        elif line.startswith("ERROR"):
            css_class = "error-report"
        elif line.startswith("WARNING"):
            css_class = "warning-report"
        elif line.startswith("INFO"):
            css_class = "info-report"
        elif line.startswith("DEBUG"):
            css_class = "debug-report"
        elif line.startswith("TRACE"):
            css_class = "trace-report"
        else:
            css_class = ""
            
        result_lines += f'<li><pre class="{css_class}">{line}</pre></li>'
        
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analysis Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f6f8;
                padding: 30px;
            }}
            .report {{
                max-width: 900px;
                margin: auto;
                background: white;
                border-radius: 10px;
            }}

            pre {{
                padding: 10px;
                border-left: 5px solid #555;
                background-color: #f1f1f1;
                border-radius: 6px;
            }}

            .critical-report {{
                border-left-color: #b00020;
                background-color: #ffe5e5;
            }}

            .error-report {{
                border-left-color: #d32f2f;
                background-color: #fff0f0;
            }}

            .warning-report {{
                border-left-color: #f9a825;
                background-color: #fff8d6;
            }}

            .info-report {{
                border-left-color: #1976d2;
                background-color: #e8f2ff;
            }}

            .debug-report {{
                border-left-color: #2e7d32;
                background-color: #eaf7ea;
            }}

            .trace-report {{
                border-left-color: #777777;
                background-color: #eeeeee;
            }}
        </style>
    </head>
    <body>
        <div class="report">
        </div>
    </body>
        <h1>Analysis Report</h1>

        <p><strong>Keyword:<strong> {keyword}</p>
        <p><strong>Levels:</strong> {levels}</p>
        <p><strong>Matches:</strong> {matches}</p>

        <h2>Matching Lines</h2>
        <ul>
            {result_lines}
        </ul>
    </body>
    </html>
    """

    file_data=BytesIO()
    file_data.write(html.encode("utf-8"))
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_report.html",
        mimetype="text/html"
    )

@app.route("/download-analysis-excel")
def download_analysis_excel():

    latest = history[-1] if history else {}

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Analysis Results"

    sheet["A1"] = "Level"
    sheet["B1"] = "Message"

    for line in latest.get("results", []):
        line = line.replace("<marks>", "")
        line = line.replace("</marks>", "")

        parts = line.split(" ", 1)

        if len(parts) ==2:
            level = parts[0]
            message = parts[1]
        else:
            level = "UNKNOWN"
            message = line

        sheet.append([level, message])

    file_data = BytesIO()
    workbook.save(file_data)
    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="analysis_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    
    
    


        
    
if __name__ == "__main__":
    app.run(debug=True)


































