from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user
from api.models import AppUser
from api.schemas import EncryptionKeyResponse, EncryptionKeyUpload

router = APIRouter(prefix="/encryption-keys", tags=["encryption-keys"])


@router.put("/me", response_model=EncryptionKeyResponse)
def upload_encryption_key(payload: EncryptionKeyUpload, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)) -> EncryptionKeyResponse:
    current_user.encryption_public_key = payload.public_key
    current_user.encrypted_private_key_backup = payload.encrypted_private_key_backup
    current_user.encryption_recovery_salt = payload.recovery_salt
    db.commit()
    return EncryptionKeyResponse(**payload.model_dump())


@router.get("/me", response_model=EncryptionKeyResponse)
def get_encryption_key(current_user: AppUser = Depends(get_current_user)) -> EncryptionKeyResponse:
    if not all((current_user.encryption_public_key, current_user.encrypted_private_key_backup, current_user.encryption_recovery_salt)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encryption key not found")
    return EncryptionKeyResponse(public_key=current_user.encryption_public_key, encrypted_private_key_backup=current_user.encrypted_private_key_backup, recovery_salt=current_user.encryption_recovery_salt)
