"""Domain-specific errors surfaced by download services."""


class VortexDLError(Exception):
    """Base class for expected, user-displayable application errors."""


class DownloadError(VortexDLError):
    """A download failed for a known operational reason."""


class NetworkDownloadError(DownloadError):
    """The remote server or network prevented a download."""


class DiskFullError(DownloadError):
    """The destination filesystem has no free space."""


class OutputDirectoryError(DownloadError):
    """The selected output directory cannot be used."""


class DependencyMissingError(DownloadError):
    """An optional or required external program is unavailable."""


class DownloadCancelled(DownloadError):
    """The user cancelled a task."""
