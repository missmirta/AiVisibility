"""FastAPI service that serves the registered stance classifier.

Run: `uv run uvicorn aivisibility.classifier.serve:app --port 8000`
"""

from contextlib import asynccontextmanager

import mlflow
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aivisibility.common import config


class PredictRequest(BaseModel):
    texts: list[str]


class PredictResponse(BaseModel):
    labels: list[str]
    model_uri: str


def load_model(uri: str):
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    return mlflow.sklearn.load_model(uri)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The service stays up even without a model, so /health can report it.
    app.state.model = None
    try:
        app.state.model = load_model(config.STANCE_MODEL_URI)
    except Exception:
        pass
    yield


app = FastAPI(title="AiVisibility stance classifier", lifespan=lifespan)


@app.get("/health")
def health():
    return {"model_loaded": app.state.model is not None, "model_uri": config.STANCE_MODEL_URI}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    labels = [str(label) for label in app.state.model.predict(req.texts)]
    return PredictResponse(labels=labels, model_uri=config.STANCE_MODEL_URI)
