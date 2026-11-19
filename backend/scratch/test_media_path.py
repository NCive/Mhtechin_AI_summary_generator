from app.services.meeting_service import get_media_path
from fastapi import HTTPException

try:
    get_media_path('nonexistent')
except HTTPException as e:
    print('HTTPException', e.status_code, e.detail)
