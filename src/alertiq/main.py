from fastapi import FastAPI
from alertiq.api.routes import incidents, webhook

app = FastAPI(
    title="AlertIQ",
    description="On-call Incident Intelligence — predict alert severity from your own incident history.",
    version="0.1.0",
)

app.include_router(incidents.router)
app.include_router(webhook.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "alertiq"}
