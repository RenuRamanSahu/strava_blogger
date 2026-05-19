from google import genai
from google.genai import types


def generate_blog_with_gemini(metrics: dict, training_data: dict, strava_url: str):
    """Uses gemini-2.5-flash to compile raw stats into a human narrative blog layout"""
    ai_client = genai.Client()

    system_instruction = (
        "You are a professional fitness blogger writing for renuramansahu.com. "
        "Your tone is authentic, engaging, and entirely human—avoid cliché AI phrasing. "
        "Write a structured blog post based on the provided activity data. "
        "Format using clean HTML (only <h2>, <p>, <strong>, <ul>, and <a> tags). No markdown wrappers."
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
        - Distance: {metrics.get('distance_km')} km
        - Moving Time: {metrics.get('duration_mins')} minutes
        - Elevation Gain: {metrics.get('elevation_m')} meters
        - Average Speed: {metrics.get('average_speed')} m/s
        - Max Speed: {metrics.get('max_speed')} m/s
        - Start Date: {metrics.get('start_date_local')}
        
        Training Load & Run Health Data:
        - Acute Load (last 7 days): {training_data.get('acute_load_7d')}
        - Chronic Load (weekly avg over 28 days): {training_data.get('chronic_load_weekly_avg')}
        - Acute:Chronic Workload Ratio (ACWR): {training_data.get('acwr')}
        - Run Health Status: {training_data.get('health_status')}
        - Injury Risk Level: {training_data.get('injury_risk')}
        - Runs in last 7 days: {training_data.get('runs_last_7d')}
        - Runs in last 28 days: {training_data.get('runs_last_28d')}
        - Distance last 7 days: {training_data.get('distance_last_7d_km')} km
        - Distance last 28 days: {training_data.get('distance_last_28d_km')} km
        
        Write the blog post in the following structure:
        
        1. Opening summary of the run
        2. Performance analysis from a coach's perspective
        3. Acute:Chronic Workload Ratio breakdown — explain what the current ACWR 
           means for Raman's training load management and injury risk
        4. Run health assessment — based on the ACWR zone, volume trends, and 
           frequency, give a clear verdict on whether Raman is undertraining, 
           in the sweet spot, or pushing too hard
        5. What the session likely improved physiologically
        6. Suggested next workout based on this effort and current ACWR
        7. Long-term progression insight incorporating workload trends
        
        The coaching analysis should feel realistic and data-driven.
        Use the ACWR data to make specific, actionable recommendations.
        
        ACWR interpretation guide for reference:
        - Below 0.8: Undertraining / detraining risk
        - 0.8 to 1.3: Optimal training zone (sweet spot)
        - 1.3 to 1.5: Overreaching — caution needed
        - Above 1.5: Danger zone — high injury risk
        
        Examples of topics you may discuss:
        - aerobic development
        - pacing consistency
        - fatigue management
        - endurance adaptation
        - recovery
        - running economy
        - threshold development
        - load management
        - periodization
        
        Avoid generic motivational clichés.
        
        Keep the length around 500–800 words.
        
        End the article with a concise coaching takeaway for Raman's next phase of training,
        specifically referencing his current ACWR and what adjustments to make.
        
        At the very end of the blog post, include a link to the original Strava activity:
        <p><a href="{strava_url}" target="_blank">View the original activity on Strava</a></p>
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


def generate_blog_title(metrics: dict) -> str:
    """Uses Gemini to generate a creative, SEO-friendly blog post title"""
    ai_client = genai.Client()

    prompt = f"""
        Generate a single blog post title for a running activity recap on renuramansahu.com.

        Activity details:
        - Name: {metrics.get('name')}
        - Distance: {metrics.get('distance_km')} km
        - Duration: {metrics.get('duration_mins')} minutes
        - Elevation: {metrics.get('elevation_m')} meters

        Rules:
        - Return ONLY the title text, nothing else
        - No quotes, no explanation, no punctuation wrapping
        - Make it engaging, specific to the run, and SEO-friendly
        - Reference the athlete "Raman" by name
        - Keep it under 80 characters
        - Avoid generic phrases like "A Great Run" or "Another Day"
        """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.9),
    )
    return response.text.strip()
