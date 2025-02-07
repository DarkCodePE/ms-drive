from fastapi import FastAPI

import asyncio

from starlette.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import drive


import logging



app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    drive.router
)

# Inicializa la base de datos
#init_db()


# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "langsmith_enabled": True
    }


@app.on_event("startup")
async def startup_event():
    print("Starting up...")


if __name__ == "__main__":
    import uvicorn

    # Elimina la coma y el texto adicional que tenías para evitar errores
    uvicorn.run(app, host="0.0.0.0", port=9014, workers=2)
