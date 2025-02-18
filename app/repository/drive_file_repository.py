import logging
from typing import List
from sqlalchemy.orm import Session
from dateutil.parser import parse as parse_date
from datetime import datetime

from app.event.producers.producer import KafkaProducer
from app.model.db_model import DriveFileModel
from app.model.model import DriveFile

logger = logging.getLogger(__name__)

# Instancia global de KafkaProducer (puedes ajustarlo según tus necesidades)
kafka_producer = KafkaProducer()


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


async def sync_drive_files(db: Session, drive_files: List[DriveFile]) -> List[DriveFileModel]:
    """
    Sincroniza una lista de archivos con la base de datos.

    Args:
        db: Sesión de base de datos
        drive_files: Lista de archivos de Drive a sincronizar

    Returns:
        Lista de nuevos archivos insertados

    Raises:
        Exception: Si hay un error durante la sincronización
    """
    try:
        logger.info(f"Iniciando sincronización de {len(drive_files)} archivos")
        new_files = []

        for drive_file in drive_files:
            try:
                # 1. Preparar los datos del archivo
                file_data = {
                    'id': safe_str(getattr(drive_file, 'id', '')),
                    'name': safe_str(getattr(drive_file, 'name', '')),
                    'mime_type': safe_str(getattr(drive_file, 'mimeType', '')),
                    'web_view_link': safe_str(getattr(drive_file, 'webViewLink', '')),
                }

                # 2. Procesar la fecha de modificación
                try:
                    modified_time = parse_date(
                        drive_file.modifiedTime) if drive_file.modifiedTime else datetime.utcnow()
                except (ValueError, AttributeError):
                    modified_time = datetime.utcnow()
                    logger.warning(f"Usando fecha actual para {file_data['name']}")

                # 3. Buscar el archivo en la BD
                existing = db.query(DriveFileModel).filter_by(file_id=file_data['id']).first()

                if not existing:
                    # 4a. Crear nuevo registro
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
                    logger.info(f"Archivo nuevo preparado para inserción: {file_data['name']}")
                else:
                    # 4b. Actualizar si la fecha de modificación cambió
                    if existing.modified_time != modified_time:
                        existing.name = file_data['name']
                        existing.mime_type = file_data['mime_type']
                        existing.modified_time = modified_time
                        existing.web_view_link = file_data['web_view_link'] if file_data[
                                                                                   'web_view_link'] != 'None' else None
                        db.add(existing)
                        logger.info(f"Archivo preparado para actualización: {file_data['name']}")

            except Exception as e:
                logger.error(f"Error procesando archivo {safe_str(getattr(drive_file, 'name', 'Unknown'))}: {str(e)}")
                continue

        # 5. Guardar todos los cambios en la base de datos
        try:
            db.commit()
            logger.info(f"Sincronización completada. {len(new_files)} archivos nuevos insertados")
        except Exception as commit_error:
            logger.error(f"Error al guardar en base de datos: {str(commit_error)}")
            db.rollback()
            raise
        # Preparar evento
        event = {
            "type": "drive-files-synced",
            "data": {
                "file_ids": [file.file_id for file in new_files],
                "file_names": [file.name for file in new_files],
                "mime_types": [file.mime_type for file in new_files],
                "modified_times": [file.modified_time.isoformat() for file in new_files],
                "web_view_links": [file.web_view_link for file in new_files],
                "detected_at": datetime.utcnow().isoformat()
            },
            "metadata": {
                "source": "ms-ingest",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        # Publicar evento en Kafka
        try:
            await kafka_producer.send_event("drive-events", event)
            logger.info(f"Evento enviado al tópico 'drive-events': {event}")
        except Exception as e:
            logger.error(f"Error al enviar evento a Kafka: {e}")

        return new_files

    except Exception as e:
        logger.error(f"Error en sync_drive_files: {str(e)}")
        db.rollback()
        raise
