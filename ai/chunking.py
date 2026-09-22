from __future__ import annotations


def chunk_text(text: str, size: int = 450, overlap: int = 60) -> list[str]:
    """Line-aware chunking so 'Label: value' lines stay intact."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " "]
        )
        return [c.strip() for c in splitter.split_text(text) if c.strip()]
    except ImportError:
        chunks, buf = [], ""
        for line in text.splitlines():
            if len(buf) + len(line) > size and buf:
                chunks.append(buf.strip())
                buf = buf[-overlap:]
            buf += line + "\n"
        if buf.strip():
            chunks.append(buf.strip())
        return chunks
