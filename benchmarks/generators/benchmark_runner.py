#!/usr/bin/env python3
"""Benchmark Runner - Generates all LayoutLens test data.

This script runs all benchmark generators to create a comprehensive
test suite with both positive and negative examples.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any
import argparse


def generate_layout_alignment_tests(output_dir: Path) -> List[str]:
    """Generate layout alignment test cases."""
    
    test_files = []
    
    # Navigation centering - GOOD example
    nav_good = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centered Navigation - Good Example</title>
    <style>
        .header { 
            background: #f0f0f0; 
            padding: 1rem; 
            text-align: center; 
        }
        .nav { 
            display: inline-block; 
            position: relative;
            left: 50%;
            transform: translateX(-50%); /* Perfect centering */
        }
        .nav a { 
            margin: 0 1rem; 
            text-decoration: none; 
            color: #333; 
        }
    </style>
</head>
<body>
    <header class="header">
        <nav class="nav">
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#services">Services</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Perfect Navigation Centering</h1>
        <p>This navigation is precisely centered using transform: translateX(-50%)</p>
    </main>
</body>
</html>"""
    
    # Navigation centering - BAD example (2% off)
    nav_bad = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Misaligned Navigation - Issue Example</title>
    <style>
        .header { 
            background: #f0f0f0; 
            padding: 1rem; 
            text-align: center; 
        }
        .nav { 
            display: inline-block; 
            position: relative;
            left: 52%; /* 2% off-center - subtle but wrong */
            transform: translateX(-50%);
        }
        .nav a { 
            margin: 0 1rem; 
            text-decoration: none; 
            color: #333; 
        }
    </style>
</head>
<body>
    <header class="header">
        <nav class="nav">
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#services">Services</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Misaligned Navigation</h1>
        <p>This navigation is 2% off-center (left: 52% instead of 50%)</p>
    </main>
</body>
</html>"""
    
    # Logo positioning - GOOD example
    logo_good = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Correct Logo Positioning</title>
    <style>
        .header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 1rem 2rem; 
            background: #fff;
            border-bottom: 1px solid #eee;
        }
        .logo { 
            font-size: 1.5rem; 
            font-weight: bold; 
            color: #2c3e50; 
            order: 0; /* Logo first (left side) */
        }
        .nav { 
            order: 1; /* Navigation second (right side) */
        }
        .nav a { 
            margin: 0 1rem; 
            text-decoration: none; 
            color: #333; 
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">CompanyLogo</div>
        <nav class="nav">
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Correct Logo Placement</h1>
        <p>Logo is correctly positioned on the left side following web conventions.</p>
    </main>
</body>
</html>"""
    
    # Logo positioning - BAD example
    logo_bad = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wrong Logo Positioning</title>
    <style>
        .header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 1rem 2rem; 
            background: #fff;
            border-bottom: 1px solid #eee;
        }
        .logo { 
            font-size: 1.5rem; 
            font-weight: bold; 
            color: #2c3e50; 
            order: 1; /* Logo second (right side) - WRONG! */
        }
        .nav { 
            order: 0; /* Navigation first (left side) - violates conventions */
        }
        .nav a { 
            margin: 0 1rem; 
            text-decoration: none; 
            color: #333; 
        }
    </style>
</head>
<body>
    <header class="header">
        <nav class="nav">
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
        </nav>
        <div class="logo">CompanyLogo</div>
    </header>
    <main>
        <h1>Incorrect Logo Placement</h1>
        <p>Logo is incorrectly positioned on the right side, violating web conventions.</p>
    </main>
</body>
</html>"""
    
    # Write test files
    files = [
        ("nav_centered.html", nav_good),
        ("nav_misaligned.html", nav_bad),
        ("logo_correct.html", logo_good),
        ("logo_wrong.html", logo_bad)
    ]
    
    for filename, content in files:
        file_path = output_dir / "layout_alignment" / filename
        file_path.write_text(content, encoding='utf-8')
        test_files.append(str(file_path))
        print(f"✓ Generated: {filename}")
    
    return test_files


def generate_accessibility_tests(output_dir: Path) -> List[str]:
    """Generate accessibility test cases."""
    
    test_files = []
    
    # WCAG compliant - GOOD example  
    wcag_good = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG Compliant Page</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            line-height: 1.6; 
            color: #212529; /* High contrast: 16.9:1 */ 
            background: #ffffff;
            margin: 2rem;
        }
        h1 { 
            color: #2c3e50; /* High contrast: 12.6:1 */ 
            margin-bottom: 1rem;
        }
        .form-group { margin: 1.5rem 0; }
        label { 
            display: block; 
            font-weight: bold; 
            margin-bottom: 0.5rem; 
            color: #2c3e50;
        }
        input[type="text"], input[type="email"] { 
            width: 100%; 
            padding: 0.75rem; 
            border: 2px solid #6c757d; 
            border-radius: 4px; 
            font-size: 1rem;
            min-height: 44px; /* WCAG touch target minimum */
        }
        input:focus { 
            outline: 3px solid #007bff; /* Clear focus indicator */
            outline-offset: 2px;
        }
        .btn { 
            background: #007bff; 
            color: white; 
            padding: 0.75rem 1.5rem; 
            border: none; 
            border-radius: 4px; 
            font-size: 1rem; 
            cursor: pointer;
            min-height: 44px; /* Touch target */
        }
        .btn:focus {
            outline: 3px solid #ffc107;
            outline-offset: 2px;
        }
        .skip-link {
            position: absolute;
            top: -40px;
            left: 6px;
            background: #000;
            color: #fff;
            padding: 8px;
            text-decoration: none;
            z-index: 1000;
        }
        .skip-link:focus {
            top: 6px;
        }
    </style>
</head>
<body>
    <a href="#main" class="skip-link">Skip to main content</a>
    
    <header>
        <h1>Accessible Contact Form</h1>
    </header>
    
    <main id="main">
        <form>
            <div class="form-group">
                <label for="name">Full Name (required)</label>
                <input type="text" id="name" name="name" required aria-describedby="name-help">
                <small id="name-help">Enter your first and last name</small>
            </div>
            
            <div class="form-group">
                <label for="email">Email Address (required)</label>
                <input type="email" id="email" name="email" required aria-describedby="email-help">
                <small id="email-help">We'll never share your email address</small>
            </div>
            
            <button type="submit" class="btn">Submit Form</button>
        </form>
    </main>
</body>
</html>"""
    
    # WCAG violations - BAD example
    wcag_bad = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG Violations Example</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            color: #999999; /* Poor contrast: 2.85:1 - VIOLATION */ 
            background: #ffffff;
            margin: 2rem;
        }
        h1 { 
            color: #cccccc; /* Very poor contrast: 1.61:1 - VIOLATION */ 
        }
        .form-group { margin: 1rem 0; }
        /* Missing label styles - VIOLATION */
        input[type="text"], input[type="email"] { 
            width: 100%; 
            padding: 4px; /* Too small - VIOLATION */
            border: 1px solid #ddd; 
            font-size: 12px; /* Too small for readability */
            height: 20px; /* Below 44px minimum - VIOLATION */
        }
        /* No focus styles - VIOLATION */
        .btn { 
            background: #e0e0e0; /* Poor contrast button - VIOLATION */
            color: #cccccc; /* Poor contrast text - VIOLATION */
            padding: 4px 8px; /* Too small - VIOLATION */
            border: none; 
            font-size: 10px; /* Too small */
            cursor: pointer;
            height: 24px; /* Below minimum touch target */
        }
        img { 
            width: 200px; 
            height: 150px; 
            /* No alt text will be provided - VIOLATION */
        }
    </style>
</head>
<body>
    <!-- No skip link - VIOLATION -->
    
    <!-- Improper heading hierarchy - VIOLATION -->
    <h3>Contact Form</h3> <!-- Should be h1 -->
    
    <form>
        <!-- Unlabeled form fields - VIOLATION -->
        <div class="form-group">
            <input type="text" name="name" placeholder="Name"> <!-- No label - VIOLATION -->
        </div>
        
        <div class="form-group">
            <input type="email" name="email" placeholder="Email"> <!-- No label - VIOLATION -->
        </div>
        
        <!-- Image without alt text - VIOLATION -->
        <img src="contact-image.jpg">
        
        <button type="submit" class="btn">Submit</button>
    </form>
</body>
</html>"""
    
    files = [
        ("wcag_compliant.html", wcag_good),
        ("wcag_violations.html", wcag_bad)
    ]
    
    for filename, content in files:
        file_path = output_dir / "accessibility" / filename
        file_path.write_text(content, encoding='utf-8')
        test_files.append(str(file_path))
        print(f"✓ Generated: {filename}")
    
    return test_files


def generate_responsive_tests(output_dir: Path) -> List[str]:
    """Generate responsive design test cases."""
    
    test_files = []
    
    # Mobile-friendly - GOOD example
    responsive_good = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobile-Friendly Responsive Design</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            line-height: 1.6;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 1rem; 
        }
        .header { 
            background: #2c3e50; 
            color: white; 
            padding: 1rem; 
        }
        .nav { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 1rem; 
        }
        .nav a { 
            color: white; 
            text-decoration: none; 
            padding: 0.5rem 1rem; 
            min-height: 44px; /* Touch-friendly */
            display: flex;
            align-items: center;
        }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 2rem; 
            margin: 2rem 0; 
        }
        .card { 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            padding: 1.5rem; 
            background: #f9f9f9; 
        }
        .btn { 
            background: #007bff; 
            color: white; 
            padding: 0.75rem 1.5rem; 
            border: none; 
            border-radius: 4px; 
            font-size: 1rem; 
            min-height: 44px; /* Touch target */
            width: 100%;
            cursor: pointer;
        }
        
        /* Mobile optimizations */
        @media (max-width: 768px) {
            .container { padding: 0.5rem; }
            .nav { 
                flex-direction: column; 
            }
            .nav a { 
                justify-content: center; 
                font-size: 1.1rem; /* Larger for mobile */
            }
            .grid { 
                grid-template-columns: 1fr; /* Single column */
                gap: 1rem; 
            }
            body { 
                font-size: 16px; /* Minimum for mobile readability */
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <h1>Responsive Design</h1>
            <nav class="nav">
                <a href="#home">Home</a>
                <a href="#about">About</a>
                <a href="#services">Services</a>
                <a href="#contact">Contact</a>
            </nav>
        </div>
    </header>
    
    <main class="container">
        <div class="grid">
            <div class="card">
                <h2>Service 1</h2>
                <p>This layout adapts perfectly to all screen sizes with proper touch targets.</p>
                <button class="btn">Learn More</button>
            </div>
            <div class="card">
                <h2>Service 2</h2>
                <p>Text remains readable and buttons stay touch-friendly on mobile devices.</p>
                <button class="btn">Learn More</button>
            </div>
            <div class="card">
                <h2>Service 3</h2>
                <p>Grid layout automatically adjusts from 3 columns to 1 column on mobile.</p>
                <button class="btn">Learn More</button>
            </div>
        </div>
    </main>
</body>
</html>"""
    
    # Mobile-broken - BAD example
    responsive_bad = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobile-Broken Responsive Design</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            font-size: 12px; /* Too small for mobile - VIOLATION */
        }
        .container { 
            width: 1200px; /* Fixed width causes horizontal scroll - VIOLATION */
            margin: 0 auto; 
            padding: 1rem; 
        }
        .header { 
            background: #2c3e50; 
            color: white; 
            padding: 1rem; 
            width: 100%;
        }
        .nav { 
            display: flex; 
            gap: 0.2rem; /* Too small gaps */
        }
        .nav a { 
            color: white; 
            text-decoration: none; 
            padding: 2px 4px; /* Tiny touch targets - VIOLATION */
            font-size: 10px; /* Too small */
            height: 20px; /* Below 44px minimum - VIOLATION */
        }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(3, 1fr); /* Never changes - VIOLATION */
            gap: 0.5rem; 
            margin: 2rem 0; 
        }
        .card { 
            border: 1px solid #ddd; 
            padding: 0.5rem; 
            background: #f9f9f9; 
            min-width: 300px; /* Causes overflow on mobile - VIOLATION */
        }
        .btn { 
            background: #007bff; 
            color: white; 
            padding: 2px 4px; /* Too small for touch - VIOLATION */
            border: none; 
            font-size: 8px; /* Unreadable on mobile */
            height: 16px; /* Too small - VIOLATION */
            cursor: pointer;
        }
        
        /* No mobile media queries - VIOLATION */
        /* Content will overflow and be unusable on mobile */
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <h1>Broken Mobile Design</h1>
            <nav class="nav">
                <a href="#home">Home</a>
                <a href="#about">About</a>
                <a href="#services">Services</a>
                <a href="#contact">Contact</a>
            </nav>
        </div>
    </header>
    
    <main class="container">
        <div class="grid">
            <div class="card">
                <h2>Service 1</h2>
                <p>This text is too small to read on mobile devices.</p>
                <button class="btn">Tiny Button</button>
            </div>
            <div class="card">
                <h2>Service 2</h2>
                <p>Fixed width layout causes horizontal scrolling on mobile.</p>
                <button class="btn">Too Small</button>
            </div>
            <div class="card">
                <h2>Service 3</h2>
                <p>Touch targets are too small to tap accurately on touch screens.</p>
                <button class="btn">Unusable</button>
            </div>
        </div>
    </main>
</body>
</html>"""
    
    files = [
        ("mobile_friendly.html", responsive_good),
        ("mobile_broken.html", responsive_bad)
    ]
    
    for filename, content in files:
        file_path = output_dir / "responsive_design" / filename
        file_path.write_text(content, encoding='utf-8')
        test_files.append(str(file_path))
        print(f"✓ Generated: {filename}")
    
    return test_files


def generate_ui_component_tests(output_dir: Path) -> List[str]:
    """Generate UI component test cases."""
    
    test_files = []
    
    # Well-designed form - GOOD example
    form_good = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Well-Designed Form</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            line-height: 1.6; 
            color: #333; 
            background: #f8f9fa;
            margin: 0;
            padding: 2rem;
        }
        .form-container { 
            max-width: 500px; 
            margin: 0 auto; 
            background: white; 
            padding: 2rem; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { 
            text-align: center; 
            color: #2c3e50; 
            margin-bottom: 2rem; 
        }
        .form-group { 
            margin-bottom: 1.5rem; 
        }
        label { 
            display: block; 
            font-weight: 600; 
            margin-bottom: 0.5rem; 
            color: #2c3e50; 
        }
        input, textarea, select { 
            width: 100%; 
            padding: 0.75rem; 
            border: 2px solid #e1e5e9; 
            border-radius: 4px; 
            font-size: 1rem; 
            transition: border-color 0.3s;
            min-height: 44px; /* Touch-friendly */
        }
        input:focus, textarea:focus, select:focus { 
            outline: none; 
            border-color: #007bff; 
            box-shadow: 0 0 0 3px rgba(0,123,255,0.25); 
        }
        .required { color: #dc3545; }
        .help-text { 
            font-size: 0.875rem; 
            color: #6c757d; 
            margin-top: 0.25rem; 
        }
        .btn-primary { 
            background: #007bff; 
            color: white; 
            padding: 0.75rem 2rem; 
            border: none; 
            border-radius: 4px; 
            font-size: 1.1rem; 
            font-weight: 600; 
            cursor: pointer; 
            width: 100%; 
            min-height: 48px;
            transition: background-color 0.3s;
        }
        .btn-primary:hover { 
            background: #0056b3; 
        }
        .btn-primary:focus {
            outline: 3px solid #ffc107;
            outline-offset: 2px;
        }
    </style>
</head>
<body>
    <div class="form-container">
        <h1>Contact Us</h1>
        <form>
            <div class="form-group">
                <label for="name">
                    Full Name <span class="required">*</span>
                </label>
                <input type="text" id="name" name="name" required>
                <div class="help-text">Enter your first and last name</div>
            </div>
            
            <div class="form-group">
                <label for="email">
                    Email Address <span class="required">*</span>
                </label>
                <input type="email" id="email" name="email" required>
                <div class="help-text">We'll never share your email</div>
            </div>
            
            <div class="form-group">
                <label for="subject">Subject</label>
                <select id="subject" name="subject">
                    <option value="">Select a topic</option>
                    <option value="support">Support</option>
                    <option value="sales">Sales</option>
                    <option value="other">Other</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="message">
                    Message <span class="required">*</span>
                </label>
                <textarea id="message" name="message" rows="5" required></textarea>
                <div class="help-text">Please provide details about your inquiry</div>
            </div>
            
            <button type="submit" class="btn-primary">Send Message</button>
        </form>
    </div>
</body>
</html>"""
    
    files = [
        ("form_well_designed.html", form_good)
    ]
    
    for filename, content in files:
        file_path = output_dir / "ui_components" / filename
        file_path.write_text(content, encoding='utf-8')
        test_files.append(str(file_path))
        print(f"✓ Generated: {filename}")
    
    return test_files


def main():
    """Main benchmark generation function."""
    parser = argparse.ArgumentParser(description="Generate LayoutLens benchmark test data")
    parser.add_argument("--output", "-o", default="benchmarks_new/test_data", 
                       help="Output directory for test files")
    
    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔧 Generating LayoutLens Benchmark Test Data")
    print("=" * 50)
    
    all_files = []
    
    # Generate each test category
    print("\\n📐 Generating layout alignment tests...")
    all_files.extend(generate_layout_alignment_tests(output_dir))
    
    print("\\n♿ Generating accessibility tests...")
    all_files.extend(generate_accessibility_tests(output_dir))
    
    print("\\n📱 Generating responsive design tests...")
    all_files.extend(generate_responsive_tests(output_dir))
    
    print("\\n🎨 Generating UI component tests...")
    all_files.extend(generate_ui_component_tests(output_dir))
    
    # Generate summary
    summary = {
        "generated": len(all_files),
        "categories": {
            "layout_alignment": 4,
            "accessibility": 2, 
            "responsive_design": 2,
            "ui_components": 1
        },
        "files": all_files
    }
    
    summary_file = output_dir.parent / "generation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\\n✅ Generated {len(all_files)} test files")
    print(f"📄 Summary saved to: {summary_file}")
    print("\\n🎯 Next steps:")
    print("  1. Run: python benchmarks_new/generators/answer_key_generator.py")
    print("  2. Run: python benchmarks_new/evaluation/evaluator.py")


if __name__ == "__main__":
    main()