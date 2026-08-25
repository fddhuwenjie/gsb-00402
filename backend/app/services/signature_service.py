import logging
import os
import uuid
from pathlib import Path, PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.yara_parser import YaraParser
from app.entities.models import SignatureFile
from app.repositories.signature_repository import SignatureRepository
from app.schemas.common import PageResponse
from app.schemas.signature import SignatureFileDTO, SignatureContentDTO

logger = logging.getLogger(__name__)


class SignatureService:
    def __init__(self, db: AsyncSession):
        self.repo = SignatureRepository(db)
        self.parser = YaraParser()

    @staticmethod
    def _validate_upload(filename: str, content: bytes):
        ext = PurePosixPath(filename).suffix.lower()
        if ext not in settings.ALLOWED_SIGNATURE_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(settings.ALLOWED_SIGNATURE_EXTENSIONS))}"
            )

        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File too large ({size_mb:.1f} MB). Maximum: {settings.MAX_FILE_SIZE_MB} MB"
            )

        if not content.strip():
            raise ValueError("File is empty")

    async def upload_signature(
        self, name: str, description: str, filename: str, content: bytes
    ) -> SignatureFileDTO:
        self._validate_upload(filename, content)

        upload_dir = Path(settings.UPLOAD_DIR) / "signatures"
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(filename).stem}{PurePosixPath(filename).suffix}"
        file_path = upload_dir / safe_name
        file_path.write_bytes(content)

        text = content.decode("utf-8", errors="replace")
        rules = self.parser.parse_content(text, source=filename)
        rule_count = len(rules)
        func_count = sum(len(r.signatures) for r in rules)

        sig = SignatureFile(
            name=name,
            original_filename=filename,
            file_path=str(file_path),
            description=description,
            rule_count=rule_count,
            function_count=func_count,
        )
        sig = await self.repo.create(sig)

        logger.info("Uploaded signature file: %s (%d rules, %d functions)", name, rule_count, func_count)
        return SignatureFileDTO.model_validate(sig)

    async def list_signatures(self, page: int = 1, page_size: int = 20) -> PageResponse[SignatureFileDTO]:
        items, total = await self.repo.find_all(page, page_size)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[SignatureFileDTO.model_validate(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_signature_detail(self, sig_id: int) -> SignatureContentDTO:
        sig = await self.repo.find_by_id(sig_id)
        if not sig:
            raise ValueError(f"Signature file not found: {sig_id}")

        rules = self.parser.parse_file(sig.file_path)
        rules_data = []
        for r in rules:
            rules_data.append({
                "name": r.name,
                "description": r.description,
                "total_functions": r.total_functions,
                "signatures": [
                    {"identifier": s.identifier, "pattern": s.pattern, "prefix": s.prefix}
                    for s in r.signatures
                ],
            })

        return SignatureContentDTO(
            id=sig.id,
            name=sig.name,
            original_filename=sig.original_filename,
            description=sig.description,
            rule_count=sig.rule_count,
            function_count=sig.function_count,
            rules=rules_data,
            created_at=sig.created_at,
        )

    async def delete_signature(self, sig_id: int) -> bool:
        sig = await self.repo.find_by_id(sig_id)
        if sig and os.path.exists(sig.file_path):
            os.remove(sig.file_path)
        deleted = await self.repo.delete_by_id(sig_id)
        if deleted:
            logger.info("Deleted signature file: id=%d", sig_id)
        return deleted
