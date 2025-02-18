import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File
from sqlalchemy.orm import Session
from app.config.config import get_settings, get_drive_watcher
from app.model.db_model import DriveFileModel, DriveFolderModel
from app.model.model import MonitoringStatus, DriveFile, ServiceStatus, FolderCreate
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

        new_files = await sync_drive_files(db_session, drive_files)

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


@router.post("/folders")
async def create_drive_folder_sync(
        folder: FolderCreate,  # Use your FolderCreate Pydantic schema
        watcher: DriveWatcher = Depends(get_drive_watcher),
        db: Session = Depends(get_db)):
    """Crea una nueva carpeta en la estructura de la aplicación, sincronizando con Google Drive."""
    try:

        # 1. Check if folder exists in Google Drive
        existing_folder_in_drive = watcher.find_folder_by_name(folder.name)

        if existing_folder_in_drive:
            google_drive_folder_id = existing_folder_in_drive.get('id')
            logger.info(f"Folder '{folder.name}' already exists in Google Drive (ID: {google_drive_folder_id}).")

            # 2. Check if folder exists in DB with this google_drive_folder_id
            existing_folder_in_db = db.query(DriveFolderModel).filter(
                DriveFolderModel.google_drive_folder_id == google_drive_folder_id).first()

            if existing_folder_in_db:
                logger.info(
                    f"Folder '{folder.name}' already exists in database (ID: {existing_folder_in_db.id}). Returning existing folder.")
                return {
                    "message": "Folder already exists",
                    "folder_id": existing_folder_in_db.id,
                    "google_drive_folder_id": existing_folder_in_db.google_drive_folder_id,
                    "parent_folder_id": existing_folder_in_db.parent_id
                }
            else:
                logger.info(f"Folder '{folder.name}' exists in Drive but not in DB. Creating DB record.")
                # Create DB record linking to existing Drive folder
                db_folder = DriveFolderModel(
                    name=folder.name,
                    parent_id=existing_folder_in_drive['parents'][0],
                    google_drive_folder_id=google_drive_folder_id
                )
                db.add(db_folder)
                db.commit()
                db.refresh(db_folder)
                return {
                    "message": "Folder synced (Drive folder existed, DB record created)",
                    "folder_id": db_folder.id,
                    "google_drive_folder_id": db_folder.google_drive_folder_id,
                    "parent_folder_id": db_folder.parent_id
                }

        else:
            logger.info(f"Folder '{folder.name}' does not exist in Google Drive. Creating in Drive.")
            # 3. Create folder in Google Drive as it doesn't exist
            google_parent_folder_id = watcher.folder_id
            created_folder_in_drive = watcher.create_folder(folder.name, google_parent_folder_id)
            if created_folder_in_drive:
                google_drive_folder_id = created_folder_in_drive.get('id')

                # 4. Create folder in DB as it doesn't exist
                db_folder = DriveFolderModel(
                    name=folder.name,
                    parent_id=google_parent_folder_id,  # Use requested parent ID from input
                    google_drive_folder_id=google_drive_folder_id
                )
                db.add(db_folder)
                db.commit()
                db.refresh(db_folder)
                return {
                    "message": "Folder created successfully in Drive and DB",
                    "folder_id": db_folder.id,
                    "google_drive_folder_id": db_folder.google_drive_folder_id,
                    "parent_folder_id": db_folder.parent_id
                }
            else:
                raise HTTPException(status_code=500,
                                    detail="Error creating folder in Google Drive")

    except HTTPException as http_e:
        db.rollback()
        logger.error(f"HTTP Error creating folder: {str(http_e)}")
        raise http_e  # Re-raise HTTP exception to propagate status code
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")


@router.get("/folders/{folder_id}/structure",
            response_model=None)  # TODO: Define un Pydantic model para la estructura de carpeta
async def get_folder_structure(folder_id: int, db: Session = Depends(get_db)):
    """Obtiene la estructura de carpetas y archivos de una carpeta específica."""
    db_folder = db.query(DriveFolderModel).get(folder_id)
    if not db_folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    def build_structure(folder: DriveFolderModel):
        """Función recursiva para construir la estructura JSON."""
        folder_data = {
            "id": folder.id,
            "name": folder.name,
            "google_drive_folder_id": folder.google_drive_folder_id,
            "children": [build_structure(child) for child in folder.children],
            "documents": [{"id": doc.id, "name": doc.name, "mime_type": doc.mime_type, "file_id": doc.file_id} for doc
                          in folder.documents]
        }
        return folder_data

    return build_structure(db_folder)


@router.get("/root_structure", response_model=None)  # TODO: Define un Pydantic model para la estructura raiz
async def get_root_structure(db: Session = Depends(get_db)):
    """Obtiene la estructura de carpetas y archivos desde la raíz."""
    root_folders = db.query(DriveFolderModel).filter(DriveFolderModel.parent_id == None).all()  # Obtener carpetas raíz
    structure = []
    for folder in root_folders:
        structure.append(await get_folder_structure(folder.id, db))  # Reutiliza get_folder_structure para cada raíz
    return structure


@router.post("/folders/{folder_id}/upload_file",
             response_model=None)  # TODO: Define un Pydantic model para respuesta de subida de archivo
async def upload_file_to_folder(folder_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Sube un archivo a una carpeta específica (solo metadatos en la DB por ahora)."""
    db_folder = db.query(DriveFolderModel).get(folder_id)
    if not db_folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Por ahora, solo guardamos metadatos en la base de datos.
    # La descarga desde Google Drive y el procesamiento se manejarán por el DriveFileConsumer.
    db_document = DriveFileModel(
        name=file.filename,
        mime_type=file.content_type,  # file.mime_type no existe en UploadFile de FastAPI
        folder_id=folder_id,
        file_id="pending_upload_" + str(datetime.now().timestamp())
        # Placeholder, se actualiza al sincronizar con Drive si es necesario
        # ... otros campos que puedas obtener o necesitar ...
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return {"message": "File metadata added successfully",
            "document_id": db_document.id}  # Devuelve un JSON con mensaje e ID
