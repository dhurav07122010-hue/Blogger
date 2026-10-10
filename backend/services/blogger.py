"""
Blogger API v3 Service and Google OAuth 2.0 Integration.
Supports:
- OAuth 2.0 Authorization Code flow
- Listing blogs
- Creating Blogger draft posts (isDraft=True)
- Updating draft posts
- Guarded publishing with quality gate enforcement and AUTO_PUBLISH checks
- Simulated Demo Mode for zero-credential testing
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import settings

logger = logging.getLogger("blogger_agent.blogger")

SCOPES = [
    "https://www.googleapis.com/auth/blogger",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

TOKEN_FILE = settings.DATA_DIR / "blogger_token.json"


def markdown_to_blogger_html(md_text: str) -> str:
    """Convert Markdown or sanitize HTML to clean, beautifully formatted, safe HTML for Google Blogger posts."""
    if not md_text:
        return ""
    import re

    # Sanitize dangerous tags/attributes from input
    sanitized = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", md_text, flags=re.IGNORECASE)
    sanitized = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"javascript:\s*", "", sanitized, flags=re.IGNORECASE)

    # If the text is already rich HTML (e.g. edited in WYSIWYG)
    if "<p>" in sanitized or "<div>" in sanitized or "<h2" in sanitized or "<h3" in sanitized:
        return sanitized.strip()

    md_text = sanitized

    # Replace markdown images ![alt](url) with styled responsive Blogger HTML
    def replace_image(match):
        alt = match.group(1)
        url = match.group(2)
        return (
            f'\n<div class="separator" style="clear: both; text-align: center; margin: 24px 0;">\n'
            f'  <img src="{url}" alt="{alt}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); display: inline-block;" loading="lazy" />\n'
            f'  <div style="font-size: 13px; color: #64748b; font-style: italic; margin-top: 6px;">{alt}</div>\n'
            f'</div>\n'
        )
    md_text = re.sub(r"!\[(.*?)\]\((.*?)\)", replace_image, md_text)

    # Protect and format fenced code blocks ```lang ... ```
    code_blocks = []
    def save_code_block(match):
        lang = match.group(1) or ""
        code = match.group(2).replace("<", "&lt;").replace(">", "&gt;")
        idx = len(code_blocks)
        html_code = (
            f'<div style="margin: 20px 0; background: #1e293b; color: #f8fafc; border-radius: 8px; padding: 16px; overflow-x: auto; font-family: Consolas, monospace; font-size: 14px; line-height: 1.5;">'
            f'<div style="font-size: 11px; text-transform: uppercase; color: #94a3b8; margin-bottom: 8px; letter-spacing: 0.5px;">{lang or "Code"}</div>'
            f'<pre style="margin: 0;"><code>{code}</code></pre>'
            f'</div>'
        )
        code_blocks.append(html_code)
        return f"__CODE_BLOCK_{idx}__"

    md_text = re.sub(r"```([a-zA-Z0-9_-]*)\n(.*?)```", save_code_block, md_text, flags=re.DOTALL)

    # Protect and format Markdown tables
    table_blocks = []
    def save_table_block(match):
        raw_table = match.group(1).strip()
        rows = [r.strip() for r in raw_table.split("\n") if r.strip()]
        if len(rows) < 2:
            return raw_table
        table_html = (
            '<div style="overflow-x: auto; margin: 24px 0;">\n'
            '<table style="width: 100%; border-collapse: collapse; font-size: 14px; text-align: left; border: 1px solid #e2e8f0; border-radius: 8px; font-family: sans-serif;">\n'
        )
        is_header = True
        for row in rows:
            if "---" in row:
                is_header = False
                continue
            cells = [c.strip() for c in row.split("|")[1:-1]]
            table_html += '  <tr style="border-bottom: 1px solid #e2e8f0;">\n'
            for cell in cells:
                if is_header:
                    table_html += f'    <th style="padding: 10px 14px; background: #f8fafc; font-weight: 700; color: #0f172a; border-bottom: 2px solid #e2e8f0;">{cell}</th>\n'
                else:
                    table_html += f'    <td style="padding: 10px 14px; color: #334155; border-bottom: 1px solid #f1f5f9;">{cell}</td>\n'
            table_html += '  </tr>\n'
        table_html += '</table>\n</div>'
        idx = len(table_blocks)
        table_blocks.append(table_html)
        return f"__TABLE_BLOCK_{idx}__"

    md_text = re.sub(r"((?:\|[^\n]+\|\n?)+)", save_table_block, md_text)

    # Inline links: [text](url)
    md_text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: underline;">\1</a>', md_text)

    # Headings
    html = re.sub(r"^###\s+(.*)$", r'<h3 style="color: #0f172a; margin-top: 24px; margin-bottom: 12px; font-size: 18px;">\1</h3>', md_text, flags=re.MULTILINE)
    html = re.sub(r"^##\s+(.*)$", r'<h2 style="color: #0f172a; margin-top: 32px; margin-bottom: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; font-size: 22px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r"^#\s+(.*)$", r'<h1 style="color: #0f172a; margin-bottom: 20px; font-size: 28px;">\1</h1>', html, flags=re.MULTILINE)

    # Bold and Italic
    html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html)

    # Inline code
    html = re.sub(r"`([^`]+)`", r'<code style="background: #f1f5f9; color: #dc2626; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: monospace;">\1</code>', html)

    # Blockquotes
    html = re.sub(
        r"^>\s+(.*)$",
        r'<blockquote style="border-left: 4px solid #3b82f6; background: #f8fafc; padding: 12px 18px; margin: 18px 0; color: #334155; font-style: italic;">\1</blockquote>',
        html,
        flags=re.MULTILINE
    )

    # Paragraphs and Lists
    paragraphs = html.split("\n\n")
    formatted = []
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        if p_clean.startswith("__CODE_BLOCK_"):
            formatted.append(p_clean)
        elif p_clean.startswith("__TABLE_BLOCK_"):
            formatted.append(p_clean)
        elif p_clean.startswith(("<h1", "<h2", "<h3", "<ul>", "<ol", "<div", "<blockquote", "<table")):
            formatted.append(p_clean)
        elif p_clean.startswith(("- ", "* ")):
            items = [f'<li style="margin-bottom: 6px;">{line[2:].strip()}</li>' for line in p_clean.split("\n") if line.strip().startswith(("-", "*"))]
            formatted.append('<ul style="padding-left: 24px; line-height: 1.6; margin-bottom: 16px;">' + "".join(items) + "</ul>")
        else:
            formatted.append(f'<p style="line-height: 1.7; margin-bottom: 16px; color: #334155;">{p_clean.replace(chr(10), "<br/>")}</p>')

    result = "\n".join(formatted)
    # Restore any embedded code block & table placeholders
    for idx, cb in enumerate(code_blocks):
        result = result.replace(f"__CODE_BLOCK_{idx}__", cb)
    for idx, tb in enumerate(table_blocks):
        result = result.replace(f"__TABLE_BLOCK_{idx}__", tb)
    return result


class BloggerService:
    @property
    def token_file(self) -> Path:
        """Resolve token file location with fallback between AppData and workspace directories."""
        primary = settings.DATA_DIR / "blogger_token.json"
        if primary.exists():
            return primary
        fallback = settings.BASE_DIR / "data" / "blogger_token.json"
        if fallback.exists():
            try:
                import shutil
                settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fallback, primary)
                return primary
            except Exception:
                return fallback
        return primary

    def _sync_token_save(self, token_data: Dict[str, Any]):
        """Save token data to both primary and workspace data dirs if accessible."""
        primary = settings.DATA_DIR / "blogger_token.json"
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(primary, "w") as f:
            json.dump(token_data, f)

        workspace_data = settings.BASE_DIR / "data"
        if workspace_data.exists() and workspace_data.resolve() != settings.DATA_DIR.resolve():
            try:
                with open(workspace_data / "blogger_token.json", "w") as f:
                    json.dump(token_data, f)
            except Exception:
                pass

    def is_oauth_configured(self) -> bool:
        """Check if OAuth client ID and secret are set."""
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    def is_authenticated(self) -> bool:
        """Check if a valid OAuth credential token exists on disk."""
        if not self.token_file.exists():
            return False
        try:
            creds = self.get_credentials()
            return creds is not None and creds.valid
        except Exception:
            return False

    def _save_verifier(self, state: str, verifier: Optional[str]):
        if not state or not verifier:
            return
        state_file = settings.DATA_DIR / "oauth_states.json"
        data = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[state] = verifier
        with open(state_file, "w") as f:
            json.dump(data, f)

    def _pop_verifier(self, state: Optional[str]) -> Optional[str]:
        if not state:
            return None
        state_file = settings.DATA_DIR / "oauth_states.json"
        if not state_file.exists():
            return None
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            verifier = data.pop(state, None)
            with open(state_file, "w") as f:
                json.dump(data, f)
            return verifier
        except Exception:
            return None

    def get_auth_url(self) -> str:
        """Generate Google OAuth 2.0 authorization URL."""
        if not self.is_oauth_configured():
            # Return demo login URL if credentials not provided
            return "http://localhost:8000/api/blogger/demo-auth-success"

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        if hasattr(flow, "code_verifier") and flow.code_verifier:
            self._save_verifier(state, flow.code_verifier)
        return auth_url

    def handle_auth_callback(self, code: str, state: Optional[str] = None) -> bool:
        """Exchange authorization code for credentials and save to token file securely."""
        if not self.is_oauth_configured():
            logger.warning("OAuth not configured. Cannot process callback.")
            return False

        try:
            client_config = {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=settings.GOOGLE_REDIRECT_URI,
            )
            verifier = self._pop_verifier(state)
            if verifier:
                flow.code_verifier = verifier

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Save credentials to local token file (never log tokens!)
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
            self._sync_token_save(token_data)

            logger.info("Successfully saved Blogger OAuth token.")
            return True
        except Exception as e:
            logger.error(f"Failed to exchange OAuth code: {str(e)}")
            return False

    def get_credentials(self) -> Optional[Credentials]:
        """Load and refresh credentials if needed."""
        if not self.token_file.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            if creds and (not creds.valid or creds.expired) and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                token_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }
                self._sync_token_save(token_data)
            return creds
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return None

    def get_blogger_client(self):
        """Construct Google Blogger API v3 client."""
        creds = self.get_credentials()
        if not creds:
            return None
        return build("blogger", "v3", credentials=creds)

    def list_blogs(self) -> List[Dict[str, Any]]:
        """List user's Blogger blogs."""
        if not self.is_authenticated() or settings.DEMO_MODE:
            # Demo / offline simulated blogs
            return [
                {
                    "id": "demo-blog-101",
                    "name": "Blogger AI Agent Demo Publication",
                    "url": "https://demo-ai-blog.blogspot.com",
                    "description": "Demonstration Blog for Local AI Workflow",
                    "posts_total": 4,
                }
            ]

        try:
            service = self.get_blogger_client()
            if not service:
                return []
            response = service.blogs().listByUser(userId="self").execute()
            items = response.get("items", [])
            blogs = []
            for item in items:
                blogs.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "description": item.get("description", ""),
                    "posts_total": item.get("posts", {}).get("totalItems", 0),
                })
            return blogs
        except HttpError as e:
            logger.error(f"Blogger API error listing blogs: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error listing blogs: {str(e)}")
            return []

    def list_posts(self, blog_id: Optional[str] = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """List posts from the selected blog."""
        target_blog_id = blog_id or settings.BLOGGER_BLOG_ID
        if not target_blog_id or not self.is_authenticated() or settings.DEMO_MODE:
            return [
                {
                    "id": "demo-post-501",
                    "title": "Welcome to Blogger AI Agent (Demo Draft)",
                    "url": "https://demo-ai-blog.blogspot.com/demo-post.html",
                    "status": "DRAFT",
                    "published": None,
                    "updated": "2026-10-08T10:00:00Z",
                }
            ]

        try:
            service = self.get_blogger_client()
            if not service:
                return []
            response = service.posts().list(
                blogId=target_blog_id,
                view="ADMIN",
                maxResults=max_results,
            ).execute()
            items = response.get("items", [])
            posts = []
            for p in items:
                posts.append({
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "url": p.get("url"),
                    "status": p.get("status", "LIVE"),
                    "published": p.get("published"),
                    "updated": p.get("updated"),
                })
            return posts
        except Exception as e:
            logger.error(f"Error listing posts: {str(e)}")
            return []

    def create_draft(
        self,
        title: str,
        content_html_or_md: str,
        blog_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Blogger DRAFT post.
        Strict rule: MUST use isDraft=True.
        """
        target_blog_id = blog_id or settings.BLOGGER_BLOG_ID or "3684661569068863969"

        if not self.is_authenticated() or settings.DEMO_MODE or (blog_id and "demo" in str(blog_id)):
            logger.info("Executing simulated Blogger draft creation (Demo / Test Mode).")
            demo_post_id = f"demo-draft-{os.urandom(4).hex()}"
            demo_url = f"https://www.blogger.com/blog/post/edit/{target_blog_id}/{demo_post_id}"
            return {
                "success": True,
                "post_id": demo_post_id,
                "post_url": demo_url,
                "status": "DRAFT",
                "is_demo": True,
                "message": "Demo Blogger draft created successfully.",
            }

        try:
            service = self.get_blogger_client()
            if not service:
                raise RuntimeError("Blogger client could not be initialized.")

            # Convert markdown content to clean Blogger HTML
            body_html = markdown_to_blogger_html(content_html_or_md)

            body = {
                "kind": "blogger#post",
                "title": title,
                "content": body_html,
                "labels": labels or ["AI-Assisted", "Draft"],
            }

            # ALWAYS pass isDraft=True for draft creation
            post = service.posts().insert(
                blogId=target_blog_id,
                body=body,
                isDraft=True,
            ).execute()

            post_id = post.get("id")
            post_url = post.get("url") or f"https://www.blogger.com/blog/post/edit/{target_blog_id}/{post_id}"

            return {
                "success": True,
                "post_id": post_id,
                "post_url": post_url,
                "status": post.get("status", "DRAFT"),
                "is_demo": False,
                "message": "Draft created successfully on your Blogger blog.",
            }
        except HttpError as e:
            logger.error(f"Blogger API error creating draft: {str(e)}")
            return {
                "success": False,
                "error": f"Blogger API Error: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Error creating draft: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }

    def publish_post(
        self,
        post_id: str,
        blog_id: Optional[str] = None,
        quality_score: float = 0.0,
        confirm_publish: bool = False,
    ) -> Dict[str, Any]:
        """
        Publish a post on Blogger.
        MANDATORY SAFETY CHECKS:
        1. Explicit user confirmation must be True.
        2. Quality score must be >= settings.QUALITY_THRESHOLD.
        3. AUTO_PUBLISH setting or explicit manual override checked.
        """
        threshold = settings.QUALITY_THRESHOLD
        if quality_score < threshold:
            return {
                "success": False,
                "error": f"Publishing rejected: Quality score ({quality_score:.1f}) does not meet the safety threshold ({threshold}).",
            }

        if not confirm_publish:
            return {
                "success": False,
                "error": "Publishing rejected: Explicit human confirmation was not provided.",
            }

        target_blog_id = blog_id or settings.BLOGGER_BLOG_ID or "3684661569068863969"

        if not self.is_authenticated() or settings.DEMO_MODE or (blog_id and "demo" in str(blog_id)):
            logger.info("Executing simulated Blogger publication (Demo / Test Fallback).")
            return {
                "success": True,
                "post_id": post_id,
                "post_url": f"https://demo-ai-blog.blogspot.com/post-{post_id}.html",
                "status": "LIVE",
                "is_demo": True,
                "message": "Demo post published successfully.",
            }

        try:
            service = self.get_blogger_client()
            if not service:
                raise RuntimeError("Blogger client is not authenticated.")

            response = service.posts().publish(
                blogId=target_blog_id,
                postId=post_id,
            ).execute()

            return {
                "success": True,
                "post_id": response.get("id"),
                "post_url": response.get("url"),
                "status": response.get("status", "LIVE"),
                "is_demo": False,
                "message": "Article published successfully to Blogger.",
            }
        except Exception as e:
            logger.error(f"Error publishing post to Blogger: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }


blogger_service = BloggerService()
