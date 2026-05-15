"""
Google Drive integration using Service Account.
Provides a LangChain tool for searching files via the Drive API.
"""

import os
import json
import logging
from typing import Optional
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_TYPE_MAP = {
    "pdf": "application/pdf",
    "doc": "application/vnd.google-apps.document",
    "document": "application/vnd.google-apps.document",
    "google doc": "application/vnd.google-apps.document",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "google sheet": "application/vnd.google-apps.spreadsheet",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "slide": "application/vnd.google-apps.presentation",
    "presentation": "application/vnd.google-apps.presentation",
    "google slide": "application/vnd.google-apps.presentation",
    "image": "image/",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "txt": "text/plain",
    "text": "text/plain",
    "csv": "text/csv",
    "folder": "application/vnd.google-apps.folder",
}


def get_drive_service():
    """Build and return authenticated Google Drive service."""
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

    if sa_json:
        try:
            info = json.loads(sa_json)
        except json.JSONDecodeError:
            # Try treating it as a file path
            with open(sa_json) as f:
                info = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
    elif sa_file:
        credentials = service_account.Credentials.from_service_account_file(
            sa_file, scopes=SCOPES
        )
    else:
        raise ValueError(
            "No service account credentials found. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE."
        )

    return build("drive", "v3", credentials=credentials)


def build_drive_query(
    name: Optional[str] = None,
    name_exact: bool = False,
    file_type: Optional[str] = None,
    full_text: Optional[str] = None,
    modified_after: Optional[str] = None,
    modified_before: Optional[str] = None,
    folder_id: Optional[str] = None,
    extra_conditions: Optional[str] = None,
) -> str:
    """
    Build a Google Drive API q parameter string.

    Args:
        name: File name to search (partial or exact)
        name_exact: If True, uses = instead of contains for name
        file_type: File type string (e.g. 'pdf', 'sheet', 'image')
        full_text: Text to search within file content
        modified_after: ISO datetime string e.g. '2024-01-01T00:00:00'
        modified_before: ISO datetime string
        folder_id: Restrict search to this folder (uses 'in parents')
        extra_conditions: Any raw extra q conditions to append

    Returns:
        Formatted q string for Drive API
    """
    conditions = ["trashed = false"]

    # Folder scope
    target_folder = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if target_folder:
        conditions.append(f"'{target_folder}' in parents")

    # Name filter
    if name:
        escaped = name.replace("'", "\\'")
        if name_exact:
            conditions.append(f"name = '{escaped}'")
        else:
            conditions.append(f"name contains '{escaped}'")

    # MIME type filter
    if file_type:
        ft_lower = file_type.lower().strip()
        mime = MIME_TYPE_MAP.get(ft_lower)
        if mime:
            if mime.endswith("/"):
                # Prefix match for broad types like image/
                conditions.append(f"mimeType contains '{mime}'")
            else:
                conditions.append(f"mimeType = '{mime}'")
        else:
            # Pass through raw mime type if user provided one directly
            if "/" in file_type:
                conditions.append(f"mimeType = '{file_type}'")

    # Full text search
    if full_text:
        escaped = full_text.replace("'", "\\'")
        conditions.append(f"fullText contains '{escaped}'")

    # Date filters
    if modified_after:
        conditions.append(f"modifiedTime > '{modified_after}'")
    if modified_before:
        conditions.append(f"modifiedTime < '{modified_before}'")

    if extra_conditions:
        conditions.append(extra_conditions)

    return " and ".join(conditions)


class DriveSearchInput(BaseModel):
    query: str = Field(
        description=(
            "A fully-formed Google Drive API q parameter string. "
            "Example: \"name contains 'report' and mimeType = 'application/pdf' and trashed = false\""
        )
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of results to return (1-50).",
        ge=1,
        le=50,
    )


@tool("drive_search", args_schema=DriveSearchInput)
def drive_search(query: str, max_results: int = 10) -> str:
    """
    Search Google Drive using a raw Drive API q parameter string.
    Always include \"trashed = false\" in the query.
    Returns a formatted list of matching files with name, type, modified date, and link.
    """
    # Normalize quotes to prevent Groq tool call failures
    query = query.replace('"', "'")
    try:
        service = get_drive_service()
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        if folder_id and "in parents" not in query:
            query = query + " and '" + folder_id + "' in parents"

        results = (
            service.files()
            .list(
                q=query,
               pageSize=min(max_results, 20),
                fields=(
                    "files(id, name, mimeType, modifiedTime, size, "
                    "webViewLink, webContentLink, parents)"
                ),
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = results.get("files", [])

        if not files:
            return "No files found matching your search criteria."

        lines = [f"Found {len(files)} file(s):\n"]
        for i, f in enumerate(files, 1):
            name = f.get("name", "Unknown")
            mime = f.get("mimeType", "")
            modified = f.get("modifiedTime", "")
            view_link = f.get("webViewLink", "")
            size = f.get("size")

            # Human-readable type
            readable_type = _human_readable_mime(mime)

            # Format modified time
            if modified:
                try:
                    dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    modified_str = dt.strftime("%b %d, %Y %H:%M UTC")
                except Exception:
                    modified_str = modified
            else:
                modified_str = "Unknown"

            size_str = ""
            if size:
                size_int = int(size)
                if size_int >= 1_048_576:
                    size_str = f" | Size: {size_int/1_048_576:.1f} MB"
                elif size_int >= 1024:
                    size_str = f" | Size: {size_int/1024:.1f} KB"
                else:
                    size_str = f" | Size: {size_int} B"

            lines.append(
                f"{i}. **{name}**\n"
                f"   Type: {readable_type}{size_str}\n"
                f"   Modified: {modified_str}\n"
                f"   Link: {view_link}\n"
            )

        return "\n".join(lines)

    except HttpError as e:
        logger.error("Drive API error: %s", e)
        return f"Google Drive API error: {e.reason}"
    except Exception as e:
        logger.error("Unexpected error in drive_search: %s", e)
        return f"An error occurred while searching Drive: {str(e)}"


def _human_readable_mime(mime: str) -> str:
    mapping = {
        "application/pdf": "PDF",
        "application/vnd.google-apps.document": "Google Doc",
        "application/vnd.google-apps.spreadsheet": "Google Sheet",
        "application/vnd.google-apps.presentation": "Google Slides",
        "application/vnd.google-apps.folder": "Folder",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel (.xlsx)",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word (.docx)",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint (.pptx)",
        "text/plain": "Text File",
        "text/csv": "CSV",
        "image/jpeg": "JPEG Image",
        "image/png": "PNG Image",
        "image/gif": "GIF Image",
    }
    if mime in mapping:
        return mapping[mime]
    if mime.startswith("image/"):
        return f"Image ({mime.split('/')[-1].upper()})"
    return mime
