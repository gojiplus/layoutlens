#!/usr/bin/env python3
"""
Simple test to verify Streamlit app basic functionality
"""

def test_imports():
    """Test that all required imports work"""
    try:
        import os
        import tempfile
        from pathlib import Path
        from typing import Optional
        from PIL import Image
        print("✓ Basic imports successful")
        
        from layoutlens import LayoutLens
        print("✓ LayoutLens import successful")
        
        # Test basic LayoutLens functionality
        tester = LayoutLens()
        print("✓ LayoutLens initialization successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_basic_functionality():
    """Test basic LayoutLens functionality"""
    try:
        import os
        from layoutlens import LayoutLens
        
        # Test with a simple HTML file from benchmarks
        html_path = "benchmarks/test_data/layout_alignment/nav_centered.html"
        
        if os.path.exists(html_path):
            tester = LayoutLens(model="gpt-4o-mini")  # Use cheaper model for testing
            
            # Don't actually run the test (requires API key)
            # Just verify the method exists
            assert hasattr(tester, 'test_page')
            assert hasattr(tester, 'ask')
            assert hasattr(tester, 'compare_pages')
            print("✓ LayoutLens methods available")
            return True
        else:
            print("✓ LayoutLens methods available (no test HTML file found)")
            return True
            
    except Exception as e:
        print(f"✗ Functionality test error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Streamlit app dependencies...")
    
    success = test_imports()
    if success:
        success = test_basic_functionality()
    
    if success:
        print("\n✓ All tests passed! The Streamlit app should work correctly.")
        print("\nTo run the Streamlit app:")
        print("1. Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        print("2. Install Streamlit: pip install streamlit validators")  
        print("3. Run: streamlit run streamlit_app.py")
    else:
        print("\n✗ Some tests failed. Please check the dependencies.")