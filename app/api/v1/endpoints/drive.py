import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request

from app.config.config import get_settings, get_drive_watcher
from app.model.model import MonitoringStatus, DriveFile, ServiceStatus
from app.service.driver_watcher import DriveWatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drive", tags=["drive"])


@router.on_event("startup")
async def startup_event():
    """Inicializa los servicios al iniciar la aplicación."""
    settings = get_settings()
    logger.info("Inicializando DriveWatcher...")
    drive_watcher = get_drive_watcher(settings)
    # Si en la configuración se define un drive_notification_url, se registra el canal.
    if getattr(settings, "drive_notification_url", None):
        try:
            channel = drive_watcher.register_watch_channel(settings.drive_notification_url)
            logger.info(f"Canal de notificaciones registrado correctamente: {channel}")
        except Exception as e:
            logger.error(f"Fallo al registrar el canal de notificaciones: {str(e)}")


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
        watcher: DriveWatcher = Depends(get_drive_watcher)
) -> dict:
    """
    Endpoint para recibir notificaciones push de Google Drive.

    Google Drive enviará una petición POST con cabeceras específicas
    (ej. X-Goog-Resource-State, X-Goog-Channel-ID, etc.). Aquí se registra
    la notificación y se puede disparar el procesamiento (por ejemplo, chequear archivos nuevos).
    """
    headers = request.headers
    body = await request.body()
    logger.info(f"Notificación recibida de Drive. Headers: {headers}. Body: {body}")

    try:
        # En este ejemplo, se invoca la comprobación de nuevos archivos.
        new_files = watcher.check_for_new_files()
        if new_files:
            logger.info(f"Nuevos archivos detectados vía notificación push: {new_files}")
            # Aquí podrías despachar un evento, encolar tareas o realizar otro procesamiento.
        else:
            logger.info("No se detectaron archivos nuevos en la notificación.")
    except Exception as e:
        logger.error(f"Error procesando la notificación: {str(e)}")
        raise HTTPException(status_code=500, detail="Error procesando la notificación")

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
        return {"changes": changes, "new_token": new_token}
    except Exception as e:
        logger.error(f"Error obteniendo cambios incrementales: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
