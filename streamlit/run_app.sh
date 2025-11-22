#!/bin/bash

# LayoutLens Streamlit App Launch Script

echo "🔍 Starting LayoutLens Streamlit App..."

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "💡 Note: No OPENAI_API_KEY environment variable detected"
    echo "   You can enter your API key directly in the app sidebar"
    echo "   Or set it with: export OPENAI_API_KEY='your-key-here'"
    echo ""
else
    echo "✅ OpenAI API key found in environment"
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit is not installed."
    echo "   Please install it with: pip install streamlit validators"
    exit 1
fi

# Check if LayoutLens is available
python3 -c "import layoutlens" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ LayoutLens is not available."
    echo "   Please install it with: pip install -e ."
    echo "   (from the main LayoutLens directory)"
    exit 1
fi

echo "✅ All dependencies check passed!"
echo ""
echo "🚀 Launching Streamlit app..."
echo "   The app will open in your browser shortly"
echo "   Press Ctrl+C to stop the server"
echo ""

# Launch the app
streamlit run streamlit_app.py
