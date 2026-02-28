# src/services/file_upload.py
import aiofiles
import os
from pathlib import Path
from fastapi import UploadFile, HTTPException
from typing import List, Optional
import magic
import hashlib
from datetime import datetime
import uuid
from PIL import Image
import io
import PyPDF2
from src.services.monitoring import logger

class FileUploadService:
    """File upload and management service"""
    
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.allowed_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif'],
            'document': ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'text/plain'],
            'archive': ['application/zip', 'application/x-tar'],
            'data': ['text/csv', 'application/json', 'application/xml']
        }
        
        # Create upload directory if not exists
        self.upload_dir.mkdir(exist_ok=True)
        
        # Subdirectories for different purposes
        self.ticket_dir = self.upload_dir / "tickets"
        self.equipment_dir = self.upload_dir / "equipment"
        self.temp_dir = self.upload_dir / "temp"
        
        for dir_path in [self.ticket_dir, self.equipment_dir, self.temp_dir]:
            dir_path.mkdir(exist_ok=True)
    
    async def validate_file(self, file: UploadFile) -> bool:
        """Validate file size and type"""
        # Check file size
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        
        if size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {self.max_file_size / 1024 / 1024}MB"
            )
        
        # Check file type
        content = await file.read(1024)
        mime = magic.from_buffer(content, mime=True)
        file.file.seek(0)
        
        allowed = any(mime in types for types in self.allowed_types.values())
        
        if not allowed:
            raise HTTPException(
                status_code=400,
                detail=f"File type {mime} not allowed"
            )
        
        return True
    
    async def save_upload(self, file: UploadFile, purpose: str, metadata: dict) -> dict:
        """Save uploaded file with metadata"""
        await self.validate_file(file)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{file_ext}"
        
        # Determine subdirectory
        if purpose == "ticket":
            save_dir = self.ticket_dir
        elif purpose == "equipment":
            save_dir = self.equipment_dir
        else:
            save_dir = self.temp_dir
        
        file_path = save_dir / filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Get file info
        stat = os.stat(file_path)
        
        # Process based on file type
        preview = None
        if file.content_type.startswith('image/'):
            preview = await self.generate_image_preview(file_path)
        elif file.content_type == 'application/pdf':
            preview = await self.extract_pdf_preview(file_path)
        
        file_info = {
            "id": file_id,
            "original_filename": file.filename,
            "stored_filename": filename,
            "path": str(file_path),
            "size": stat.st_size,
            "mime_type": file.content_type,
            "hash": file_hash,
            "purpose": purpose,
            "metadata": metadata,
            "preview": preview,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"File uploaded: {filename} ({purpose})")
        
        return file_info
    
    async def generate_image_preview(self, file_path: Path) -> str:
        """Generate thumbnail preview for images"""
        try:
            with Image.open(file_path) as img:
                # Create thumbnail
                img.thumbnail((200, 200))
                
                # Save to bytes
                thumb_bytes = io.BytesIO()
                img.save(thumb_bytes, format='JPEG')
                
                # Return as base64 for embedding
                import base64
                return f"data:image/jpeg;base64,{base64.b64encode(thumb_bytes.getvalue()).decode()}"
        except:
            return None
    
    async def extract_pdf_preview(self, file_path: Path) -> str:
        """Extract first page preview from PDF"""
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                if len(pdf_reader.pages) > 0:
                    first_page = pdf_reader.pages[0]
                    text = first_page.extract_text()
                    return text[:500] + "..." if len(text) > 500 else text
        except:
            return None
    
    async def get_file(self, file_id: str) -> Optional[dict]:
        """Get file info by ID"""
        # Search in all directories
        for dir_path in [self.ticket_dir, self.equipment_dir, self.temp_dir]:
            for file_path in dir_path.glob(f"{file_id}.*"):
                if file_path.exists():
                    stat = os.stat(file_path)
                    return {
                        "id": file_id,
                        "path": str(file_path),
                        "filename": file_path.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    }
        return None
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file by ID"""
        file_info = await self.get_file(file_id)
        if file_info:
            os.remove(file_info["path"])
            logger.info(f"File deleted: {file_id}")
            return True
        return False
    
    async def attach_to_ticket(self, ticket_id: int, file_id: str):
        """Attach file to support ticket"""
        async with get_db() as db:
            await crud.attach_file_to_ticket(db, ticket_id, file_id)
        
        # Move file to ticket directory if not already there
        file_info = await self.get_file(file_id)
        if file_info and self.temp_dir.name in file_info["path"]:
            current_path = Path(file_info["path"])
            new_path = self.ticket_dir / current_path.name
            os.rename(current_path, new_path)