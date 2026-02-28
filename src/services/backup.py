# src/services/backup.py
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
import aiofiles
import boto3
from botocore.exceptions import ClientError
import tarfile
import shutil
from src.services.monitoring import logger
from src.core.config import settings

class BackupService:
    """Automated backup and recovery service"""
    
    def __init__(self):
        self.backup_dir = Path("/backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # S3 client for cloud storage
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.S3_BACKUP_BUCKET
        
        # Retention policy
        self.retention = {
            "hourly": 24,  # Keep 24 hourly backups
            "daily": 30,    # Keep 30 daily backups
            "weekly": 12,   # Keep 12 weekly backups
            "monthly": 12   # Keep 12 monthly backups
        }
    
    async def create_backup(self, backup_type: str = "hourly") -> Dict:
        """Create a full system backup"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}_{backup_type}"
        
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)
        
        results = {}
        
        # 1. Backup PostgreSQL database
        db_backup = await self.backup_database(backup_path)
        results["database"] = db_backup
        
        # 2. Backup Redis data
        redis_backup = await self.backup_redis(backup_path)
        results["redis"] = redis_backup
        
        # 3. Backup uploaded files
        files_backup = await self.backup_uploaded_files(backup_path)
        results["files"] = files_backup
        
        # 4. Backup configuration
        config_backup = await self.backup_config(backup_path)
        results["config"] = config_backup
        
        # 5. Create manifest
        manifest = await self.create_manifest(backup_path, backup_type, results)
        results["manifest"] = manifest
        
        # 6. Compress backup
        archive_path = await self.compress_backup(backup_path, backup_id)
        
        # 7. Upload to S3
        s3_result = await self.upload_to_s3(archive_path, backup_id, backup_type)
        
        # 8. Clean up local backup
        shutil.rmtree(backup_path)
        os.remove(archive_path)
        
        # 9. Apply retention policy
        await self.apply_retention_policy(backup_type)
        
        logger.info(f"Backup completed: {backup_id}")
        
        return {
            "backup_id": backup_id,
            "type": backup_type,
            "timestamp": timestamp,
            "results": results,
            "s3_upload": s3_result,
            "size": os.path.getsize(archive_path) if os.path.exists(archive_path) else 0
        }
    
    async def backup_database(self, backup_path: Path) -> Dict:
        """Backup PostgreSQL database"""
        db_file = backup_path / "database.sql"
        
        # Use pg_dump
        cmd = [
            "pg_dump",
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}/{settings.DB_NAME}",
            "-f", str(db_file),
            "--format=custom"  # Custom format for better compression
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "status": "success",
                    "file": str(db_file),
                    "size": os.path.getsize(db_file)
                }
            else:
                return {
                    "status": "failed",
                    "error": stderr.decode()
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def backup_redis(self, backup_path: Path) -> Dict:
        """Backup Redis data"""
        redis_file = backup_path / "redis.rdb"
        
        # Use redis-cli to trigger save and copy RDB
        try:
            # Trigger SAVE
            process = await asyncio.create_subprocess_exec(
                "redis-cli", "SAVE",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            # Copy RDB file
            import shutil
            shutil.copy("/var/lib/redis/dump.rdb", redis_file)
            
            return {
                "status": "success",
                "file": str(redis_file),
                "size": os.path.getsize(redis_file)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def backup_uploaded_files(self, backup_path: Path) -> Dict:
        """Backup uploaded files directory"""
        files_dir = backup_path / "uploads"
        files_dir.mkdir(exist_ok=True)
        
        try:
            # Copy uploads directory
            import shutil
            shutil.copytree("/app/uploads", files_dir, dirs_exist_ok=True)
            
            # Calculate total size
            total_size = sum(
                f.stat().st_size for f in files_dir.rglob('*') if f.is_file()
            )
            
            return {
                "status": "success",
                "path": str(files_dir),
                "file_count": len(list(files_dir.rglob('*'))),
                "total_size": total_size
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def backup_config(self, backup_path: Path) -> Dict:
        """Backup configuration files"""
        config_file = backup_path / "config.env"
        
        try:
            # Copy .env file (redact secrets)
            async with aiofiles.open(".env", "r") as src:
                async with aiofiles.open(config_file, "w") as dst:
                    async for line in src:
                        if any(secret in line.lower() for secret in ["password", "secret", "key"]):
                            key, _ = line.strip().split("=", 1)
                            await dst.write(f"{key}=REDACTED\n")
                        else:
                            await dst.write(line)
            
            return {
                "status": "success",
                "file": str(config_file),
                "size": os.path.getsize(config_file)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def create_manifest(self, backup_path: Path, backup_type: str, results: Dict) -> Dict:
        """Create backup manifest"""
        manifest = {
            "backup_id": backup_path.name,
            "type": backup_type,
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0",
            "components": results,
            "retention_policy": self.retention
        }
        
        import json
        manifest_file = backup_path / "manifest.json"
        async with aiofiles.open(manifest_file, "w") as f:
            await f.write(json.dumps(manifest, indent=2))
        
        return {
            "file": str(manifest_file),
            "size": os.path.getsize(manifest_file)
        }
    
    async def compress_backup(self, backup_path: Path, backup_id: str) -> Path:
        """Compress backup directory"""
        archive_path = self.backup_dir / f"{backup_id}.tar.gz"
        
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_path, arcname=backup_id)
        
        return archive_path
    
    async def upload_to_s3(self, archive_path: Path, backup_id: str, backup_type: str) -> Dict:
        """Upload backup to S3"""
        try:
            # Upload with metadata
            self.s3.upload_file(
                str(archive_path),
                self.bucket_name,
                f"backups/{backup_type}/{backup_id}.tar.gz",
                ExtraArgs={
                    "Metadata": {
                        "backup_id": backup_id,
                        "type": backup_type,
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            return {
                "status": "success",
                "bucket": self.bucket_name,
                "key": f"backups/{backup_type}/{backup_id}.tar.gz"
            }
        except ClientError as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def apply_retention_policy(self, backup_type: str):
        """Delete old backups based on retention policy"""
        try:
            # List backups in S3
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"backups/{backup_type}/"
            )
            
            if "Contents" not in response:
                return
            
            # Sort by last modified
            backups = sorted(
                response["Contents"],
                key=lambda x: x["LastModified"],
                reverse=True
            )
            
            # Keep only the most recent N backups
            keep_count = self.retention.get(backup_type, 10)
            
            if len(backups) > keep_count:
                for backup in backups[keep_count:]:
                    self.s3.delete_object(
                        Bucket=self.bucket_name,
                        Key=backup["Key"]
                    )
                    logger.info(f"Deleted old backup: {backup['Key']}")
        
        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}")
    
    async def restore_from_backup(self, backup_id: str, components: List[str] = None):
        """Restore system from backup"""
        logger.warning(f"Starting restore from backup: {backup_id}")
        
        # Download from S3
        local_path = self.backup_dir / f"{backup_id}.tar.gz"
        
        try:
            # Find backup in S3
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"backups/"
            )
            
            backup_key = None
            for obj in response.get("Contents", []):
                if backup_id in obj["Key"]:
                    backup_key = obj["Key"]
                    break
            
            if not backup_key:
                raise Exception(f"Backup {backup_id} not found")
            
            # Download
            self.s3.download_file(
                self.bucket_name,
                backup_key,
                str(local_path)
            )
            
            # Extract
            with tarfile.open(local_path, "r:gz") as tar:
                tar.extractall(self.backup_dir)
            
            extracted_path = self.backup_dir / backup_id
            
            # Restore components
            results = {}
            
            if not components or "database" in components:
                results["database"] = await self.restore_database(extracted_path)
            
            if not components or "redis" in components:
                results["redis"] = await self.restore_redis(extracted_path)
            
            if not components or "files" in components:
                results["files"] = await self.restore_files(extracted_path)
            
            if not components or "config" in components:
                results["config"] = await self.restore_config(extracted_path)
            
            # Cleanup
            shutil.rmtree(extracted_path)
            os.remove(local_path)
            
            logger.info(f"Restore completed: {backup_id}")
            
            return {
                "status": "success",
                "backup_id": backup_id,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def restore_database(self, backup_path: Path) -> Dict:
        """Restore database from backup"""
        db_file = backup_path / "database.sql"
        
        if not db_file.exists():
            return {"status": "skipped", "reason": "Database backup not found"}
        
        # Use pg_restore
        cmd = [
            "pg_restore",
            "--clean",  # Clean (drop) database objects before recreating
            "--if-exists",
            "--dbname",
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}/{settings.DB_NAME}",
            str(db_file)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {"status": "success"}
            else:
                return {
                    "status": "failed",
                    "error": stderr.decode()
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def restore_redis(self, backup_path: Path) -> Dict:
        """Restore Redis from backup"""
        redis_file = backup_path / "redis.rdb"
        
        if not redis_file.exists():
            return {"status": "skipped", "reason": "Redis backup not found"}
        
        try:
            # Stop Redis, copy RDB, start Redis
            await asyncio.create_subprocess_exec("systemctl", "stop", "redis")
            shutil.copy(redis_file, "/var/lib/redis/dump.rdb")
            await asyncio.create_subprocess_exec("systemctl", "start", "redis")
            
            return {"status": "success"}
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def restore_files(self, backup_path: Path) -> Dict:
        """Restore uploaded files"""
        files_backup = backup_path / "uploads"
        
        if not files_backup.exists():
            return {"status": "skipped", "reason": "Files backup not found"}
        
        try:
            # Restore uploads directory
            shutil.rmtree("/app/uploads")
            shutil.copytree(files_backup, "/app/uploads")
            
            return {"status": "success"}
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def restore_config(self, backup_path: Path) -> Dict:
        """Restore configuration"""
        config_file = backup_path / "config.env"
        
        if not config_file.exists():
            return {"status": "skipped", "reason": "Config backup not found"}
        
        try:
            # Restore .env (manually review first!)
            shutil.copy(config_file, ".env.restore")
            
            return {
                "status": "warning",
                "message": "Config restored to .env.restore - review before using"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }