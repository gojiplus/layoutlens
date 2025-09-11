# LayoutLens Streamlit Web App

A web interface for LayoutLens that allows users to upload screenshots or test URLs with natural language queries.

## Features

- **Screenshot Upload**: Upload PNG/JPEG images for analysis
- **URL Testing**: Enter any URL to capture and analyze
- **Custom Questions**: Ask specific questions about your UI
- **Auto-generated Questions**: Let AI generate relevant test questions
- **Multiple Viewports**: Test on desktop, mobile, and tablet viewports
- **Real-time Analysis**: Get instant AI-powered feedback

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run streamlit_app.py
```

2. Open your browser to the displayed URL (usually http://localhost:8501)

3. **Enter your OpenAI API key** in the sidebar (required for analysis)
   - The app will guide you on how to get one if needed
   - You can also set it as an environment variable: `export OPENAI_API_KEY="your-key"`

4. Choose your input method:
   - **Upload Screenshot**: Drag and drop an image file
   - **Enter URL**: Provide any website URL

5. Configure your analysis:
   - Choose the model (gpt-4o or gpt-4o-mini)  
   - Select viewport for URL testing

6. Add your questions:
   - **Custom Questions**: Write specific questions about your UI
   - **Auto-generate**: Let LayoutLens create relevant test questions

7. Click "🚀 Analyze UI" and view the results!

## Example Questions

- "Is the navigation menu properly aligned?"
- "Are there any accessibility issues visible?"
- "Does the layout work well on mobile devices?"
- "Are the colors and contrast appropriate?"
- "Is the typography readable and well-sized?"

## Testing

Run the test script to verify everything works:

```bash
python test_streamlit.py
```

## Configuration

### API Keys
- Set `OPENAI_API_KEY` environment variable or enter it in the sidebar
- The app will use gpt-4o-mini by default for cost efficiency

### Viewports
Available viewport options:
- **Desktop**: 1920x1080 
- **Mobile Portrait**: 375x667
- **Mobile Landscape**: 667x375  
- **Tablet**: 768x1024

## Architecture

The app integrates with the LayoutLens core library:
- Uses `LayoutLens.test_page()` for URL analysis
- Uses `LayoutLens.ask()` for direct screenshot analysis
- Supports all LayoutLens configuration options

## Troubleshooting

**Import Errors**: Make sure LayoutLens is installed (`pip install -e .` from the main directory)

**API Errors**: Verify your OpenAI API key is correct and has sufficient credits

**URL Issues**: Some websites may block automated access - try with simple HTML pages first

**Screenshot Analysis**: For uploaded images, the app uses direct image analysis rather than HTML page testing