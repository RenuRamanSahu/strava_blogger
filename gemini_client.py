from google import genai
from google.genai import types


def generate_blog_with_gemini(metrics: dict):
    """Uses gemini-2.5-flash to compile raw stats into a human narrative blog layout"""
    ai_client = genai.Client()

    system_instruction = (
        "You are a professional fitness blogger writing for renuramansahu.com. "
        "Your tone is authentic, engaging, and entirely human—avoid cliché AI phrasing. "
        "Write a structured blog post based on the provided activity data. "
        "Format using clean HTML (only <h2>, <p>, <strong>, and <ul> tags). No markdown wrappers."
    )

    user_prompt = f"""
    Write an engaging blog post about my recent workout:
    - Activity Type: {metrics['type']}
    - Workout Name: "{metrics['name']}"
    - Distance Covered: {metrics['distance_km']} km
    - Total Time: {metrics['duration_mins']} minutes
    - Elevation Gain: {metrics['elevation_m']} meters
    """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )
    )
    return response.text
