import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from app.config.config import get_settings, get_drive_watcher
from app.model.db_model import DriveFileModel
from app.model.model import MonitoringStatus, DriveFile, ServiceStatus
from app.repository.drive_file_repository import sync_drive_files
from app.service.driver_watcher import DriveWatcher
from app.config.database import db_manager  # Importar la instancia de Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drive", tags=["drive"])


# Dependency para obtener la sesión de base de datos
def get_db():
    with db_manager.get_db() as session:
        yield session


@router.on_event("startup")
async def startup_event():
    """Inicializa los servicios al iniciar la aplicación."""
    settings = get_settings()
    print("Inicializando DriveWatcher...")
    drive_watcher = get_drive_watcher(settings)
    print(f"drive_notification_url: {settings.DRIVE_NOTIFICATION_URL}")

    if getattr(settings, "DRIVE_NOTIFICATION_URL", None):
        try:
            channel = drive_watcher.register_watch_channel(settings.DRIVE_NOTIFICATION_URL)
            print(f"Canal de notificaciones registrado correctamente: {channel}")
        except Exception as e:
            print(f"Fallo al registrar el canal de notificaciones: {str(e)}")
    else:
        print("No se configuró DRIVE_NOTIFICATION_URL. Las notificaciones push no estarán disponibles.")


@router.get("/health")
async def health_check(
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> ServiceStatus:
    """Verifica el estado de salud del servicio."""
    return ServiceStatus(
        status="healthy",
        version="1.0.0",
        google_drive_connected=watcher.is_connected(),
        monitoring_active=watcher.is_connected(),
        folder_id=watcher.folder_id
    )


@router.get("/files", response_model=List[DriveFile])
async def list_files(
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> List[DriveFile]:
    """Lista todos los archivos de la carpeta monitorizada."""
    try:
        files = watcher.list_files()
        return [DriveFile(**file) for file in files]
    except Exception as e:
        logger.error(f"Error al listar archivos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/new", response_model=List[DriveFile])
async def check_new_files(
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> List[DriveFile]:
    """Detecta archivos nuevos en la carpeta monitorizada."""
    try:
        new_files = watcher.check_for_new_files()
        return [DriveFile(**file) for file in new_files]
    except Exception as e:
        logger.error(f"Error al chequear nuevos archivos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}", response_model=DriveFile)
async def get_file_details(
        file_id: str,
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> DriveFile:
    """Obtiene detalles de un archivo específico."""
    try:
        file_details = watcher.get_file_details(file_id)
        if file_details is None:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        return DriveFile(**file_details)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener detalles del archivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=MonitoringStatus)
async def get_status(
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> MonitoringStatus:
    """Devuelve el estado actual del monitoreo."""
    return MonitoringStatus(**watcher.get_monitoring_status())


@router.post("/reset")
async def reset_monitoring(
        background_tasks: BackgroundTasks,
        watcher: DriveWatcher = Depends(get_drive_watcher)
):
    """Reinicia el estado del monitoreo."""
    try:
        background_tasks.add_task(watcher.reset_processed_files)
        return {"message": "Reinicio del estado de monitoreo iniciado"}
    except Exception as e:
        logger.error(f"Error al reiniciar el monitoreo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications")
async def drive_notifications(
        request: Request,
        background_tasks: BackgroundTasks,
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> dict:
    """
    Endpoint para recibir notificaciones push de Google Drive.
    """

    print("--- NOTIFICATION ENDPOINT HIT ---")  # <--- ADD THIS LINE
    print(f"Raw Headers: {request.headers}")  # <--- Log raw headers
    try:
        body = await request.body()
        print(f"Raw Body: {body}")  # <--- Log raw body
        print(f"Decoded Body: {body.decode('utf-8') if body else ''}")  # <--- Try to decode body
    except Exception as body_err:
        print(f"Error reading body: {body_err}")

    headers = request.headers
    print(f"Parsed Headers: {dict(headers)}")  # <--- Log parsed headers

    resource_state = headers.get("X-Goog-Resource-State")
    channel_id = headers.get("X-Goog-Channel-ID")
    resource_id = headers.get("X-Goog-Resource-ID")
    print(f"Resource State: {resource_state}, Channel ID: {channel_id}, Resource ID: {resource_id}")

    try:
        print("Calling watcher.check_for_new_files() from notification endpoint...")  # <--- ADD THIS LINE
        background_tasks.add_task(watcher.check_for_new_files)
        print("watcher.check_for_new_files() task dispatched.")  # <--- ADD THIS LINE
    except Exception as e:
        logger.error(f"Error processing the notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing the notification")
    print("--- NOTIFICATION ENDPOINT PROCESSING COMPLETED ---")  # <--- ADD THIS LINE
    return {"status": "notificación recibida"}


@router.get("/files/changes")
async def get_incremental_changes(
        saved_token: Optional[str] = None,
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> dict:
    """
    Endpoint para obtener los cambios incrementales desde un token guardado.

    Si no se proporciona 'saved_token', se obtiene el token inicial.
    Retorna un diccionario con la lista de cambios y el nuevo token.
    """
    try:
        changes, new_token = watcher.get_incremental_changes(saved_token)
        print(f"changes: {changes}")
        return {"changes": changes, "new_token": new_token}
    except Exception as e:
        logger.error(f"Error obteniendo cambios incrementales: {str(e)}")
        print(f"Error obteniendo cambios incrementales: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_drive_files_endpoint(
        watcher: DriveWatcher = Depends(get_drive_watcher),
        db_session: Session = Depends(get_db)
) -> dict:
    """Sincroniza la lista de archivos de Google Drive con la base de datos."""
    try:
        files = watcher.list_files()
        drive_files = [DriveFile(**file) for file in files]

        new_files = sync_drive_files(db_session, drive_files)

        return {
            "synced": len(new_files),
            "new_files": [file.name for file in new_files]
        }
    except Exception as e:
        logger.error(f"Error en la sincronización: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db-files")
async def get_db_files(
        db_session: Session = Depends(get_db)
) -> List[dict]:
    """Retorna la lista de archivos almacenados en la base de datos."""
    try:
        files = db_session.query(DriveFileModel).all()
        return [file.to_dict() for file in files]
    except Exception as e:
        logger.error(f"Error al obtener archivos desde la base de datos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
