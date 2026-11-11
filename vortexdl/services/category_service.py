"""Automatic destination routing for downloads."""
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit

from vortexdl.core.models import CategoryRule


class CategoryRoutingService:
    """Choose a configured destination while respecting explicit user folders."""

    def __init__(self):
        self._default_rules = (
            CategoryRule(
                name="Music",
                extensions=[".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma"],
                folder="",
                content_types=["audio/"],
            ),
            CategoryRule(
                name="Video",
                extensions=[".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpeg", ".mpg"],
                folder="",
                content_types=["video/"],
            ),
            CategoryRule(
                name="Documents",
                extensions=[".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md",
                            ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".csv"],
                folder="",
                content_types=["application/pdf", "application/msword",
                               "application/vnd.", "text/"],
            ),
        )

    @staticmethod
    def _expand(path):
        return str(Path(path).expanduser()) if path else ""

    def rules_from_settings(self, settings):
        settings = settings or {}
        return tuple(
            CategoryRule(
                name=rule.name,
                extensions=list(rule.extensions),
                folder=self._expand(settings.get(key, "")),
                content_types=list(rule.content_types),
            )
            for rule, key in zip(
                self._default_rules,
                ("music_folder", "video_folder", "documents_folder"),
            )
        )

    @staticmethod
    def _candidate_extensions(url="", title="", media_format="", available_formats=()):
        extensions = []
        for candidate in (title, url):
            if not candidate:
                continue
            path = urlsplit(candidate).path if "://" in candidate else candidate
            ext = os.path.splitext(path)[1].lower()
            if ext:
                extensions.append(ext)
        # The requested output type takes precedence over alternate formats
        # offered by the extractor (which often include both audio and video).
        if media_format == "audio":
            extensions.extend((".mp3", ".m4a"))
        elif media_format == "video":
            extensions.extend((".mp4", ".mkv"))
        for fmt in available_formats or ():
            fmt = str(fmt).strip().lower().lstrip(".")
            if fmt and fmt.isalnum():
                extensions.append("." + fmt)
        return tuple(dict.fromkeys(extensions))

    @staticmethod
    def _matches(rule, extensions, content_type):
        if any(ext in rule.extensions for ext in extensions):
            return True
        if content_type:
            content_type = content_type.lower()
            return any(
                content_type == marker or content_type.startswith(marker)
                for marker in rule.content_types
            )
        return False

    def match_rule(self, url="", title="", media_format="", available_formats=(),
                   content_type="", settings=None):
        """Return the matched configured rule, or None if no type is recognized."""
        settings = settings or {}
        extensions = self._candidate_extensions(
            url=url, title=title, media_format=media_format,
            available_formats=available_formats,
        )
        if not content_type:
            for ext in extensions:
                guessed, _encoding = mimetypes.guess_type("download" + ext)
                if guessed:
                    content_type = guessed
                    break

        rules = self.rules_from_settings(settings)
        # Direct file extensions take precedence; then use MIME type hints.
        for ext in extensions:
            for rule in rules:
                if ext in rule.extensions:
                    return rule
        for rule in rules:
            if self._matches(rule, (), content_type):
                return rule
        return None

    def resolve_output_dir(
        self, *, url="", title="", media_format="", available_formats=(),
        content_type="", default_folder="", manual_folder="", settings=None,
    ):
        """Resolve a destination; explicit user-selected folders always win."""
        if manual_folder:
            return self._expand(manual_folder)
        settings = settings or {}
        if not settings.get("smart_categories_enabled", False):
            return self._expand(default_folder)
        rule = self.match_rule(
            url=url, title=title, media_format=media_format,
            available_formats=available_formats, content_type=content_type,
            settings=settings,
        )
        return self._expand(rule.folder) if rule and rule.folder else self._expand(default_folder)
