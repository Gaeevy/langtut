#!/usr/bin/env python3

import re
import json
import argparse
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path, start_page=0, end_page=None):
    """Extract text from specified pages of the PDF file."""
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    if end_page is None:
        end_page = total_pages
    
    print(f"PDF has {total_pages} pages. Extracting from page {start_page+1} to {end_page}")
    
    text = ""
    for i in range(start_page, min(end_page, total_pages)):
        page_text = reader.pages[i].extract_text()
        text += f"\n--- PAGE {i+1} ---\n{page_text}\n"
    
    return text

def preprocess_text(text):
    """
    Preprocess the text to handle examples and translations that are split across lines.
    For example:
    • o seu programa teve um enorme sucesso –
    His program had enormous success.
    
    Should become:
    • o seu programa teve um enorme sucesso – His program had enormous success.
    """
    lines = text.split('\n')
    processed_lines = []
    
    i = 0
    while i < len(lines):
        current_line = lines[i].strip()
        
        # Check if this line ends with "–" (likely split translation)
        if current_line.endswith('–') and i + 1 < len(lines):
            next_line = lines[i+1].strip()
            # Check if the next line doesn't start with a bullet point or a number
            if not next_line.startswith('•') and not re.match(r'^\d+\s+', next_line) and not '|' in next_line:
                # Join the lines
                processed_lines.append(f"{current_line} {next_line}")
                i += 2  # Skip the next line as we've combined it
                continue
                
        processed_lines.append(current_line)
        i += 1
    
    return '\n'.join(processed_lines)

def parse_frequency_entries(text):
    """
    Parse frequency dictionary entries based on the observed format:
    Format: <rank> <word> <pos> <meaning> ... <frequency data>
    
    Example from the PDF:
    "1 o at the (F a) ... 100 | 1675835"
    "2 de prp of, from ... 100 | xxxxxx"
    "17 como cj/av how, like, as ... 100 | xxxxx"
    
    Examples format (potentially multiline):
    "• o mulato não se vê como negro, no entanto
    é identificado como negro – Mulatos don't see
    themselves as black; however, they are identified as black."
    """
    # Preprocess the text to handle split translations
    text = preprocess_text(text)
    
    lines = text.split('\n')
    entries = []
    
    # Pattern for entries that look like: "<rank> <word> <pos> ..."
    # Updated to handle slashes in part of speech (e.g., "cj/av")
    entry_start_pattern = r'^\s*(\d+)\s+(\w+)\s+([a-z]{1,4}(?:/[a-z]{1,4})?)\s+(.+)'
    
    # Pattern for frequency data that looks like: "100 | 1675835"
    frequency_pattern = r'(\d+)\s+\|\s+(\d+)'
    
    # Variables to track the current entry being processed
    current_entry = None
    current_example_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this line starts a new entry
        entry_match = re.match(entry_start_pattern, line)
        if entry_match:
            # If we have a previous entry being processed, add it to entries
            if current_entry:
                # Process any examples collected
                if current_example_lines:
                    process_example(current_entry, current_example_lines)
                # Add the completed entry to our list
                entries.append(current_entry)
            
            # Start new entry
            rank = int(entry_match.group(1))
            word = entry_match.group(2)
            pos = entry_match.group(3)  # part of speech
            meaning = entry_match.group(4).strip()
            
            current_entry = {
                "rank": rank,
                "word": word,
                "part_of_speech": pos,
                "meaning": meaning,
                "examples": [],
                "frequency": None,
                "dispersion": None  # This might be the 100 value
            }

            # Reset example lines for the new entry
            current_example_lines = []
        
        # Check if this line contains frequency data (the last part of the entry)
        elif current_entry and '|' in line:
            # Process any collected example lines before processing frequency
            if current_example_lines:
                process_example(current_entry, current_example_lines)
                current_example_lines = []
            
            # Process frequency data
            freq_match = re.search(frequency_pattern, line)
            if freq_match:
                dispersion = int(freq_match.group(1))
                frequency = int(freq_match.group(2))
                current_entry["dispersion"] = dispersion
                current_entry["frequency"] = frequency
        
        # If line starts with bullet, it's the start of an example
        elif current_entry and line.startswith('•'):
            # If we already have example lines, process them before starting a new example
            if current_example_lines:
                process_example(current_entry, current_example_lines)
            # Start collecting a new example
            current_example_lines = [line.strip('• ')]
        
        # If not a new entry, frequency, or bullet point, append to current example
        elif current_entry:
            current_example_lines.append(line)
    
    # Process any remaining example and add the last entry
    if current_entry:
        if current_example_lines:
            process_example(current_entry, current_example_lines)
        entries.append(current_entry)
    
    return entries

def process_example(entry, example_lines):
    """
    Process a collected multiline example and add it to the entry.
    """
    if not example_lines:
        return
    
    # Join all lines of the example
    full_example = ' '.join(example_lines)
    
    # Split by the dash character to separate Portuguese from English translation
    if '–' in full_example:
        parts = full_example.split('–', 1)
        pt_example = parts[0].strip()
        en_translation = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        
        if en_translation == "":
            en_translation = None
        
        example = {
            "portuguese": pt_example,
            "english": en_translation
        }
    else:
        # If no translation is available
        example = {
            "portuguese": full_example.strip(),
            "english": None
        }
    
    entry["examples"].append(example)

def create_dictionary_metadata(entries):
    """Create metadata about the dictionary."""
    if not entries:
        return {}
    
    # Get the range of ranks
    ranks = [entry["rank"] for entry in entries if "rank" in entry and entry["rank"] is not None]
    min_rank = min(ranks) if ranks else None
    max_rank = max(ranks) if ranks else None
    
    # Get part of speech distribution
    pos_counts = {}
    for entry in entries:
        pos = entry.get("part_of_speech")
        if pos:
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
    
    # Get frequency distribution
    frequencies = [entry["frequency"] for entry in entries if "frequency" in entry and entry["frequency"] is not None]
    min_freq = min(frequencies) if frequencies else None
    max_freq = max(frequencies) if frequencies else None
    
    # Count entries with examples
    entries_with_examples = sum(1 for entry in entries if entry.get("examples"))
    examples_with_translations = sum(1 for entry in entries 
                                     for example in entry.get("examples", [])
                                     if example.get("english") is not None)
    
    return {
        "total_entries": len(entries),
        "rank_range": {"min": min_rank, "max": max_rank},
        "frequency_range": {"min": min_freq, "max": max_freq},
        "part_of_speech_distribution": pos_counts,
        "entries_with_examples": entries_with_examples,
        "examples_with_translations": examples_with_translations
    }

def main():
    parser = argparse.ArgumentParser(description='Parse frequency dictionary from PDF.')
    parser.add_argument('--pdf', default='frec_dict.pdf', help='Path to the PDF file')
    parser.add_argument('--output', default='frequency_dict.json', help='Path for the output JSON file')
    parser.add_argument('--start-page', type=int, default=22, help='First page to parse (1-indexed)')
    parser.add_argument('--end-page', type=int, default=27, help='Last page to parse (1-indexed)')
    parser.add_argument('--full', action='store_true', help='Parse the entire dictionary (pages 22-300)')
    args = parser.parse_args()
    
    pdf_path = args.pdf
    output_path = args.output
    
    # Convert to 0-indexed for internal processing
    start_page = args.start_page - 1
    end_page = args.end_page
    
    if args.full:
        end_page = 300
        print("Parsing the entire frequency dictionary...")
    
    print(f"Parsing frequency dictionary from pages {start_page+1}-{end_page}...")
    text = extract_text_from_pdf(pdf_path, start_page, end_page)
    
    entries = parse_frequency_entries(text)
    
    print(f"\nFound {len(entries)} dictionary entries")
    
    if entries:
        # Print first and last entries to verify range
        print("\nFirst entry:")
        print(json.dumps(entries[0], ensure_ascii=False, indent=2))
        
        # Look for specific entries to verify improvements
        como_entry = None
        for entry in entries:
            if entry["word"] == "como" and "cj/av" in entry.get("part_of_speech", ""):
                como_entry = entry
                break
                
        if como_entry:
            print("\nEntry with complex part of speech (cj/av):")
            print(json.dumps(como_entry, ensure_ascii=False, indent=2))
        
        # Look for multiline example
        se_entry = None
        for entry in entries:
            if entry["word"] == "se" and entry["part_of_speech"] == "pn":
                se_entry = entry
                break
        
        if se_entry:
            print("\nEntry with multiline example:")
            print(json.dumps(se_entry, ensure_ascii=False, indent=2))
        
        # Print an entry with examples to verify the format
        print("\nExample entries with translations:")
        examples_shown = 0
        for entry in entries:
            if entry.get("examples") and examples_shown < 2:
                for example in entry["examples"]:
                    if example.get("english"):
                        print(json.dumps(entry, ensure_ascii=False, indent=2))
                        examples_shown += 1
                        break
                if examples_shown >= 2:
                    break
        
        print("\nLast entry:")
        print(json.dumps(entries[-1], ensure_ascii=False, indent=2))
        
        # Create dictionary with metadata
        dictionary = {
            "metadata": create_dictionary_metadata(entries),
            "entries": entries
        }
        
        # Print metadata
        print("\nDictionary metadata:")
        print(json.dumps(dictionary["metadata"], ensure_ascii=False, indent=2))
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        print(f"\nSaved dictionary with {len(entries)} entries to {output_path}")
    else:
        print("No entries found to save.")

if __name__ == "__main__":
    main()
