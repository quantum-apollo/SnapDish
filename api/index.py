import os
import asyncio
from fastapi import FastAPI
import uvicorn

# Add backend/snapdish to path
import sys
sys.path.insert(0, './backend/snapdish')

from main import app as snapdish_app

# Vercel serverless runs sync, use lifespan
app = FastAPI(lifespan=snapdish_app.router.lifespan if hasattr(snapdish_app.router, 'lifespan') else None)

app.mount("/", snapdish_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
