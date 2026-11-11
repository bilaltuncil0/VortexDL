undefined

@dataclass
class CategoryRule:
    """Route a downloaded file to a folder based on extension or content type."""
    name: str
    extensions: list[str] = field(default_factory=list)
    folder: str = ""
    content_types: list[str] = field(default_factory=list)
