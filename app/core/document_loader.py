"""
Document loading and processing utilities.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import markdown
from dataclasses import dataclass


@dataclass
class Document:
    """Represents a processed document."""
    path: str
    content: str
    metadata: Dict[str, Any]


def read_markdown_file(file_path: Path) -> Optional[Document]:
    """Read and parse a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title from first header
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem
        
        # Extract sections based on headers
        sections = []
        current_section = {"title": "Introduction", "content": ""}
        
        for line in content.split('\n'):
            if line.startswith('#') and not line.startswith('```'):
                if current_section["content"].strip():
                    sections.append(current_section)
                level = len(line) - len(line.lstrip('#'))
                current_section = {
                    "title": line.strip('# '),
                    "content": "",
                    "level": level
                }
            else:
                current_section["content"] += line + '\n'
        
        if current_section["content"].strip():
            sections.append(current_section)
        
        return Document(
            path=str(file_path),
            content=content,
            metadata={
                "title": title,
                "sections": sections,
                "word_count": len(content.split()),
                "last_modified": os.path.getmtime(file_path)
            }
        )
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def load_documents(docs_path: str = "docs") -> List[Document]:
    """Load all markdown documents from the docs directory."""
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        raise FileNotFoundError(f"Documents directory not found: {docs_path}")
    
    documents = []
    for md_file in docs_dir.rglob("*.md"):
        doc = read_markdown_file(md_file)
        if doc:
            documents.append(doc)
    
    return documents
