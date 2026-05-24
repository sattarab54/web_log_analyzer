
from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        log_text = request.form.get("log_text", "")
        uploaded_file = request.files.get("log_file")
        source_name = "Pasted text"
        keyword = request.form.get("keyword", "")
        selected_levels = request.form.getlist("levels")
        case_sensitive = "case_sensitive" in request.form

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

        # 2. selected level filter
        if selected_levels:
            lines = [
                line for line in lines
                if any(line.startswith(level) for level in selected_levels)
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
                              
        # 4. summary from final results
        summary = {
            "ERROR": 0,
            "WARNING": 0,
            "INFO": 0,
            "DEBUG": 0,
        }

        for line in results:
            for level in summary:
                if line.startswith(level):
                    summary[level] += 1
        
        return render_template(
            "results.html",
            keyword=keyword,
            results=results,
            total=len(results),
            selected_levels=selected_levels,
            summary=summary,
            case_sensitive=case_sensitive,
            source_name=source_name,
        )

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)








