#!/usr/bin/env python3
"""
Benchmark Test Data Generator for LayoutLens

This script generates HTML test files for benchmarking LayoutLens's UI analysis capabilities.
It creates paired good/bad examples for various UI testing categories.
"""

import json
import os
from pathlib import Path
from typing import Any

# Get the benchmarks directory path
BENCHMARKS_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BENCHMARKS_DIR / "templates"
TEST_DATA_DIR = BENCHMARKS_DIR / "test_data"
ANSWER_KEYS_DIR = BENCHMARKS_DIR / "answer_keys"


def load_template(template_name: str = "base_template.html") -> str:
    """Load the specified HTML template."""
    template_path = TEMPLATES_DIR / template_name
    with open(template_path) as f:
        return f.read()


def generate_html(title: str, custom_styles: str, content: str, template_name: str = "base_template.html") -> str:
    """Generate HTML from template with provided content."""
    template = load_template(template_name)
    html = template.replace("{{TITLE}}", title)
    html = html.replace("{{CUSTOM_STYLES}}", custom_styles)
    html = html.replace("{{CONTENT}}", content)
    return html


# Available templates for testing different UI patterns
TEMPLATES = [
    ("modern_template.html", "Modern"),
    ("bootstrap_template.html", "Bootstrap"),
    ("dense_template.html", "Dense"),
    ("visual_template.html", "Visual"),
    ("minimal_template.html", "Minimal"),
]


def get_template_for_test(test_name: str, category: str) -> tuple[str, str]:
    """Get template for a specific test to ensure variety."""
    # Distribute templates across tests to ensure coverage
    template_index = hash(f"{category}_{test_name}") % len(TEMPLATES)
    template_file, template_type = TEMPLATES[template_index]
    return template_file, template_type


def create_layout_alignment_tests():
    """Generate layout alignment test files using different templates."""
    category_dir = TEST_DATA_DIR / "layout_alignment"
    category_dir.mkdir(parents=True, exist_ok=True)

    # Test configurations
    tests = [
        {
            "name": "nav_centered",
            "title": "Centered Navigation Test",
            "styles": """
                nav {
                    position: fixed;
                    top: 0;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #2c3e50;
                    padding: 1rem 2rem;
                    border-radius: 0 0 10px 10px;
                    z-index: 1000;
                }

                nav ul {
                    display: flex;
                    list-style: none;
                    gap: 2rem;
                }

                nav a {
                    color: white;
                    text-decoration: none;
                    font-weight: 500;
                }

                main { padding-top: 80px; }
            """,
            "content": """
            <nav role="navigation" aria-label="Main navigation">
                <ul>
                    <li><a href="#home">Home</a></li>
                    <li><a href="#about">About</a></li>
                    <li><a href="#services">Services</a></li>
                    <li><a href="#contact">Contact</a></li>
                </ul>
            </nav>
            <main class="container">
                <h1>Perfectly Centered Navigation</h1>
                <p>The navigation bar above is perfectly centered using CSS transforms.</p>
            </main>
            """,
        },
        {
            "name": "nav_misaligned",
            "title": "Misaligned Navigation Test",
            "styles": """
                nav {
                    position: fixed;
                    top: 0;
                    left: 52%;  /* Intentionally 2% off-center */
                    transform: translateX(-50%);
                    background: #2c3e50;
                    padding: 1rem 2rem;
                    border-radius: 0 0 10px 10px;
                    z-index: 1000;
                }

                nav ul {
                    display: flex;
                    list-style: none;
                    gap: 2rem;
                }

                nav a {
                    color: white;
                    text-decoration: none;
                    font-weight: 500;
                }

                main { padding-top: 80px; }
            """,
            "content": """
            <nav role="navigation" aria-label="Main navigation">
                <ul>
                    <li><a href="#home">Home</a></li>
                    <li><a href="#about">About</a></li>
                    <li><a href="#services">Services</a></li>
                    <li><a href="#contact">Contact</a></li>
                </ul>
            </nav>
            <main class="container">
                <h1>Slightly Misaligned Navigation</h1>
                <p>The navigation bar is 2% off-center - a subtle but noticeable issue.</p>
            </main>
            """,
        },
    ]

    # Generate tests with different templates
    for test in tests:
        template_file, template_type = get_template_for_test(test["name"], "layout_alignment")
        filename = f"{test['name']}_{template_type.lower()}.html"

        with open(category_dir / filename, "w") as f:
            f.write(generate_html(test["title"], test["styles"], test["content"], template_file))

    # Navigation misaligned (2% off)
    nav_misaligned_styles = """
        nav {
            position: fixed;
            top: 0;
            left: 52%;  /* Intentionally 2% off-center */
            transform: translateX(-50%);
            background: #2c3e50;
            padding: 1rem 2rem;
            border-radius: 0 0 10px 10px;
            z-index: 1000;
        }

        nav ul {
            display: flex;
            list-style: none;
            gap: 2rem;
        }

        nav a {
            color: white;
            text-decoration: none;
            font-weight: 500;
        }

        main { padding-top: 80px; }
    """

    nav_misaligned_content = """
    <nav role="navigation" aria-label="Main navigation">
        <ul>
            <li><a href="#home">Home</a></li>
            <li><a href="#about">About</a></li>
            <li><a href="#services">Services</a></li>
            <li><a href="#contact">Contact</a></li>
        </ul>
    </nav>
    <main class="container">
        <h1>Slightly Misaligned Navigation</h1>
        <p>The navigation bar is 2% off-center - a subtle but noticeable issue.</p>
    </main>
    """

    with open(category_dir / "nav_misaligned.html", "w") as f:
        f.write(generate_html("Misaligned Navigation Test", nav_misaligned_styles, nav_misaligned_content))

    # Flexbox centering (correct)
    flexbox_correct_styles = """
        .hero {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .hero-content {
            text-align: center;
            color: white;
            padding: 2rem;
        }

        .hero h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
    """

    flexbox_correct_content = """
    <div class="hero">
        <div class="hero-content">
            <h1>Perfectly Centered Hero</h1>
            <p>This content is centered both horizontally and vertically using flexbox.</p>
            <button style="padding: 0.75rem 2rem; font-size: 1.1rem; border: none;
                          background: white; color: #667eea; border-radius: 50px;
                          cursor: pointer; margin-top: 1rem;">Get Started</button>
        </div>
    </div>
    """

    with open(category_dir / "flexbox_center_correct.html", "w") as f:
        f.write(generate_html("Flexbox Centering Test (Correct)", flexbox_correct_styles, flexbox_correct_content))

    # Flexbox centering (broken)
    flexbox_broken_styles = """
        .hero {
            display: flex;
            justify-content: center;
            /* Missing align-items: center - content won't be vertically centered */
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .hero-content {
            text-align: center;
            color: white;
            padding: 2rem;
        }

        .hero h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
    """

    flexbox_broken_content = """
    <div class="hero">
        <div class="hero-content">
            <h1>Broken Vertical Centering</h1>
            <p>This content is only horizontally centered. Vertical centering is broken.</p>
            <button style="padding: 0.75rem 2rem; font-size: 1.1rem; border: none;
                          background: white; color: #667eea; border-radius: 50px;
                          cursor: pointer; margin-top: 1rem;">Get Started</button>
        </div>
    </div>
    """

    with open(category_dir / "flexbox_center_broken.html", "w") as f:
        f.write(generate_html("Flexbox Centering Test (Broken)", flexbox_broken_styles, flexbox_broken_content))

    # CSS Grid layout (correct)
    grid_correct_styles = """
        .grid-container {
            display: grid;
            grid-template-areas:
                "header header header"
                "sidebar main aside"
                "footer footer footer";
            grid-template-columns: 200px 1fr 200px;
            grid-template-rows: 80px 1fr 60px;
            gap: 1rem;
            min-height: 100vh;
            padding: 1rem;
        }

        .header {
            grid-area: header;
            background: #3498db;
            display: flex;
            align-items: center;
            padding: 0 2rem;
            color: white;
        }

        .sidebar {
            grid-area: sidebar;
            background: #ecf0f1;
            padding: 1rem;
        }

        .main {
            grid-area: main;
            background: white;
            padding: 2rem;
            border: 1px solid #bdc3c7;
        }

        .aside {
            grid-area: aside;
            background: #ecf0f1;
            padding: 1rem;
        }

        .footer {
            grid-area: footer;
            background: #2c3e50;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
    """

    grid_correct_content = """
    <div class="grid-container">
        <header class="header">
            <h1>CSS Grid Layout - Properly Structured</h1>
        </header>
        <nav class="sidebar">
            <h2>Sidebar</h2>
            <ul style="list-style: none; padding: 0;">
                <li><a href="#">Link 1</a></li>
                <li><a href="#">Link 2</a></li>
                <li><a href="#">Link 3</a></li>
            </ul>
        </nav>
        <main class="main">
            <h2>Main Content Area</h2>
            <p>This layout uses CSS Grid with proper semantic areas defined.</p>
            <p>Each section is properly placed in its designated grid area.</p>
        </main>
        <aside class="aside">
            <h2>Aside</h2>
            <p>Related content</p>
        </aside>
        <footer class="footer">
            <p>&copy; 2024 Grid Layout Example</p>
        </footer>
    </div>
    """

    with open(category_dir / "grid_layout_correct.html", "w") as f:
        f.write(generate_html("CSS Grid Layout Test (Correct)", grid_correct_styles, grid_correct_content))

    # CSS Grid layout (broken)
    grid_broken_styles = """
        .grid-container {
            display: grid;
            /* Broken: grid areas don't match the template */
            grid-template-areas:
                "header header header"
                "sidebar main aside"
                "footer footer footer";
            grid-template-columns: 200px 1fr 200px;
            grid-template-rows: 80px 1fr 60px;
            gap: 1rem;
            min-height: 100vh;
            padding: 1rem;
        }

        .header {
            grid-area: top;  /* Wrong area name */
            background: #3498db;
            display: flex;
            align-items: center;
            padding: 0 2rem;
            color: white;
        }

        .sidebar {
            grid-area: left;  /* Wrong area name */
            background: #ecf0f1;
            padding: 1rem;
        }

        .main {
            grid-area: center;  /* Wrong area name */
            background: white;
            padding: 2rem;
            border: 1px solid #bdc3c7;
        }

        .aside {
            grid-area: right;  /* Wrong area name */
            background: #ecf0f1;
            padding: 1rem;
        }

        .footer {
            grid-area: bottom;  /* Wrong area name */
            background: #2c3e50;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
    """

    grid_broken_content = """
    <div class="grid-container">
        <header class="header">
            <h1>CSS Grid Layout - Broken Structure</h1>
        </header>
        <nav class="sidebar">
            <h2>Sidebar</h2>
            <ul style="list-style: none; padding: 0;">
                <li><a href="#">Link 1</a></li>
                <li><a href="#">Link 2</a></li>
                <li><a href="#">Link 3</a></li>
            </ul>
        </nav>
        <main class="main">
            <h2>Main Content Area</h2>
            <p>This layout has broken CSS Grid area definitions.</p>
            <p>Elements won't be placed correctly in the grid.</p>
        </main>
        <aside class="aside">
            <h2>Aside</h2>
            <p>Related content</p>
        </aside>
        <footer class="footer">
            <p>&copy; 2024 Broken Grid Example</p>
        </footer>
    </div>
    """

    with open(category_dir / "grid_layout_broken.html", "w") as f:
        f.write(generate_html("CSS Grid Layout Test (Broken)", grid_broken_styles, grid_broken_content))

    print(f"✅ Generated {len(list(category_dir.glob('*.html')))} layout alignment test files")


def create_accessibility_tests():
    """Generate accessibility test files."""
    category_dir = TEST_DATA_DIR / "accessibility"
    category_dir.mkdir(parents=True, exist_ok=True)

    # Focus management (good)
    focus_good_styles = """
        .modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            width: 90%;
        }

        .modal.open {
            display: block;
        }

        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
        }

        .modal-overlay.open {
            display: block;
        }

        button {
            padding: 0.5rem 1rem;
            font-size: 1rem;
            border: 2px solid #3498db;
            background: #3498db;
            color: white;
            border-radius: 4px;
            cursor: pointer;
        }

        button:hover {
            background: #2980b9;
        }

        .close-btn {
            background: #e74c3c;
            border-color: #e74c3c;
            float: right;
        }
    """

    focus_good_content = """
    <main class="container">
        <h1>Modal with Proper Focus Management</h1>
        <p>This modal implements proper focus trapping and management.</p>
        <button onclick="openModal()" id="open-btn">Open Modal</button>
    </main>

    <div class="modal-overlay" id="overlay"></div>
    <div class="modal" id="modal" role="dialog" aria-labelledby="modal-title" aria-modal="true">
        <button class="close-btn" onclick="closeModal()" aria-label="Close modal">×</button>
        <h2 id="modal-title">Accessible Modal</h2>
        <p>This modal properly manages focus. Tab navigation is trapped within the modal.</p>
        <input type="text" placeholder="Enter your name" aria-label="Name input">
        <button onclick="closeModal()">Confirm</button>
    </div>

    <script>
        let previousFocus;

        function openModal() {
            previousFocus = document.activeElement;
            document.getElementById('overlay').classList.add('open');
            document.getElementById('modal').classList.add('open');
            document.getElementById('modal').querySelector('button').focus();

            // Add focus trap
            document.addEventListener('keydown', trapFocus);
        }

        function closeModal() {
            document.getElementById('overlay').classList.remove('open');
            document.getElementById('modal').classList.remove('open');
            document.removeEventListener('keydown', trapFocus);

            if (previousFocus) {
                previousFocus.focus();
            }
        }

        function trapFocus(e) {
            if (e.key === 'Escape') {
                closeModal();
            }

            if (e.key === 'Tab') {
                const modal = document.getElementById('modal');
                const focusable = modal.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])');
                const first = focusable[0];
                const last = focusable[focusable.length - 1];

                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
    </script>
    """

    with open(category_dir / "focus_management_good.html", "w") as f:
        f.write(generate_html("Focus Management Test (Good)", focus_good_styles, focus_good_content))

    # Focus management (broken)
    focus_broken_styles = focus_good_styles  # Same styles

    focus_broken_content = """
    <main class="container">
        <h1>Modal without Focus Management</h1>
        <p>This modal lacks proper focus trapping and management.</p>
        <button onclick="document.getElementById('modal').style.display='block'">Open Modal</button>
    </main>

    <!-- No overlay, no focus trap, no ARIA attributes -->
    <div id="modal" style="display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
                           background:white; padding:2rem; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
        <button style="float:right" onclick="this.parentElement.style.display='none'">×</button>
        <h2>Inaccessible Modal</h2>
        <p>This modal doesn't manage focus. Users can tab outside the modal.</p>
        <input type="text" placeholder="Enter your name">
        <button onclick="this.parentElement.style.display='none'">Confirm</button>
    </div>
    """

    with open(category_dir / "focus_management_broken.html", "w") as f:
        f.write(generate_html("Focus Management Test (Broken)", focus_broken_styles, focus_broken_content))

    print(f"✅ Generated {len(list(category_dir.glob('*.html')))} accessibility test files")


def create_responsive_tests():
    """Generate responsive design test files."""
    category_dir = TEST_DATA_DIR / "responsive_design"
    category_dir.mkdir(parents=True, exist_ok=True)

    # Container queries (good)
    container_queries_styles = """
        @container (min-width: 700px) {
            .card {
                display: grid;
                grid-template-columns: 200px 1fr;
                gap: 2rem;
            }
        }

        .card-container {
            container-type: inline-size;
            container-name: card;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .card img {
            width: 100%;
            height: auto;
            border-radius: 4px;
        }

        .grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            padding: 2rem;
        }
    """

    container_queries_content = """
    <main class="grid">
        <div class="card-container">
            <article class="card">
                <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='150' viewBox='0 0 200 150'%3E%3Crect fill='%23ddd' width='200' height='150'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EProduct%3C/text%3E%3C/svg%3E" alt="Product placeholder">
                <div>
                    <h2>Container Query Card</h2>
                    <p>This card uses container queries for responsive layout. It adapts based on its container size, not viewport.</p>
                </div>
            </article>
        </div>

        <div class="card-container">
            <article class="card">
                <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='150' viewBox='0 0 200 150'%3E%3Crect fill='%23ddd' width='200' height='150'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EProduct%3C/text%3E%3C/svg%3E" alt="Product placeholder">
                <div>
                    <h2>Another Card</h2>
                    <p>Each card responds individually to its container size using modern container queries.</p>
                </div>
            </article>
        </div>
    </main>
    """

    with open(category_dir / "container_queries_good.html", "w") as f:
        f.write(generate_html("Container Queries Test", container_queries_styles, container_queries_content))

    # Viewport units (broken)
    viewport_broken_styles = """
        /* Using vh units without considering mobile browser chrome */
        .hero {
            height: 100vh;  /* Will be too tall on mobile with address bar */
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
        }

        .section {
            min-height: 100vh;  /* Each section forced to viewport height */
            padding: 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .section:nth-child(even) {
            background: #f8f9fa;
        }

        /* Font size using vw without limits - will be huge on wide screens */
        h1 {
            font-size: 5vw;  /* No max limit */
        }

        p {
            font-size: 2vw;  /* Will be unreadable on mobile */
        }
    """

    viewport_broken_content = """
    <section class="hero">
        <div>
            <h1>Broken Viewport Units</h1>
            <p>This layout uses viewport units incorrectly, causing issues on mobile devices.</p>
        </div>
    </section>

    <section class="section">
        <div>
            <h2 style="font-size: 4vw;">Section with Bad Sizing</h2>
            <p>The text size scales poorly with viewport width, becoming too small on mobile and too large on desktop.</p>
        </div>
    </section>
    """

    with open(category_dir / "viewport_units_broken.html", "w") as f:
        f.write(generate_html("Viewport Units Test (Broken)", viewport_broken_styles, viewport_broken_content))

    # Fluid typography (good)
    fluid_typography_styles = """
        /* Fluid typography with clamp() */
        h1 {
            font-size: clamp(1.5rem, 4vw, 3rem);
            line-height: 1.2;
        }

        h2 {
            font-size: clamp(1.25rem, 3vw, 2rem);
            line-height: 1.3;
        }

        p {
            font-size: clamp(1rem, 2vw, 1.25rem);
            line-height: 1.6;
            max-width: 65ch;
            margin: 0 auto;
        }

        .container {
            padding: clamp(1rem, 5vw, 3rem);
        }

        .hero {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: clamp(2rem, 10vw, 6rem) 1rem;
        }

        .content {
            padding: 2rem 1rem;
            max-width: 1200px;
            margin: 0 auto;
        }
    """

    fluid_typography_content = """
    <header class="hero">
        <h1>Fluid Typography Example</h1>
        <p>This text scales smoothly between minimum and maximum sizes using CSS clamp().</p>
    </header>

    <main class="content">
        <h2>Responsive Text Scaling</h2>
        <p>The typography on this page uses fluid sizing with clamp() to ensure text is always readable, regardless of screen size. It sets minimum and maximum boundaries while scaling smoothly in between.</p>

        <h2>Benefits of Fluid Typography</h2>
        <p>Text remains proportional and readable across all devices. No jarring jumps at breakpoints. The reading experience is optimized for every screen size.</p>
    </main>
    """

    with open(category_dir / "fluid_typography_good.html", "w") as f:
        f.write(generate_html("Fluid Typography Test", fluid_typography_styles, fluid_typography_content))

    print(f"✅ Generated {len(list(category_dir.glob('*.html')))} responsive design test files")


def create_ui_components_tests():
    """Generate UI component test files."""
    category_dir = TEST_DATA_DIR / "ui_components"
    category_dir.mkdir(parents=True, exist_ok=True)

    # Well-designed form
    form_good_styles = """
        .form-container {
            max-width: 600px;
            margin: 2rem auto;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: #333;
        }

        input[type="text"],
        input[type="email"],
        input[type="tel"],
        select,
        textarea {
            width: 100%;
            padding: 0.75rem;
            font-size: 1rem;
            border: 2px solid #e0e0e0;
            border-radius: 4px;
            transition: border-color 0.3s;
        }

        input:focus,
        select:focus,
        textarea:focus {
            border-color: #3498db;
            outline: none;
        }

        .error {
            color: #e74c3c;
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }

        .help-text {
            color: #666;
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }

        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .submit-btn {
            background: #3498db;
            color: white;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .submit-btn:hover {
            background: #2980b9;
        }

        .submit-btn:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }

        .required::after {
            content: " *";
            color: #e74c3c;
        }
    """

    form_good_content = """
    <div class="form-container">
        <form>
            <h1>Contact Form</h1>
            <p>Fields marked with * are required</p>

            <div class="form-group">
                <label for="name" class="required">Full Name</label>
                <input type="text" id="name" name="name" required aria-required="true"
                       aria-describedby="name-help">
                <span id="name-help" class="help-text">Enter your first and last name</span>
            </div>

            <div class="form-group">
                <label for="email" class="required">Email Address</label>
                <input type="email" id="email" name="email" required aria-required="true"
                       aria-describedby="email-error" aria-invalid="false">
                <span id="email-error" class="error" role="alert" style="display:none;">
                    Please enter a valid email address
                </span>
            </div>

            <div class="form-group">
                <label for="phone">Phone Number</label>
                <input type="tel" id="phone" name="phone"
                       pattern="[0-9]{3}-[0-9]{3}-[0-9]{4}"
                       aria-describedby="phone-help">
                <span id="phone-help" class="help-text">Format: 123-456-7890</span>
            </div>

            <div class="form-group">
                <label for="subject">Subject</label>
                <select id="subject" name="subject">
                    <option value="">Select a subject</option>
                    <option value="general">General Inquiry</option>
                    <option value="support">Technical Support</option>
                    <option value="billing">Billing Question</option>
                    <option value="feedback">Feedback</option>
                </select>
            </div>

            <div class="form-group">
                <label for="message" class="required">Message</label>
                <textarea id="message" name="message" rows="5" required
                          aria-required="true"></textarea>
            </div>

            <div class="form-group">
                <div class="checkbox-group">
                    <input type="checkbox" id="newsletter" name="newsletter">
                    <label for="newsletter">Subscribe to our newsletter</label>
                </div>
            </div>

            <button type="submit" class="submit-btn">Send Message</button>
        </form>
    </div>
    """

    with open(category_dir / "form_well_designed.html", "w") as f:
        f.write(generate_html("Well-Designed Form Test", form_good_styles, form_good_content))

    print(f"✅ Generated {len(list(category_dir.glob('*.html')))} UI component test files")


def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        TEMPLATES_DIR,
        TEST_DATA_DIR,
        ANSWER_KEYS_DIR,
        TEST_DATA_DIR / "layout_alignment",
        TEST_DATA_DIR / "accessibility",
        TEST_DATA_DIR / "responsive_design",
        TEST_DATA_DIR / "ui_components",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def main():
    """Main function to generate all benchmark test files using multiple templates."""
    print("\n" + "=" * 60)
    print("🚀 LayoutLens Multi-Template Benchmark Generator v2.0")
    print("=" * 60 + "\n")

    # Ensure directories exist
    ensure_directories()

    # Check if templates exist
    missing_templates = []
    for template_file, template_type in TEMPLATES:
        template_path = TEMPLATES_DIR / template_file
        if not template_path.exists():
            missing_templates.append(f"   {template_file} ({template_type})")

    if missing_templates:
        print("❌ Error: Missing template files:")
        for template in missing_templates:
            print(template)
        return 1

    print(f"📋 Using {len(TEMPLATES)} templates:")
    for template_file, template_type in TEMPLATES:
        print(f"   ✅ {template_type} ({template_file})")

    # Generate test files for each category
    print("\n📝 Generating test files with template variety...\n")

    create_layout_alignment_tests()
    create_accessibility_tests()
    create_responsive_tests()
    create_ui_components_tests()

    # Count total files generated by category
    categories = ["layout_alignment", "accessibility", "responsive_design", "ui_components"]
    category_counts = {}
    total_files = 0

    for category in categories:
        if (TEST_DATA_DIR / category).exists():
            count = len(list((TEST_DATA_DIR / category).glob("*.html")))
            category_counts[category] = count
            total_files += count

    print("\n" + "=" * 60)
    print(f"✨ Successfully generated {total_files} test files across {len(TEMPLATES)} templates!")
    print("=" * 60)

    print("\n📊 Files by category:")
    for category, count in category_counts.items():
        print(f"   📂 {category.replace('_', ' ').title()}: {count} files")

    print(f"\n📁 Test files created in:")
    print(f"   {TEST_DATA_DIR}")

    print("\n🎯 Template distribution ensures LayoutLens is tested on:")
    print("   • Modern design systems")
    print("   • Bootstrap-style frameworks")
    print("   • Dense, information-heavy layouts")
    print("   • Visual-rich, image-heavy designs")
    print("   • Minimal, unstyled HTML")

    print("\n📈 Next steps:")
    print("   1. Run LayoutLens on the generated test files")
    print("   2. Use evaluation/evaluator.py to check results")
    print("   3. Compare accuracy across different template styles")
    print("   4. Update answer keys if needed for template variations")

    return 0


if __name__ == "__main__":
    exit(main())
