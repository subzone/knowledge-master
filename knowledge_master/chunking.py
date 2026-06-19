"""Smart chunking engine - splits text by structure (headings, functions, paragraphs)."""

import hashlib
import re


def chunk_id(source: str, index: int) -> str:
    """Deterministic chunk ID from source path and position."""
    return hashlib.md5(f"{source}:{index}".encode()).hexdigest()


def chunk_markdown(text: str, max_tokens: int = 512) -> list[dict]:
    """Split markdown by headings, keeping sections together."""
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # If section is too long, split by paragraphs
        if len(section.split()) > max_tokens:
            paragraphs = section.split("\n\n")
            buffer = ""
            for para in paragraphs:
                if len((buffer + para).split()) > max_tokens and buffer:
                    chunks.append(buffer.strip())
                    buffer = para
                else:
                    buffer = buffer + "\n\n" + para if buffer else para
            if buffer.strip():
                chunks.append(buffer.strip())
        else:
            chunks.append(section)
    return chunks


def chunk_code(text: str, language: str = "", max_tokens: int = 400) -> list[dict]:
    """Split code by function/class boundaries or fixed blocks."""
    # Try to split by top-level definitions
    patterns = {
        "python": r"(?=^(?:def |class |async def ))",
        "typescript": r"(?=^(?:export |function |class |const \w+ = ))",
        "rust": r"(?=^(?:fn |pub fn |impl |struct |enum ))",
        "go": r"(?=^(?:func ))",
    }
    pattern = patterns.get(language)
    if pattern:
        parts = re.split(pattern, text, flags=re.MULTILINE)
    else:
        # Fall back to splitting by blank lines / large gaps
        parts = re.split(r"\n{3,}", text)

    chunks = []
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len((buffer + part).split()) > max_tokens and buffer:
            chunks.append(buffer.strip())
            buffer = part
        else:
            buffer = buffer + "\n\n" + part if buffer else part
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


def chunk_text(text: str, max_tokens: int = 512) -> list[str]:
    """Generic text chunking by paragraphs."""
    paragraphs = text.split("\n\n")
    chunks = []
    buffer = ""
    for para in paragraphs:
        if len((buffer + para).split()) > max_tokens and buffer:
            chunks.append(buffer.strip())
            buffer = para
        else:
            buffer = buffer + "\n\n" + para if buffer else para
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".tf": "terraform",
    ".md": "markdown",
    ".markdown": "markdown",
}


def chunk_file(text: str, extension: str, max_tokens: int = 512) -> list[str]:
    """Route to appropriate chunker based on file extension."""
    lang = LANGUAGE_MAP.get(extension, "")
    if lang == "markdown":
        return chunk_markdown(text, max_tokens)
    elif lang:
        return chunk_code(text, lang, max_tokens)
    else:
        return chunk_text(text, max_tokens)
