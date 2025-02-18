import io
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

logger = logging.getLogger(__name__)


class DriveWatcher:
    """Monitor de carpeta en Google Drive con capacidades de notificación push e incremental changes."""

    REQUIRED_SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive.photos.readonly",
        "https://www.googleapis.com/auth/drive.metadata",
        "https://www.googleapis.com/auth/drive.meet.readonly",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, folder_id: str, credentials_path: str):
        self.folder_id = folder_id
        # Carga las credenciales con los scopes requeridos
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=self.REQUIRED_SCOPES
        )
        # Verifica que las credenciales tengan los scopes requeridos
        self.verify_scopes()
        # Construye el cliente de la API de Drive
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
        self.processed_files = set()
        self.last_check_time = None
        self._is_connected = False
        self._verify_connection()

    def verify_scopes(self) -> bool:
        """Verifica que las credenciales tengan los scopes requeridos."""
        if not self.credentials.scopes:
            print("No se encontraron scopes en las credenciales.")
            logger.warning("No se encontraron scopes en las credenciales.")
            return False
        missing = [scope for scope in self.REQUIRED_SCOPES if scope not in self.credentials.scopes]
        if missing:
            print(f"Faltan los siguientes scopes requeridos: {missing}")
            logger.error(f"Faltan los siguientes scopes requeridos: {missing}")
            return False
        else:
            print("Todos los scopes requeridos están presentes.")
            logger.info("Todos los scopes requeridos están presentes.")
            return True

    def _verify_connection(self) -> bool:
        """Verifica la conexión a Google Drive."""
        try:
            self.drive_service.files().get(fileId=self.folder_id).execute()
            self._is_connected = True
            print("Conexión exitosa a Google Drive")
            logger.info("Conexión exitosa a Google Drive")
            return True
        except HttpError as e:
            print(f"Fallo al conectar con Google Drive: {str(e)}")
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
            logger.debug(f"Información de la carpeta: {folder}")
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
        print("--- check_for_new_files FUNCTION STARTED ---")  # <--- ADD THIS LINE
        print(f"Current processed_files set: {self.processed_files}")  # <--- ADD THIS LINE
        files = self.list_files()
        print(f"list_files() returned {len(files)} files.")  # <--- ADD THIS LINE
        new_files = []
        for file in files:
            file_id = file['id']
            if file_id not in self.processed_files:
                file['detected_at'] = datetime.now(timezone.utc).isoformat()
                new_files.append(file)
                self.processed_files.add(file_id)
                logger.info(f"Archivo nuevo detectado: {file['name']} (ID: {file_id})")
        print(f"New files detected in this check: {len(new_files)}")  # <--- ADD THIS LINE
        print(f"processed_files set after check: {self.processed_files}")  # <--- ADD THIS LINE
        print("--- check_for_new_files FUNCTION COMPLETED ---")  # <--- ADD THIS LINE
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
        if not notification_url:
            logger.warning("No se proporcionó drive_notification_url. El canal de notificaciones no se registrará.")
            logger.debug(f"notification_url: {notification_url}")
            return {}
        channel_id = str(uuid.uuid4())
        logger.info(f"channel_id: {channel_id}")
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": notification_url
        }
        try:
            start_page_token_response = self.drive_service.changes().getStartPageToken().execute()
            print(f"start_page_token_response: {start_page_token_response}")
            start_page_token = start_page_token_response.get("startPageToken")
            print(f"start_page_token: {start_page_token}")
            channel = self.drive_service.changes().watch(
                pageToken=start_page_token,
                body=body
            ).execute()
            print(f"""
                    Canal de notificaciones registrado exitosamente:
                    - Channel ID: {channel.get('id')}
                    - Resource ID: {channel.get('resourceId')}
                    - Expiration: {channel.get('expiration')}
                    - Type: {channel.get('type')}
                """)
            logger.info(f"Canal de notificaciones registrado con ID {channel_id}: {channel}")
            return channel
        except HttpError as e:
            print(f"Error al registrar el canal de notificaciones: {str(e)}")
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
            print(f"page_token: {page_token}")
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

    def create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Crea una nueva carpeta en Google Drive.

        Args:
            folder_name: El nombre de la carpeta a crear.
            parent_folder_id: El ID de la carpeta padre en Google Drive, si aplica.
                                Si es None, la carpeta se crea en la raíz del Drive.

        Returns:
            Un diccionario con los metadatos de la carpeta creada, o None si falla la creación.
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        try:
            file = self.drive_service.files().create(body=file_metadata,
                                                     fields='id, name, mimeType, parents').execute()
            logger.info(f"Carpeta '{folder_name}' creada en Google Drive con ID: {file.get('id')}")
            return file
        except HttpError as e:
            logger.error(f"Error al crear la carpeta '{folder_name}' en Google Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al crear la carpeta '{folder_name}' en Google Drive: {e}")
            return None

    def find_folder_by_name(self, folder_name: str) -> Optional[
        Dict[str, Any]]:
        """Busca una carpeta en Google Drive por nombre y carpeta padre (opcional).

        Args:
            folder_name: El nombre de la carpeta a buscar.
            parent_folder_id: El ID de la carpeta padre en Google Drive, si aplica.

        Returns:
            Un diccionario con los metadatos de la carpeta encontrada, o None si no se encuentra.
        """
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"

        try:
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, parents)"
            ).execute()
            folders = results.get('files', [])
            if folders:
                return folders[
                    0]  # Retorna la primera carpeta encontrada (debería ser única por nombre en el mismo padre)
            else:
                return None  # No se encontró la carpeta
        except HttpError as e:
            logger.error(f"Error al buscar la carpeta '{folder_name}' en Google Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al buscar la carpeta '{folder_name}' en Google Drive: {e}")
            return None

    def upload_file(self, file_name: str, mime_type: str, file_content: bytes,
                    parent_folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Sube un archivo a Google Drive.

        Args:
            file_name: Nombre del archivo.
            mime_type: Tipo MIME del archivo.
            file_content: Contenido del archivo en bytes.
            parent_folder_id: ID de la carpeta padre en Google Drive.

        Returns:
            Dict con los metadatos del archivo subido, o None si falla.
        """
        try:
            file_metadata = {
                'name': file_name
            }
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]

            # Crear el objeto MediaIoBaseUpload desde los bytes
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(
                fh,
                mimetype=mime_type,
                resumable=True
            )

            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, webViewLink, modifiedTime, parents'
            ).execute()

            logger.info(f"Archivo '{file_name}' subido a Google Drive con ID: {file.get('id')}")
            return file

        except Exception as e:
            logger.error(f"Error al subir el archivo '{file_name}' a Google Drive: {str(e)}")
            return None