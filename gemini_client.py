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
        You are an experienced endurance running coach and sports journalist.
        
        Write a polished blog post about Raman's running activity using THIRD PERSON narration only.
        
        The tone should feel:
        - intelligent
        - reflective
        - analytical
        - motivating without sounding cheesy
        - professional but human
        
        Do NOT write in first person.
        Do NOT say "I".
        Always refer to the athlete as "Raman".
        
        Activity Data:
        - Activity Name: {metrics.get('name')}
        - Distance: {round(metrics.get('distance', 0) / 1000, 2)} km
        - Moving Time: {round(metrics.get('moving_time', 0) / 60)} minutes
        - Elevation Gain: {metrics.get('total_elevation_gain', 0)} meters
        - Average Speed: {metrics.get('average_speed')}
        - Max Speed: {metrics.get('max_speed')}
        - Start Date: {metrics.get('start_date_local')}
        
        Write the blog post in the following structure:
        
        1. Opening summary of the run
        2. Performance analysis from a coach's perspective
        3. What the session likely improved physiologically
        4. Suggested next workout based on this effort
        5. Long-term progression insight
        
        The coaching analysis should feel realistic and data-driven.
        
        Examples of topics you may discuss:
        - aerobic development
        - pacing consistency
        - fatigue management
        - endurance adaptation
        - recovery
        - running economy
        - threshold development
        
        Avoid generic motivational clichés.
        
        Keep the length around 400–700 words.
        
        End the article with a concise coaching takeaway for Raman's next phase of training.
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
