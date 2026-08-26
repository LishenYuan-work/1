"""Private document storage with local and Supabase Storage backends."""

import asyncio
from pathlib import Path

from app.core.config import settings


class StorageService:
    async def save(self, path: str, content: bytes, content_type: str) -> str:
        if settings.storage_provider == "supabase":
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RuntimeError("Supabase Storage 未正确配置")
            import urllib.request

            url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{path}"
            request = urllib.request.Request(
                url,
                data=content,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": content_type,
                    "x-upsert": "false",
                },
                method="POST",
            )
            await asyncio.to_thread(urllib.request.urlopen, request, timeout=30)
            return path
        root = settings.local_storage_dir
        target = (root / path).resolve()
        if root != target and root not in target.parents:
            raise ValueError("非法存储路径")
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, content)
        return str(target)

    async def delete(self, path: str) -> None:
        if settings.storage_provider == "supabase":
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RuntimeError("Supabase Storage 未正确配置")
            import json
            import urllib.request

            url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/remove/{settings.supabase_storage_bucket}"
            request = urllib.request.Request(
                url,
                data=json.dumps({"prefixes": [path]}).encode(),
                headers={"Authorization": f"Bearer {settings.supabase_service_role_key}", "Content-Type": "application/json"},
                method="POST",
            )
            await asyncio.to_thread(urllib.request.urlopen, request, timeout=30)
        elif settings.storage_provider == "local":
            target = Path(path).resolve()
            root = settings.local_storage_dir
            if root != target and root not in target.parents:
                raise ValueError("非法存储路径")
            await asyncio.to_thread(target.unlink, missing_ok=True)


storage_service = StorageService()
