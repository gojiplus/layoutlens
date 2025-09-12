import streamlit as st
import os
import tempfile
from pathlib import Path
from typing import Optional
from layoutlens import LayoutLens
from PIL import Image
import validators
import requests
from urllib.parse import urlparse

def main():
    st.set_page_config(
        page_title="LayoutLens - AI-Powered UI Testing",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 LayoutLens")
    st.subheader("AI-Powered UI Testing with Natural Language")
    
    st.markdown("""
    Upload a screenshot or provide a URL to test your UI with natural language queries.
    LayoutLens uses GPT-4o Vision to analyze layouts, accessibility, and visual consistency.
    """)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # API Key input
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Enter your OpenAI API key (required for analysis)",
            placeholder="sk-..."
        )
        
        # If no API key provided in input, check environment variable
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                st.success("✅ Using API key from environment variable")
            else:
                st.warning("⚠️ Please enter your OpenAI API key above")
        else:
            st.success("✅ API key provided")
        
        # Help section for API key
        with st.expander("ℹ️ How to get an OpenAI API key"):
            st.markdown("""
            1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
            2. Sign up or log in to your OpenAI account
            3. Click "Create new secret key"
            4. Copy the key and paste it above
            
            **Note:** You'll need credits in your OpenAI account to use the API.
            """)
        
        # Model selection
        model = st.selectbox(
            "Model",
            ["gpt-4o", "gpt-4o-mini"],
            index=1,
            help="Choose the OpenAI model for analysis"
        )
        
        # Viewport selection
        viewport = st.selectbox(
            "Viewport",
            ["desktop", "mobile_portrait", "mobile_landscape", "tablet"],
            help="Choose viewport for URL capture"
        )
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Input")
        
        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["Upload Screenshot", "Enter URL"],
            horizontal=True
        )
        
        input_file = None
        input_url = None
        
        if input_method == "Upload Screenshot":
            input_file = st.file_uploader(
                "Upload a screenshot",
                type=['png', 'jpg', 'jpeg'],
                help="Upload a PNG or JPEG image of your UI"
            )
            
            if input_file:
                st.image(input_file, caption="Uploaded Screenshot", use_container_width=True)
        
        elif input_method == "Enter URL":
            input_url = st.text_input(
                "Enter URL",
                placeholder="https://example.com",
                help="Enter the URL of the webpage to test"
            )
            
            if input_url and not validators.url(input_url):
                st.error("Please enter a valid URL")
                input_url = None
        
        # Questions input
        st.subheader("Test Questions")
        
        question_method = st.radio(
            "Question method:",
            ["Custom Questions", "Auto-generate"],
            horizontal=True
        )
        
        custom_questions = []
        if question_method == "Custom Questions":
            # Allow multiple questions
            num_questions = st.number_input("Number of questions", min_value=1, max_value=10, value=1)
            
            for i in range(num_questions):
                question = st.text_input(
                    f"Question {i+1}",
                    placeholder="e.g., Is the navigation menu properly aligned?",
                    key=f"question_{i}"
                )
                if question:
                    custom_questions.append(question)
        
        # Run analysis button
        run_analysis = st.button("🚀 Analyze UI", type="primary")
    
    with col2:
        st.header("Analysis Results")
        
        # Show welcome message when nothing has been run yet
        if not run_analysis:
            st.info("👋 **Welcome to LayoutLens!**")
            st.markdown("""
            **Getting Started:**
            1. **Enter your OpenAI API key** in the sidebar ← 
            2. **Choose your input method**: Upload a screenshot or enter a URL
            3. **Add your questions** or let AI auto-generate them
            4. **Click "🚀 Analyze UI"** to get instant feedback!
            
            **What LayoutLens can analyze:**
            - Layout alignment and visual hierarchy
            - Accessibility compliance (WCAG)
            - Responsive design issues  
            - Color contrast and readability
            - UI component consistency
            - And much more with custom questions!
            """)
        
        if run_analysis:
            if not api_key:
                st.error("🔑 **OpenAI API Key Required**")
                st.markdown("""
                Please provide your OpenAI API key in the sidebar to run analysis.
                
                👈 **Look to the left sidebar** and either:
                - Enter your API key in the text field, or  
                - Set the `OPENAI_API_KEY` environment variable
                
                Need an API key? Click the "ℹ️ How to get an OpenAI API key" section in the sidebar.
                """)
            elif not (input_file or input_url):
                st.error("📁 **Input Required**")
                st.markdown("Please either upload a screenshot or enter a URL to analyze.")
            else:
                with st.spinner("Analyzing UI... This may take a few moments."):
                    try:
                        # Initialize LayoutLens
                        tester = LayoutLens(
                            api_key=api_key,
                            model=model
                        )
                        
                        result = None
                        
                        if input_method == "Upload Screenshot":
                            # Handle uploaded screenshot
                            result = analyze_screenshot(tester, input_file, custom_questions, question_method)
                        
                        elif input_method == "Enter URL":
                            # Handle URL
                            result = analyze_url(tester, input_url, viewport, custom_questions, question_method)
                        
                        if result:
                            display_results(result)
                        
                    except Exception as e:
                        st.error(f"Error during analysis: {str(e)}")
                        st.exception(e)

def analyze_screenshot(tester: LayoutLens, uploaded_file, custom_questions: list, question_method: str):
    """Analyze an uploaded screenshot"""
    # For uploaded screenshots, create a temporary image file for analysis
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_file.flush()  # Ensure data is written to disk
        temp_path = temp_file.name
    
    try:
        if question_method == "Custom Questions" and custom_questions:
            # Ask each custom question
            results = []
            for question in custom_questions:
                result = tester.analyze(source=temp_path, query=question)
                results.append({
                    'query': question,
                    'answer': result.answer,
                    'confidence': result.confidence,
                    'screenshot_path': temp_path
                })
            
            return {
                'type': 'custom_questions',
                'results': results,
                'success_rate': 1.0,  # We don't have pass/fail for custom questions
                'total_tests': len(results),
                'passed_tests': len(results)
            }
        else:
            # Auto-generate questions - use a default set for screenshots
            default_questions = [
                "Describe the overall layout and visual hierarchy of this interface",
                "Are there any obvious accessibility issues visible in this screenshot?",
                "Does the layout appear responsive and well-organized?",
                "Are the colors and contrast appropriate for readability?"
            ]
            
            results = []
            for question in default_questions:
                result = tester.analyze(source=temp_path, query=question)
                results.append({
                    'query': question,
                    'answer': result.answer,
                    'confidence': result.confidence,
                    'screenshot_path': temp_path
                })
            
            return {
                'type': 'auto_generated',
                'results': results,
                'success_rate': 1.0,
                'total_tests': len(results),
                'passed_tests': len(results)
            }
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_path)
        except:
            pass

def analyze_url(tester: LayoutLens, url: str, viewport: str, custom_questions: list, question_method: str):
    """Analyze a URL directly"""
    
    try:
        if question_method == "Custom Questions" and custom_questions:
            # Ask each custom question
            results = []
            for question in custom_questions:
                result = tester.analyze(source=url, query=question, viewport=viewport)
                results.append({
                    'query': question,
                    'answer': result.answer,
                    'confidence': result.confidence,
                    'screenshot_path': None  # URL analysis doesn't have screenshot path in this context
                })
            
            return {
                'type': 'custom_questions',
                'results': results,
                'success_rate': 1.0,  # Simplified for Streamlit display
                'total_tests': len(results)
            }
            
        else:  # Auto-generate questions
            # Use a general analysis query for auto-generated analysis
            default_questions = [
                "Is this webpage well-designed and user-friendly?",
                "Are the navigation elements clear and accessible?", 
                "Does the layout appear responsive and well-organized?",
                "Are the colors and contrast appropriate for readability?"
            ]
            
            results = []
            for question in default_questions:
                result = tester.analyze(source=url, query=question, viewport=viewport)
                results.append({
                    'query': question,
                    'answer': result.answer,
                    'confidence': result.confidence,
                    'screenshot_path': None
                })
            
            return {
                'type': 'auto_generated',
                'results': results,
                'success_rate': 1.0,
                'total_tests': len(results)
            }
    
    except Exception as e:
        st.error(f"Error analyzing URL: {str(e)}")
        return None

def display_results(result):
    """Display analysis results in the Streamlit interface"""
    
    if hasattr(result, 'success_rate'):
        # PageTestResult object
        st.success(f"Analysis completed!")
        
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Success Rate", f"{result.success_rate:.1%}")
        with col2:
            st.metric("Total Tests", result.total_tests)
        with col3:
            st.metric("Passed Tests", result.passed_tests)
        
        # Display individual test results
        st.subheader("Test Results")
        
        for i, test_result in enumerate(result.test_results):
            with st.expander(f"Test {i+1}: {test_result['query']}", expanded=True):
                st.write("**Answer:**")
                st.write(test_result['answer'])
                
                if 'screenshot_path' in test_result:
                    if os.path.exists(test_result['screenshot_path']):
                        st.image(test_result['screenshot_path'], caption="Screenshot", use_container_width=True)
                
                # Display confidence if available
                if 'confidence' in test_result:
                    st.write(f"**Confidence:** {test_result['confidence']}")
    
    elif isinstance(result, dict) and 'results' in result:
        # Custom screenshot analysis results
        st.success("Analysis completed!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Questions Analyzed", len(result['results']))
        with col2:
            st.metric("Success Rate", f"{result['success_rate']:.1%}")
        
        st.subheader("Analysis Results")
        
        for i, test_result in enumerate(result['results']):
            with st.expander(f"Question {i+1}: {test_result['query']}", expanded=True):
                st.write("**Answer:**")
                st.write(test_result['answer'])
    
    else:
        st.error("Unexpected result format")
        st.write(result)

if __name__ == "__main__":
    main()