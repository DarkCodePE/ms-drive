import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class DriveWatcher:
    """Monitor de carpeta en Google Drive con capacidades de notificación push."""

    def __init__(self, folder_id: str, credentials_path: str):
        self.folder_id = folder_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
        self.processed_files = set()
        self.last_check_time = None
        self._is_connected = False
        self._verify_connection()

    def _verify_connection(self) -> bool:
        """Verifica la conexión a Google Drive."""
        try:
            # Se obtiene la metadata de la carpeta para probar la conexión.
            self.drive_service.files().get(fileId=self.folder_id).execute()
            self._is_connected = True
            logger.info("Conexión exitosa a Google Drive")
            return True
        except HttpError as e:
            logger.error(f"Fallo al conectar con Google Drive: {str(e)}")
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """Devuelve el estado de conexión a Google Drive."""
        return self._is_connected

    def get_folder_info(self) -> Dict[str, Any]:
        """Obtiene información de la carpeta monitorizada."""
        try:
            folder = self.drive_service.files().get(
                fileId=self.folder_id,
                fields="id, name, mimeType, modifiedTime"
            ).execute()
            return folder
        except HttpError as e:
            logger.error(f"Error obteniendo la información de la carpeta: {str(e)}")
            raise

    def list_files(self, page_size: int = 100) -> List[Dict[str, Any]]:
        """Lista todos los archivos de la carpeta monitorizada."""
        try:
            results = self.drive_service.files().list(
                q=f"'{self.folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
                pageSize=page_size
            ).execute()

            files = results.get('files', [])
            self.last_check_time = datetime.now(timezone.utc)
            logger.debug(f"Se encontraron {len(files)} archivos en la carpeta")
            return files
        except HttpError as e:
            logger.error(f"Error al listar archivos: {str(e)}")
            raise

    def check_for_new_files(self) -> List[Dict[str, Any]]:
        """Detecta archivos nuevos que no han sido procesados aún."""
        files = self.list_files()
        new_files = []

        for file in files:
            file_id = file['id']
            if file_id not in self.processed_files:
                file['detected_at'] = datetime.now(timezone.utc).isoformat()
                new_files.append(file)
                self.processed_files.add(file_id)
                logger.info(f"Archivo nuevo detectado: {file['name']} (ID: {file_id})")

        return new_files

    def get_file_details(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene detalles de un archivo específico."""
        try:
            return self.drive_service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, webViewLink, size, createdTime"
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Archivo no encontrado: {file_id}")
                return None
            logger.error(f"Error obteniendo detalles del archivo: {str(e)}")
            raise

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Devuelve el estado actual del monitoreo."""
        return {
            "is_running": self._is_connected,
            "folder_id": self.folder_id,
            "last_check": self.last_check_time,
            "files_processed": len(self.processed_files)
        }

    def reset_processed_files(self) -> None:
        """Limpia el registro de archivos procesados."""
        self.processed_files.clear()
        logger.info("Cache de archivos procesados limpiada")

    def register_watch_channel(self, notification_url: str) -> Dict[str, Any]:
        """
        Registra un canal de notificaciones push en el feed de cambios de Google Drive.
        Es necesario disponer de un endpoint HTTPS (notification_url) accesible desde internet.
        """
        channel_id = str(uuid.uuid4())
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": notification_url
        }
        try:
            # Se obtiene el token inicial para cambios
            start_page_token_response = self.drive_service.changes().getStartPageToken().execute()
            start_page_token = start_page_token_response.get("startPageToken")
            # Se registra el canal para recibir notificaciones
            channel = self.drive_service.changes().watch(
                pageToken=start_page_token,
                body=body
            ).execute()
            logger.info(f"Canal de notificaciones registrado con ID {channel_id}: {channel}")
            return channel
        except HttpError as e:
            logger.error(f"Error al registrar el canal de notificaciones: {str(e)}")
            raise

    def get_incremental_changes(self, saved_page_token: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        """
        Obtiene los cambios incrementales desde el token guardado.

        Si no se proporciona 'saved_page_token', se obtiene un token inicial.
        Retorna una tupla con la lista de cambios y el nuevo token.
        """
        try:
            if not saved_page_token:
                token_response = self.drive_service.changes().getStartPageToken().execute()
                saved_page_token = token_response.get("startPageToken")
                logger.info(f"Token inicial obtenido: {saved_page_token}")

            changes: List[Dict[str, Any]] = []
            page_token = saved_page_token
            new_token = saved_page_token

            while True:
                response = self.drive_service.changes().list(
                    pageToken=page_token,
                    spaces="drive",
                    fields="nextPageToken, newStartPageToken, changes(fileId, file(name, mimeType, modifiedTime, webViewLink))"
                ).execute()

                changes.extend(response.get("changes", []))
                if "newStartPageToken" in response:
                    new_token = response.get("newStartPageToken")
                if "nextPageToken" not in response:
                    break
                page_token = response.get("nextPageToken")

            logger.info(f"{len(changes)} cambios obtenidos. Nuevo token: {new_token}")
            return changes, new_token

        except HttpError as e:
            logger.error(f"Error al obtener cambios incrementales: {str(e)}")
            raise