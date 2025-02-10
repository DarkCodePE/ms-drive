from fastapi import FastAPI

import asyncio

from starlette.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import drive


import logging

from app.config.database import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Drive Monitor API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(drive.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Initializing application...")
    try:
        # Initialize database
        db_manager.init_db()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9014,
        workers=2
    )
