import os

def create_html_files():
    data = [
        {"html_path": "html/justified_text.html", "dom_id": "main_text", "attribute": "text", "expected_behavior": "justified"},
        {"html_path": "html/left_aligned_text.html", "dom_id": "main_text", "attribute": "text", "expected_behavior": "left_aligned"},
        {"html_path": "html/right_aligned_text.html", "dom_id": "main_text", "attribute": "text", "expected_behavior": "right_aligned"},
        {"html_path": "html/left_box.html", "dom_id": "main_text", "attribute": "box", "expected_behavior": "left"},
        {"html_path": "html/center_box.html", "dom_id": "main_text", "attribute": "box", "expected_behavior": "center"},
        {"html_path": "html/right_box.html", "dom_id": "main_text", "attribute": "box", "expected_behavior": "right"},
        {"html_path": "html/bold_text.html", "dom_id": "header", "attribute": "text", "expected_behavior": "bold"},
        {"html_path": "html/italic_text.html", "dom_id": "header", "attribute": "text", "expected_behavior": "italic"},
        {"html_path": "html/underlined_text.html", "dom_id": "header", "attribute": "text", "expected_behavior": "underlined"},
        {"html_path": "html/color_text.html", "dom_id": "header", "attribute": "text", "expected_behavior": "colored"}
    ]

    if not os.path.exists("html"):
        os.makedirs("html")

    for entry in data:
        html_content = generate_html(entry["dom_id"], entry["attribute"], entry["expected_behavior"])
        with open(entry["html_path"], "w") as file:
            file.write(html_content)

    print("HTML files created successfully.")

def generate_html(dom_id, attribute, behavior):
    """Generate HTML content based on the attribute and expected behavior."""
    styles = {
        "justified": "text-align: justify;",
        "left_aligned": "text-align: left;",
        "right_aligned": "text-align: right;",
        "left": "float: left;",
        "center": "margin: 0 auto;",
        "right": "float: right;",
        "bold": "font-weight: bold;",
        "italic": "font-style: italic;",
        "underlined": "text-decoration: underline;",
        "colored": "color: red;"
    }
    style = styles.get(behavior, "")

    html_template = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Benchmark - {behavior}</title>
    <style>
        #{dom_id} {{ {style} }}
    </style>
</head>
<body>
    <div id=\"{dom_id}\">This is a sample content for {behavior} testing.</div>
</body>
</html>
"""
    return html_template

if __name__ == "__main__":
    create_html_files()
