from pydantic import BaseModel


# Pydantic schema enforcing structure for incoming Strava alerts
class StravaWebhookPayload(BaseModel):
    object_type: str
    aspect_type: str
    object_id: int
    owner_id: int
    subscription_id: int
    event_time: int
