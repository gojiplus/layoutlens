import openai
import requests
from PIL import Image

openai.api_key = "your_openai_api_key"

def upload_image_to_openai(image_path, query):
    """
    Upload an image to OpenAI and query for UI analysis.
    
    Args:
        image_path (str): Path to the UI screenshot.
        query (str): The natural language question about the UI.
    
    Returns:
        str: AI response to the query.
    """
    try:
        with open(image_path, "rb") as image_file:
            response = openai.Image.create(
                purpose="classification",
                image=image_file,
                instructions=query
            )
        
        return response.get("data", {}).get("text", "No response received.")
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None

def test_ui_layout(image_path):
    # Query examples
    queries = [
        "Is the layout the same as before?",
        "Is the right box bigger than the left?",
        "Is the menu at the top of the page but below the header?",
        "Is the text in the paragraph justified?",
    ]

    results = {}
    for query in queries:
        print(f"Running query: {query}")
        result = upload_image_to_openai(image_path, query)
        results[query] = result

    return results

if __name__ == "__main__":
    image_path = "screenshot.png"  # Replace with your screenshot file path
    results = test_ui_layout(image_path)
    
    for query, response in results.items():
        print(f"Query: {query}\nResponse: {response}\n")
