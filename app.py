
from flask import Flask, render_template, request, send_file
from markupsafe import Markup
from io import BytesIO
from datetime import datetime
import re

app = Flask(__name__)

latest_results_text = ""

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
            "ERROR": 0,
            "WARNING": 0,
            "INFO": 0,
            "DEBUG": 0,
        }

        for line in results:
            for level in summary:
                if level in line:
                    summary[level] += 1

        global latest_results_text

        plain_results = [
            str(line).replace("<mark>", "").replace("</mark>", "")
            for line in results
        ]

        latest_results_text = "\n".join(plain_results)
        
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
        )

    return render_template("index.html")

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


if __name__ == "__main__":
    app.run(debug=True)








