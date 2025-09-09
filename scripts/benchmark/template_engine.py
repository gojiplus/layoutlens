"""HTML template generation system for systematic UI testing.

This module provides parameterized HTML templates for generating
test cases covering various UI patterns, layouts, and visual elements.
"""

from __future__ import annotations

from typing import Dict, Any, Optional


class TemplateEngine:
    """Generates HTML templates for UI testing scenarios.
    
    This class provides methods to create HTML content for testing
    various UI patterns including text formatting, layouts, themes,
    responsive design, and accessibility features.
    """
    
    def __init__(self):
        """Initialize the template engine."""
        self.base_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        {styles}
    </style>
</head>
<body>
    {body}
</body>
</html>"""
    
    def render_text_alignment(self, alignment: str) -> str:
        """Generate HTML for text alignment testing.
        
        Parameters
        ----------
        alignment : str
            Text alignment: left, center, right, justify
            
        Returns
        -------
        str
            Complete HTML document with aligned text
        """
        styles = f"""
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }}
        
        #main_text {{
            text-align: {alignment};
            padding: 20px;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            line-height: 1.6;
            max-width: 600px;
            margin: 0 auto;
        }}
        """
        
        body = """
        <div id="main_text">
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
        </div>
        """
        
        return self.base_template.format(
            title=f"Text Alignment - {alignment.title()}",
            styles=styles,
            body=body
        )
    
    def render_text_style(self, style_name: str, css_property: str) -> str:
        """Generate HTML for text styling testing.
        
        Parameters
        ----------
        style_name : str
            Name of the style (bold, italic, underline, etc.)
        css_property : str
            CSS property to apply
            
        Returns
        -------
        str
            Complete HTML document with styled text
        """
        styles = f"""
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
            text-align: center;
        }}
        
        #styled_text {{
            {css_property};
            font-size: 24px;
            padding: 30px;
            background-color: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            display: inline-block;
            margin: 20px;
        }}
        """
        
        body = f"""
        <h1>Text Style Test: {style_name.title()}</h1>
        <div id="styled_text">
            This text demonstrates {style_name} formatting.
        </div>
        """
        
        return self.base_template.format(
            title=f"Text Style - {style_name.title()}",
            styles=styles,
            body=body
        )
    
    def render_flexbox_layout(self, pattern_name: str, flex_direction: str) -> str:
        """Generate HTML for flexbox layout testing.
        
        Parameters
        ----------
        pattern_name : str
            Name of the flexbox pattern
        flex_direction : str
            CSS flex-direction property
            
        Returns
        -------
        str
            Complete HTML document with flexbox layout
        """
        styles = f"""
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }}
        
        #flex_container {{
            display: flex;
            {flex_direction};
            gap: 20px;
            padding: 20px;
            background-color: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            min-height: 300px;
        }}
        
        .flex_item {{
            background-color: #007bff;
            color: white;
            padding: 20px;
            border-radius: 4px;
            text-align: center;
            font-weight: bold;
            flex: 1;
            min-width: 100px;
        }}
        
        .flex_item:nth-child(2) {{
            background-color: #28a745;
        }}
        
        .flex_item:nth-child(3) {{
            background-color: #dc3545;
        }}
        """
        
        body = f"""
        <h1>Flexbox Layout: {pattern_name.replace('_', ' ').title()}</h1>
        <div id="flex_container">
            <div class="flex_item">Item 1</div>
            <div class="flex_item">Item 2</div>
            <div class="flex_item">Item 3</div>
        </div>
        """
        
        return self.base_template.format(
            title=f"Flexbox - {pattern_name.replace('_', ' ').title()}",
            styles=styles,
            body=body
        )
    
    def render_grid_layout(self, pattern_name: str, grid_template: str) -> str:
        """Generate HTML for CSS Grid layout testing.
        
        Parameters
        ----------
        pattern_name : str
            Name of the grid pattern
        grid_template : str
            CSS grid-template-columns property
            
        Returns
        -------
        str
            Complete HTML document with grid layout
        """
        styles = f"""
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }}
        
        #grid_container {{
            display: grid;
            {grid_template};
            gap: 20px;
            padding: 20px;
            background-color: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            min-height: 300px;
        }}
        
        .grid_item {{
            background-color: #6f42c1;
            color: white;
            padding: 20px;
            border-radius: 4px;
            text-align: center;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .grid_item:nth-child(even) {{
            background-color: #fd7e14;
        }}
        """
        
        items_count = 3 if "three" in pattern_name else 2
        if "asymmetric" in pattern_name:
            items_count = 3
            
        items = "".join([
            f'<div class="grid_item">Grid Item {i+1}</div>'
            for i in range(items_count)
        ])
        
        body = f"""
        <h1>Grid Layout: {pattern_name.replace('_', ' ').title()}</h1>
        <div id="grid_container">
            {items}
        </div>
        """
        
        return self.base_template.format(
            title=f"Grid - {pattern_name.replace('_', ' ').title()}",
            styles=styles,
            body=body
        )
    
    def render_themed_page(self, theme_name: str, colors: Dict[str, str]) -> str:
        """Generate HTML for color theme testing.
        
        Parameters
        ----------
        theme_name : str
            Name of the color theme
        colors : Dict[str, str]
            Color palette with bg, text, and accent colors
            
        Returns
        -------
        str
            Complete HTML document with themed content
        """
        styles = f"""
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 40px;
            background-color: {colors['bg']};
            color: {colors['text']};
            min-height: 100vh;
        }}
        
        #page_content {{
            max-width: 800px;
            margin: 0 auto;
        }}
        
        .header {{
            background-color: {colors['accent']};
            color: {colors['bg']};
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .content_section {{
            background-color: {colors['bg']};
            border: 2px solid {colors['accent']};
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        
        .accent_text {{
            color: {colors['accent']};
            font-weight: bold;
        }}
        
        .button {{
            background-color: {colors['accent']};
            color: {colors['bg']};
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px 5px;
        }}
        """
        
        body = f"""
        <div id="page_content">
            <div class="header">
                <h1>{theme_name.replace('_', ' ').title()} Theme</h1>
                <p>Testing color scheme and visual consistency</p>
            </div>
            
            <div class="content_section">
                <h2>Content Section</h2>
                <p>This is a paragraph of text in the <span class="accent_text">{theme_name}</span> theme. 
                The color palette includes background, text, and accent colors that should work together 
                harmoniously to create a cohesive visual experience.</p>
                
                <button class="button">Primary Button</button>
                <button class="button">Secondary Button</button>
            </div>
            
            <div class="content_section">
                <h3>Theme Properties</h3>
                <ul>
                    <li>Background: {colors['bg']}</li>
                    <li>Text: {colors['text']}</li>
                    <li>Accent: {colors['accent']}</li>
                </ul>
            </div>
        </div>
        """
        
        return self.base_template.format(
            title=f"{theme_name.replace('_', ' ').title()} Theme",
            styles=styles,
            body=body
        )
    
    def render_responsive_layout(self, device_name: str, width: int, height: int) -> str:
        """Generate HTML for responsive design testing.
        
        Parameters
        ----------
        device_name : str
            Target device name (mobile, tablet, desktop, wide)
        width : int
            Viewport width in pixels
        height : int
            Viewport height in pixels
            
        Returns
        -------
        str
            Complete HTML document optimized for the target device
        """
        # Determine layout based on device
        if device_name == "mobile":
            flex_direction = "column"
            nav_display = "block"
            sidebar_width = "100%"
        elif device_name == "tablet":
            flex_direction = "column"
            nav_display = "flex"
            sidebar_width = "100%"
        else:  # desktop and wide
            flex_direction = "row"
            nav_display = "flex"
            sidebar_width = "250px"
        
        styles = f"""
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        
        #responsive_container {{
            display: flex;
            flex-direction: {flex_direction};
            min-height: 100vh;
        }}
        
        .header {{
            background-color: #343a40;
            color: white;
            padding: 15px 20px;
            order: -1;
        }}
        
        .nav {{
            display: {nav_display};
            gap: 20px;
            margin-top: 10px;
        }}
        
        .nav a {{
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
        }}
        
        .nav a:hover {{
            background-color: rgba(255,255,255,0.1);
        }}
        
        .sidebar {{
            background-color: #e9ecef;
            padding: 20px;
            width: {sidebar_width};
            {"flex-shrink: 0;" if device_name not in ["mobile", "tablet"] else ""}
        }}
        
        .main_content {{
            flex: 1;
            padding: 30px;
            background-color: white;
        }}
        
        .content_grid {{
            display: grid;
            grid-template-columns: {"1fr" if device_name == "mobile" else "repeat(auto-fit, minmax(250px, 1fr))"};
            gap: 20px;
            margin-top: 20px;
        }}
        
        .card {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
        }}
        
        @media (max-width: 768px) {{
            .nav {{
                flex-direction: column;
                gap: 10px;
            }}
            
            .content_grid {{
                grid-template-columns: 1fr;
            }}
        }}
        """
        
        body = f"""
        <div id="responsive_container">
            <div class="header">
                <h1>Responsive Layout - {device_name.title()}</h1>
                <div class="nav">
                    <a href="#">Home</a>
                    <a href="#">Products</a>
                    <a href="#">About</a>
                    <a href="#">Contact</a>
                </div>
            </div>
            
            {"" if device_name == "mobile" else '''
            <div class="sidebar">
                <h3>Sidebar</h3>
                <ul>
                    <li>Category 1</li>
                    <li>Category 2</li>
                    <li>Category 3</li>
                    <li>Category 4</li>
                </ul>
            </div>
            '''}
            
            <div class="main_content">
                <h2>Main Content Area</h2>
                <p>This layout is optimized for <strong>{device_name}</strong> devices with a viewport of {width}x{height} pixels.</p>
                
                <div class="content_grid">
                    <div class="card">
                        <h3>Card 1</h3>
                        <p>Content adapts to different screen sizes using responsive design principles.</p>
                    </div>
                    <div class="card">
                        <h3>Card 2</h3>
                        <p>Grid layout adjusts column count based on available space.</p>
                    </div>
                    <div class="card">
                        <h3>Card 3</h3>
                        <p>Typography and spacing scale appropriately for readability.</p>
                    </div>
                </div>
            </div>
        </div>
        """
        
        return self.base_template.format(
            title=f"Responsive - {device_name.title()}",
            styles=styles,
            body=body
        )
    
    def render_accessibility_pattern(self, pattern_name: str) -> str:
        """Generate HTML for accessibility feature testing.
        
        Parameters
        ----------
        pattern_name : str
            Accessibility pattern name
            
        Returns
        -------
        str
            Complete HTML document with accessibility features
        """
        if pattern_name == "focus_visible":
            return self._render_focus_patterns()
        elif pattern_name == "high_contrast":
            return self._render_high_contrast()
        elif pattern_name == "aria_labels":
            return self._render_aria_labels()
        elif pattern_name == "semantic_markup":
            return self._render_semantic_markup()
        else:
            return self._render_basic_accessibility()
    
    def _render_focus_patterns(self) -> str:
        """Generate HTML for focus indicator testing."""
        styles = """
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }
        
        #accessible_content {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
        }
        
        .focusable {
            margin: 15px 0;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 4px;
            background-color: #f8f9fa;
        }
        
        .focusable:focus {
            outline: 3px solid #007bff;
            outline-offset: 2px;
            border-color: #007bff;
            background-color: #e3f2fd;
        }
        
        button:focus {
            outline: 3px solid #28a745;
            outline-offset: 2px;
        }
        """
        
        body = """
        <div id="accessible_content">
            <h1>Focus Indicator Test</h1>
            <p>Use Tab key to navigate through focusable elements.</p>
            
            <input type="text" class="focusable" placeholder="Text input with focus indicator" />
            <textarea class="focusable" placeholder="Textarea with focus indicator"></textarea>
            <button class="focusable">Button with focus indicator</button>
            <a href="#" class="focusable">Link with focus indicator</a>
            
            <div tabindex="0" class="focusable">
                Custom focusable element with tabindex
            </div>
        </div>
        """
        
        return self.base_template.format(
            title="Accessibility - Focus Indicators",
            styles=styles,
            body=body
        )
    
    def _render_high_contrast(self) -> str:
        """Generate HTML for color contrast testing."""
        styles = """
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #000000;
            color: #ffffff;
        }
        
        #accessible_content {
            max-width: 600px;
            margin: 0 auto;
            background-color: #000000;
            padding: 30px;
            border: 2px solid #ffffff;
            border-radius: 8px;
        }
        
        .high_contrast_section {
            background-color: #ffffff;
            color: #000000;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        
        .warning_text {
            background-color: #ffff00;
            color: #000000;
            padding: 15px;
            font-weight: bold;
            border-radius: 4px;
        }
        
        .error_text {
            background-color: #ff0000;
            color: #ffffff;
            padding: 15px;
            font-weight: bold;
            border-radius: 4px;
        }
        """
        
        body = """
        <div id="accessible_content">
            <h1>High Contrast Theme Test</h1>
            <p>This page demonstrates high contrast color combinations for accessibility.</p>
            
            <div class="high_contrast_section">
                <h2>White Background Section</h2>
                <p>Black text on white background provides maximum contrast ratio.</p>
            </div>
            
            <div class="warning_text">
                Warning: Yellow background with black text for alerts.
            </div>
            
            <div class="error_text">
                Error: Red background with white text for critical messages.
            </div>
        </div>
        """
        
        return self.base_template.format(
            title="Accessibility - High Contrast",
            styles=styles,
            body=body
        )
    
    def _render_aria_labels(self) -> str:
        """Generate HTML for ARIA labels testing."""
        styles = """
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }
        
        #accessible_content {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
        }
        
        .form_group {
            margin: 20px 0;
        }
        
        label {
            display: block;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        """
        
        body = """
        <div id="accessible_content">
            <h1>ARIA Labels Test</h1>
            <form aria-label="Contact form with ARIA labels">
                <div class="form_group">
                    <label for="name_input">Full Name</label>
                    <input 
                        type="text" 
                        id="name_input" 
                        aria-label="Enter your full name"
                        aria-required="true"
                        placeholder="John Doe" 
                    />
                </div>
                
                <div class="form_group">
                    <label for="email_input">Email Address</label>
                    <input 
                        type="email" 
                        id="email_input" 
                        aria-label="Enter your email address"
                        aria-required="true"
                        aria-describedby="email_help"
                        placeholder="john@example.com" 
                    />
                    <small id="email_help">We'll never share your email with anyone else.</small>
                </div>
                
                <div class="form_group">
                    <label for="country_select">Country</label>
                    <select id="country_select" aria-label="Select your country">
                        <option value="">Choose a country</option>
                        <option value="us">United States</option>
                        <option value="ca">Canada</option>
                        <option value="uk">United Kingdom</option>
                    </select>
                </div>
                
                <div class="form_group">
                    <label for="message_textarea">Message</label>
                    <textarea 
                        id="message_textarea" 
                        aria-label="Enter your message"
                        rows="4"
                        placeholder="Your message here..."
                    ></textarea>
                </div>
                
                <button type="submit" aria-label="Submit contact form">
                    Send Message
                </button>
            </form>
        </div>
        """
        
        return self.base_template.format(
            title="Accessibility - ARIA Labels",
            styles=styles,
            body=body
        )
    
    def _render_semantic_markup(self) -> str:
        """Generate HTML for semantic markup testing."""
        styles = """
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }
        
        #accessible_content {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
        }
        
        header {
            background-color: #343a40;
            color: white;
            padding: 20px;
        }
        
        nav ul {
            list-style: none;
            padding: 0;
            display: flex;
            gap: 20px;
        }
        
        nav a {
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
        }
        
        main {
            padding: 30px;
        }
        
        aside {
            background-color: #f8f9fa;
            padding: 20px;
            margin: 20px 0;
            border-left: 4px solid #007bff;
        }
        
        footer {
            background-color: #e9ecef;
            padding: 20px;
            text-align: center;
            color: #6c757d;
        }
        """
        
        body = """
        <div id="accessible_content">
            <header>
                <h1>Semantic HTML Structure</h1>
                <nav aria-label="Main navigation">
                    <ul>
                        <li><a href="#home">Home</a></li>
                        <li><a href="#about">About</a></li>
                        <li><a href="#services">Services</a></li>
                        <li><a href="#contact">Contact</a></li>
                    </ul>
                </nav>
            </header>
            
            <main>
                <article>
                    <header>
                        <h2>Article Title</h2>
                        <p><time datetime="2024-01-01">January 1, 2024</time> by <span>Author Name</span></p>
                    </header>
                    
                    <section>
                        <h3>Section Heading</h3>
                        <p>This page demonstrates proper semantic HTML structure using elements like header, nav, main, article, section, aside, and footer.</p>
                    </section>
                    
                    <section>
                        <h3>Another Section</h3>
                        <p>Semantic markup helps screen readers and other assistive technologies understand the structure and meaning of content.</p>
                    </section>
                </article>
                
                <aside>
                    <h4>Related Information</h4>
                    <p>This is sidebar content that provides additional context or related information.</p>
                </aside>
            </main>
            
            <footer>
                <p>&copy; 2024 Semantic HTML Example. All rights reserved.</p>
            </footer>
        </div>
        """
        
        return self.base_template.format(
            title="Accessibility - Semantic Markup",
            styles=styles,
            body=body
        )
    
    def _render_basic_accessibility(self) -> str:
        """Generate basic accessibility test HTML."""
        return self._render_focus_patterns()