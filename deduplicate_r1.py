import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Reference:
    data: str
    abstract: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None

def extract_references_from_ris(file_path="scopus.ris") -> List[Reference]:
    """Extract references from RIS file with full record data preservation."""
    data = Path(file_path).read_text(encoding="utf-8-sig")
    lines = data.splitlines()

    references = []
    current_ref = Reference(data="")
    entry_lines = []
    reading_entry = False

    for line in lines:
        if line.startswith("TY"):  # Start of new reference
            if reading_entry:  # Handle malformed files
                current_ref.data = "\n".join(entry_lines)
                references.append(current_ref)
            reading_entry = True
            entry_lines = [line]
            current_ref = Reference(data="")
        elif line.startswith("ER"):  # End of reference
            entry_lines.append(line)
            current_ref.data = "\n".join(entry_lines)
            references.append(current_ref)
            reading_entry = False
        elif reading_entry:
            if line.startswith("TI"):
                current_ref.title = line[6:]
            elif line.startswith("AB"):
                current_ref.abstract = line[6:] 
            entry_lines.append(line)
    
    return references

def normalize_title(title: Optional[str]) -> str:
    """Normalize titles for better duplicate detection"""
    if not title:
        return ""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)  # Remove punctuation
    title = re.sub(r'\s+', ' ', title)     # Collapse whitespace
    return title

def deduplicate_references(references: List[Reference]) -> List[Reference]:
    """Deduplicate references by title, prioritizing entries with abstracts."""
    title_groups = {}
    
    # Group references by their title (normalized)
    for ref in references:
        title = normalize_title(ref.title)
        # title = ref.title.strip().lower() or ""  # Handle None as empty string
        # if title.endswith('.'):
        #     title = title[:-1].strip()
        if title not in title_groups:
            title_groups[title] = []
        title_groups[title].append(ref)

    # Select best candidate from each group
    deduped = []
    for group in title_groups.values():
        # Prioritize first occurrence with non-empty abstract
        selected = next((r for r in group if r.abstract and r.abstract.strip()), None)
        # Fallback to first entry in group
        deduped.append(selected if selected else group[0])
    
    return deduped


if __name__ == "__main__":
    input_file = "all.ris"
    output_file = Path(input_file).stem + "_deduplicated.ris"

    references = extract_references_from_ris(input_file)
    print(f"Processing {len(references)} references in {input_file}")
    unique_references = deduplicate_references(references)

    # Write deduplicated references maintaining original RIS format
    with open(output_file, "w", encoding="utf-8") as f:
        for ref in unique_references:
            f.write(ref.data + "\n\n")  # Separate entries with empty line

    print(f"\nSuccess: {len(unique_references)} unique references written to {output_file}")
