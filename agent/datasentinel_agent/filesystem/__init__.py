"""File metadata collection: size, timestamps, owner, permissions, MIME type,
and streaming SHA-256 hashing.
"""

from datasentinel_agent.filesystem.metadata import collect_metadata, sha256_file
from datasentinel_agent.filesystem.mime import detect_mime_type

__all__ = ["collect_metadata", "sha256_file", "detect_mime_type"]
