from google import genai
from google.genai import types
from config import GEAR_LINKS


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
        You are an experienced endurance running coach, exercise physiologist, and sports journalist.
        
        Write a data-centric blog post analyzing Raman's running activity using THIRD PERSON narration only.
        
        The tone should feel:
        - analytical and numbers-driven
        - scientifically grounded
        - reflective with real coaching insight
        - professional but human
        
        Do NOT write in first person. Do NOT say "I". Always refer to the athlete as "Raman".
        
        ── SESSION DATA ──
        Activity: {metrics.get('name')}
        Date: {metrics.get('start_date_local')}
        Distance: {metrics.get('distance_km')} km
        Moving Time: {metrics.get('duration_mins')} min
        Elapsed Time: {metrics.get('elapsed_mins')} min
        Stopped Time: {metrics.get('stopped_mins')} min
        Elevation Gain: {metrics.get('elevation_m')} m
        Avg Pace: {metrics.get('average_pace')} /km
        Max Pace: {metrics.get('max_pace')} /km
        Avg Heart Rate: {metrics.get('average_heartrate', 'N/A')} bpm
        Max Heart Rate: {metrics.get('max_heartrate', 'N/A')} bpm
        Avg Cadence: {metrics.get('average_cadence', 'N/A')} spm
        Calories: {metrics.get('calories', 'N/A')} kcal
        Relative Effort: {metrics.get('suffer_score', 'N/A')}
        Gear: {metrics.get('gear', 'N/A')}{f" ({metrics.get('gear_distance_km')}km total)" if metrics.get('gear_distance_km') else ""}
        
        ── TRAINING LOAD (28-DAY WINDOW) ──
        Acute Load (7d): {training_data.get('acute_load_7d')}
        Chronic Load (weekly avg): {training_data.get('chronic_load_weekly_avg')}
        ACWR: {training_data.get('acwr')}
        Health Status: {training_data.get('health_status')}
        Injury Risk: {training_data.get('injury_risk')}
        Runs (7d / 28d): {training_data.get('runs_last_7d')} / {training_data.get('runs_last_28d')}
        Distance (7d / 28d): {training_data.get('distance_last_7d_km')} km / {training_data.get('distance_last_28d_km')} km
        
        ── BLOG STRUCTURE ──
        Write the post in these sections:
        
        1. **Run Snapshot** — Open with the key numbers: distance, pace, duration, heart rate.
           Set the context (time of day, elevation, weather if inferable from date/location).
           Keep it punchy — 2-3 sentences max.
        
        2. **Pace & Effort Breakdown** — Analyze the avg vs max pace gap.
           What does the difference suggest about pacing strategy?
           If heart rate data is available, discuss the effort-to-pace ratio.
           Compute and reference pace per km in min:sec format.
           If cadence is available, assess running form efficiency (optimal ~170-185 spm).
        
        3. **Workload Intelligence** — Dissect the ACWR number.
           Compare acute vs chronic load with actual values.
           Explain what the ratio means in practical terms for injury risk and adaptation.
           Reference the training frequency (runs per week vs month) and volume trends.
           Use the ACWR zones:
           • Below 0.8: Undertraining / detraining risk
           • 0.8–1.3: Optimal training zone
           • 1.3–1.5: Overreaching — caution
           • Above 1.5: Danger zone — high injury risk
        
        4. **Physiological Impact** — Based on the pace, duration, heart rate, and effort:
           What energy system was primarily targeted?
           What adaptations is this session driving? (e.g., mitochondrial density,
           capillarization, lactate clearance, fat oxidation, cardiac output)
           Be specific — reference the actual numbers to justify the analysis.
        
        5. **Recovery & Next Session** — Given the current ACWR and today's effort:
           How much recovery does Raman need before the next session?
           Prescribe a specific next workout (type, distance, target pace, intensity).
           Explain the reasoning using the load data.
        
        6. **Training Trajectory** — Zoom out to the 28-day picture.
           Is Raman building volume safely? Is the progression rate sustainable?
           What should the next 1-2 weeks look like to optimize adaptation
           without spiking injury risk?
        
        ── FORMATTING RULES ──
        - Reference actual numbers throughout — don't just describe, quantify.
        - When discussing pace, always use min:sec/km format.
        - Show your analytical reasoning (e.g., "At an ACWR of 1.12, the acute load
          of 180.5 sits comfortably within the chronic baseline of 161.2...").
        - Avoid vague statements like "good effort" or "solid run" without data backing.
        - Avoid generic motivational clichés.
        - Keep the length around 500–800 words.
        
        End with a concrete coaching directive referencing specific numbers
        (ACWR target, weekly km target, next session pace).
        
        At the very end of the blog post, include a link to the original Strava activity:
        <p><a href="{strava_url}" target="_blank">View the original activity on Strava</a></p>
        {_gear_blog_instruction(metrics)}
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


def _gear_blog_instruction(metrics: dict) -> str:
    """Generates the gear affiliate link instruction for the blog prompt"""
    gear_name = metrics.get('gear', 'N/A')
    if gear_name == 'N/A':
        return ""
    link = GEAR_LINKS.get(gear_name)
    if not link:
        return ""
    distance = metrics.get('gear_distance_km')
    distance_text = f" ({distance}km)" if distance else ""
    return (
        f"Also include a gear mention near the end of the blog post before the Strava link. "
        f"Mention that Raman ran this session in the {gear_name}{distance_text}. "
        f"Make the gear name a clickable link: "
        f'<a href="{link}" target="_blank" rel="nofollow">{gear_name}</a>. '
        f"Keep the mention natural and brief — one sentence."
    )


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


def generate_next_run_advice(metrics: dict, training_data: dict) -> str:
    """Uses Gemini to generate a one-liner next run recommendation"""
    ai_client = genai.Client()

    prompt = f"""
        You are an experienced running coach. Based on the athlete's latest run and
        training load data, generate a single actionable one-liner recommendation
        for their next run.

        Latest run:
        - Distance: {metrics.get('distance_km')} km
        - Duration: {metrics.get('duration_mins')} minutes
        - Elevation: {metrics.get('elevation_m')} meters

        Training load:
        - ACWR: {training_data.get('acwr', 'N/A')}
        - Health status: {training_data.get('health_status', 'N/A')}
        - Injury risk: {training_data.get('injury_risk', 'N/A')}
        - Runs last 7 days: {training_data.get('runs_last_7d')}
        - Distance last 7 days: {training_data.get('distance_last_7d_km')} km

        Rules:
        - Return ONLY one sentence, no quotes, no explanation
        - Be specific (mention distance, pace, or workout type)
        - Factor in current ACWR and injury risk
        - Keep it under 120 characters
        - Sound like a real coach, not an AI
        """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.8),
    )
    return response.text.strip()
