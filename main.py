from fastapi import FastAPI

import asyncio

from starlette.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import drive

import logging

from app.config.database import db_manager
from app.event.consumer.analysis_save_consumer import AnalysisSaveConsumer
from app.repository.drive_file_repository import kafka_producer

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
        # Inicializar el productor de Kafka
    try:
        await kafka_producer.start()
        logging.info("Kafka producer started successfully.")
    except Exception as e:
        logging.error(f"Error initializing Kafka producer: {str(e)}")
        raise
    # Inicializar el consumidor de Kafka
    analytics_consumer = AnalysisSaveConsumer()
    app.state.consumer_tasks = [asyncio.create_task(analytics_consumer.start())]
    for task in app.state.consumer_tasks:
        task.add_done_callback(lambda t: handle_consumer_task_result(t))


def handle_consumer_task_result(task):
    """
    Maneja el resultado de las tareas de los consumidores.
    Si una tarea termina con error, lo registra.
    """
    try:
        task.result()
    except asyncio.CancelledError:
        pass  # La tarea fue cancelada normalmente durante el apagado
    except Exception as e:
        logging.error(f"Consumer task failed with error: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop services on shutdown"""
    logger.info("Shutting down application...")
    try:
        # Stop Kafka producer
        await kafka_producer.stop()
        logger.info("Kafka producer stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Kafka producer: {str(e)}")
        raise
    # Stop Kafka consumer
    if hasattr(app.state, 'consumer_tasks'):
        for task in app.state.consumer_tasks:
            task.cancel()
        # Wait for all consumer tasks to finish
        await asyncio.gather(*app.state.consumer_tasks, return_exceptions=True)


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
