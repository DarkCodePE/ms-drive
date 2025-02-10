import logging
from typing import List
from sqlalchemy.orm import Session
from dateutil.parser import parse as parse_date
from datetime import datetime

from app.model.db_model import DriveFileModel
from app.model.model import DriveFile

logger = logging.getLogger(__name__)


def safe_str(value) -> str:
    """Convierte un valor a cadena de forma segura."""
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    elif isinstance(value, str):
        return value.encode('utf-8', errors='replace').decode('utf-8')
    try:
        return str(value)
    except Exception:
        return repr(value)


def sync_drive_files(db: Session, drive_files: List[DriveFile]) -> List[DriveFileModel]:
    """
    Sincroniza una lista de archivos con la base de datos.

    Args:
        db: Sesión de base de datos del DatabaseManager
        drive_files: Lista de archivos de Drive a sincronizar

    Returns:
        Lista de nuevos archivos insertados
    """
    try:
        logger.info(f"Iniciando sincronización de {len(drive_files)} archivos")
        new_files = []

        for drive_file in drive_files:
            try:
                # Prepara los datos del archivo
                file_data = {
                    'id': safe_str(getattr(drive_file, 'id', '')),
                    'name': safe_str(getattr(drive_file, 'name', '')),
                    'mime_type': safe_str(getattr(drive_file, 'mimeType', '')),
                    'web_view_link': safe_str(getattr(drive_file, 'webViewLink', '')),
                }

                # Procesa la fecha de modificación
                try:
                    modified_time = parse_date(
                        drive_file.modifiedTime) if drive_file.modifiedTime else datetime.utcnow()
                except (ValueError, AttributeError):
                    modified_time = datetime.utcnow()
                    logger.warning(f"Usando fecha actual para {file_data['name']}")

                # Busca el archivo en la BD
                existing = db.query(DriveFileModel).filter_by(file_id=file_data['id']).first()

                if not existing:
                    # Crea nuevo registro
                    new_file = DriveFileModel(
                        file_id=file_data['id'],
                        name=file_data['name'],
                        mime_type=file_data['mime_type'],
                        modified_time=modified_time,
                        web_view_link=file_data['web_view_link'] if file_data['web_view_link'] != 'None' else None,
                        detected_at=datetime.utcnow()
                    )
                    db.add(new_file)
                    new_files.append(new_file)
                    logger.info(f"Archivo nuevo insertado: {file_data['name']}")
                else:
                    # Actualiza si la fecha de modificación cambió
                    if existing.modified_time != modified_time:
                        existing.name = file_data['name']
                        existing.mime_type = file_data['mime_type']
                        existing.modified_time = modified_time
                        existing.web_view_link = file_data['web_view_link'] if file_data[
                                                                                   'web_view_link'] != 'None' else None
                        db.add(existing)
                        logger.info(f"Archivo actualizado: {file_data['name']}")

            except Exception as e:
                logger.error(f"Error procesando archivo {safe_str(getattr(drive_file, 'name', 'Unknown'))}: {str(e)}")
                continue

        # El commit se realiza automáticamente al salir del context manager
        logger.info(f"Sincronización completada. {len(new_files)} archivos nuevos insertados")
        return new_files

    except Exception as e:
        logger.error(f"Error en sync_drive_files: {str(e)}")
        raise