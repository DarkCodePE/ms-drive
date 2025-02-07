import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class DriveWatcher:
    """Enhanced Google Drive folder monitor with additional testing capabilities."""

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
        """Verify connection to Google Drive."""
        try:
            # Try to get folder metadata as connection test
            self.drive_service.files().get(fileId=self.folder_id).execute()
            self._is_connected = True
            logger.info("Successfully connected to Google Drive")
            return True
        except HttpError as e:
            logger.error(f"Failed to connect to Google Drive: {str(e)}")
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """Check if connected to Google Drive."""
        return self._is_connected

    def get_folder_info(self) -> Dict[str, Any]:
        """Get information about the monitored folder."""
        try:
            folder = self.drive_service.files().get(
                fileId=self.folder_id,
                fields="id, name, mimeType, modifiedTime"
            ).execute()
            return folder
        except HttpError as e:
            logger.error(f"Error getting folder info: {str(e)}")
            raise

    def list_files(self, page_size: int = 100) -> List[Dict[str, Any]]:
        """List all files in the monitored folder."""
        try:
            results = self.drive_service.files().list(
                q=f"'{self.folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
                pageSize=page_size
            ).execute()

            files = results.get('files', [])
            self.last_check_time = datetime.now(timezone.utc)
            logger.debug(f"Found {len(files)} files in folder")
            return files
        except HttpError as e:
            logger.error(f"Error listing files: {str(e)}")
            raise

    def check_for_new_files(self) -> List[Dict[str, Any]]:
        """Check for new files that haven't been processed."""
        files = self.list_files()
        new_files = []

        for file in files:
            file_id = file['id']
            if file_id not in self.processed_files:
                file['detected_at'] = datetime.now(timezone.utc).isoformat()
                new_files.append(file)
                self.processed_files.add(file_id)
                logger.info(f"New file detected: {file['name']} (ID: {file_id})")

        return new_files

    def get_file_details(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific file."""
        try:
            return self.drive_service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, webViewLink, size, createdTime"
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"File not found: {file_id}")
                return None
            logger.error(f"Error getting file details: {str(e)}")
            raise

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "is_running": self._is_connected,
            "folder_id": self.folder_id,
            "last_check": self.last_check_time,
            "files_processed": len(self.processed_files)
        }

    def reset_processed_files(self) -> None:
        """Clear the set of processed files."""
        self.processed_files.clear()
        logger.info("Processed files cache cleared")