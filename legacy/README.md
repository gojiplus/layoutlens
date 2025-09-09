# Legacy Components

This directory contains the original LayoutLens components that were the foundation for the current framework. These files are preserved for backward compatibility and reference.

## Files

### Core Components
- **`framework.py`** - Original LayoutLens class implementation
- **`screenshot.py`** - Basic screenshot capture utilities  
- **`benchmark_runner.py`** - Original benchmark execution system

### Evaluation and Generation
- **`eval.py`** - Legacy evaluation script (uses older OpenAI API patterns)
- **`gen_benchmark.py`** - Original benchmark generation script

## Migration Notes

The legacy components have been superseded by the enhanced framework:

### From Legacy to New Framework

```python
# Legacy usage
from framework import LayoutLens
lens = LayoutLens(api_key="key")
result = lens.ask(["image.png"], "Question?")

# New framework usage  
from layoutlens import LayoutLens
tester = LayoutLens(api_key="key")
result = tester.test_page("page.html", queries=["Question?"])
```

### Key Improvements

1. **Enhanced API**: More user-friendly methods and configuration
2. **Advanced Screenshots**: Multi-viewport, responsive design testing
3. **Intelligent Queries**: Auto-generated test questions from DOM analysis
4. **Test Suites**: Organized testing workflows
5. **CI/CD Integration**: Built-in pipeline support
6. **CLI Interface**: Command-line tools for easy usage

## Backward Compatibility

The new `LayoutLens` class maintains backward compatibility with the original `ask()` and `compare_layouts()` methods, so existing code using the legacy interface should continue to work.

## Deprecation Timeline

- **v1.x**: Legacy components available alongside new framework
- **v2.x**: Legacy components marked as deprecated  
- **v3.x**: Legacy components removed (planned)

For new projects, use the enhanced framework in the `layoutlens/` package rather than these legacy components.