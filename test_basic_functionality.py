#!/usr/bin/env python3
"""
Basic functionality test for LayoutLens
Tests core functionality without requiring external dependencies
"""
import sys
import os
sys.path.insert(0, '.')

def test_imports():
    """Test that we can import core modules."""
    print("Testing imports...")
    
    try:
        # Test basic module structure
        import layoutlens
        print(f"✓ LayoutLens package imports (version {layoutlens.__version__})")
        
        # Test core classes
        from layoutlens import LayoutLens, Config, TestSuite, TestRunner
        print("✓ Core classes import successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False

def test_config_creation():
    """Test configuration creation and basic functionality."""
    print("\nTesting configuration...")
    
    try:
        from layoutlens import Config
        
        # Test default config creation
        config = Config()
        print("✓ Default config created")
        
        # Test config properties
        assert hasattr(config, 'llm')
        assert hasattr(config, 'screenshots') 
        assert hasattr(config, 'testing')
        assert hasattr(config, 'output')
        print("✓ Config has expected sections")
        
        # Test default values
        assert config.llm.model == "gpt-4o-mini"
        assert config.testing.parallel == True
        print("✓ Default values are correct")
        
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_test_suite_creation():
    """Test TestSuite creation."""
    print("\nTesting TestSuite...")
    
    try:
        from layoutlens import TestSuite, TestCase
        
        # Create test suite
        suite = TestSuite(
            name="Test Suite",
            description="Basic test suite"
        )
        print("✓ TestSuite created")
        
        # Add test case
        test_case = TestCase(
            name="Homepage Test",
            html_path="test.html",
            queries=["Is the layout good?"]
        )
        suite.add_test_case(test_case)
        print("✓ TestCase added to suite")
        
        assert len(suite.test_cases) == 1
        assert suite.test_cases[0].name == "Homepage Test"
        print("✓ TestSuite functionality works")
        
        return True
    except Exception as e:
        print(f"✗ TestSuite test failed: {e}")
        return False

def test_directory_structure():
    """Test that expected files and directories exist."""
    print("\nTesting directory structure...")
    
    expected_files = [
        'layoutlens/__init__.py',
        'layoutlens/core.py',
        'layoutlens/config.py',
        'layoutlens/test_runner.py',
        'layoutlens/cli.py',
        'scripts/testing/__init__.py',
        'scripts/benchmark/__init__.py',
        'pyproject.toml',
        'README.md',
        'CHANGELOG.md',
        'LICENSE'
    ]
    
    expected_dirs = [
        'layoutlens',
        'scripts',
        'scripts/testing', 
        'scripts/benchmark',
        'docs',
        'docs/user-guide',
        'docs/api',
        'examples',
        'tests',
        'benchmarks'
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file_path in expected_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    for dir_path in expected_dirs:
        if not os.path.isdir(dir_path):
            missing_dirs.append(dir_path)
    
    if missing_files:
        print(f"✗ Missing files: {missing_files}")
        return False
    else:
        print("✓ All expected files present")
    
    if missing_dirs:
        print(f"✗ Missing directories: {missing_dirs}")
        return False
    else:
        print("✓ All expected directories present")
    
    return True

def test_examples_syntax():
    """Test that example files have valid Python syntax."""
    print("\nTesting example files...")
    
    import glob
    import py_compile
    
    python_files = glob.glob("examples/*.py")
    
    for py_file in python_files:
        try:
            py_compile.compile(py_file, doraise=True)
            print(f"✓ {py_file} has valid syntax")
        except py_compile.PyCompileError as e:
            print(f"✗ {py_file} syntax error: {e}")
            return False
    
    return True

def run_all_tests():
    """Run all basic functionality tests."""
    print("=" * 60)
    print("LAYOUTLENS BASIC FUNCTIONALITY TEST")
    print("=" * 60)
    
    tests = [
        test_directory_structure,
        test_imports,
        test_config_creation,
        test_test_suite_creation,
        test_examples_syntax
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    if passed == total:
        print("🎉 ALL TESTS PASSED! LayoutLens is ready for use.")
    else:
        print("❌ Some tests failed. Please check the output above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)