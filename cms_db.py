"""Supabase persistence for CMS (pages, blog, media)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from config import supabase_client, supabase_service_client

logger = logging.getLogger(__name__)


def get_cms_admin_client():
    """Service role client for CMS writes (bypasses RLS). Falls back to anon if unset."""
    if supabase_service_client:
        return supabase_service_client
    if supabase_client:
        logger.warning(
            "SUPABASE_SERVICE_ROLE_KEY not set; CMS writes use anon key and may fail RLS. "
            "Add the service role key to your .env for full CMS support."
        )
        return supabase_client
    raise RuntimeError("Supabase is not configured")


def get_cms_public_client():
    """Anon client for published content only (RLS)."""
    if not supabase_client:
        raise RuntimeError("Supabase is not configured")
    return supabase_client


def slugify(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "page"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Pages ---

def cms_list_pages() -> list[dict]:
    try:
        res = (
            get_cms_admin_client()
            .table("cms_pages")
            .select("*")
            .order("updated_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("cms_list_pages: %s", e)
        return []


def cms_get_page(page_id: str) -> Optional[dict]:
    try:
        res = (
            get_cms_admin_client()
            .table("cms_pages")
            .select("*")
            .eq("id", page_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_get_page: %s", e)
        return None


def cms_get_published_by_slug(slug: str) -> Optional[dict]:
    try:
        res = (
            get_cms_public_client()
            .table("cms_pages")
            .select("id,slug,title,status,blocks,meta,updated_at")
            .eq("slug", slug)
            .eq("status", "published")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_get_published_by_slug: %s", e)
        return None


def cms_create_page(
    title: str,
    slug: str,
    blocks: list | None = None,
    status: str = "draft",
    meta: dict | None = None,
) -> Optional[dict]:
    slug = slugify(slug)
    row = {
        "title": title,
        "slug": slug,
        "status": status,
        "blocks": blocks or [],
        "meta": meta if meta is not None else {"shell": True, "theme": "light"},
        "updated_at": _now_iso(),
    }
    try:
        res = get_cms_admin_client().table("cms_pages").insert(row).select("*").execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.error("cms_create_page: %s", e)
        raise


def cms_update_page(page_id: str, data: dict) -> Optional[dict]:
    data = {k: v for k, v in data.items() if v is not None or k in ("blocks", "meta")}
    data["updated_at"] = _now_iso()
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    try:
        res = (
            get_cms_admin_client()
            .table("cms_pages")
            .update(data)
            .eq("id", page_id)
            .select("*")
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_update_page: %s", e)
        raise


def cms_delete_page(page_id: str) -> bool:
    try:
        get_cms_admin_client().table("cms_pages").delete().eq("id", page_id).execute()
        return True
    except Exception as e:
        logger.error("cms_delete_page: %s", e)
        return False


def cms_duplicate_page(page_id: str) -> Optional[dict]:
    src = cms_get_page(page_id)
    if not src:
        return None
    base = src["slug"] + "-copy"
    slug = base
    n = 1
    existing = {p["slug"] for p in cms_list_pages()}
    while slug in existing:
        n += 1
        slug = f"{base}-{n}"
    return cms_create_page(
        title=(src.get("title") or "Page") + " (Copy)",
        slug=slug,
        blocks=src.get("blocks") or [],
        status="draft",
        meta=src.get("meta") or {"shell": True, "theme": "light"},
    )


# --- Blog ---

def cms_list_blog_posts() -> list[dict]:
    try:
        res = (
            get_cms_admin_client()
            .table("cms_blog_posts")
            .select("*")
            .order("updated_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("cms_list_blog_posts: %s", e)
        return []


def cms_get_blog_post(post_id: str) -> Optional[dict]:
    try:
        res = (
            get_cms_admin_client()
            .table("cms_blog_posts")
            .select("*")
            .eq("id", post_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_get_blog_post: %s", e)
        return None


def cms_create_blog_post(
    title: str,
    slug: str,
    content: str = "",
    featured_image_url: str | None = None,
    status: str = "draft",
) -> Optional[dict]:
    row = {
        "title": title,
        "slug": slugify(slug),
        "content": content,
        "featured_image_url": featured_image_url,
        "status": status,
        "updated_at": _now_iso(),
    }
    try:
        res = get_cms_admin_client().table("cms_blog_posts").insert(row).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.error("cms_create_blog_post: %s", e)
        raise


def cms_update_blog_post(post_id: str, data: dict) -> Optional[dict]:
    data = {k: v for k, v in data.items() if v is not None or k in ("content", "featured_image_url")}
    data["updated_at"] = _now_iso()
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    try:
        res = (
            get_cms_admin_client()
            .table("cms_blog_posts")
            .update(data)
            .eq("id", post_id)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_update_blog_post: %s", e)
        raise


def cms_delete_blog_post(post_id: str) -> bool:
    try:
        get_cms_admin_client().table("cms_blog_posts").delete().eq("id", post_id).execute()
        return True
    except Exception as e:
        logger.error("cms_delete_blog_post: %s", e)
        return False


def cms_get_published_blog_slug(slug: str) -> Optional[dict]:
    try:
        res = (
            get_cms_public_client()
            .table("cms_blog_posts")
            .select("*")
            .eq("slug", slug)
            .eq("status", "published")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("cms_get_published_blog_slug: %s", e)
        return None


# --- Media ---

def cms_list_media(limit: int = 200) -> list[dict]:
    try:
        res = (
            get_cms_admin_client()
            .table("cms_media")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("cms_list_media: %s", e)
        return []


def cms_create_media(filename: str, url: str, mime_type: str | None = None, file_size: int = 0) -> Optional[dict]:
    row = {
        "filename": filename,
        "url": url,
        "mime_type": mime_type,
        "file_size": file_size,
    }
    try:
        res = get_cms_admin_client().table("cms_media").insert(row).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.error("cms_create_media: %s", e)
        raise
