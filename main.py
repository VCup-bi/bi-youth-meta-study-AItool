import os
import csv
from pathlib import Path
from dataclasses import dataclass, replace
from typing import List, Optional
import json

# from dotenv import load_dotenv
from openai import OpenAI
from openpyxl import Workbook
from tqdm import tqdm


@dataclass
class Reference:
    data: str
    abstract: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    llm_score: Optional[int] = None
    llm_confidence: Optional[str] = None
    llm_rationale_short: Optional[str] = None
    llm_rationale_long: Optional[str] = None


def extract_references_from_ris(file_path="scopus.ris") -> List[Reference]:
    """
    Extract abstracts from a RIS file.
    
    Args:
        file_path (str): Path to the RIS file
        
    Returns:
        list: List of references found in the file
    """

    data = Path(file_path).read_text(encoding="utf-8-sig")
    lines = data.splitlines()

    references: List[Reference] = []
    reading_entry = False
    entry = []
    ref = Reference("")

    for line in lines:
        # Start of a reference
        if line.startswith("TY"):
            reading_entry = True
            entry = [line]
        elif line.startswith("TI") or line.startswith("T1"):
            entry.append(line)
            ref.title = line[6:]
        # End of reference
        elif line.startswith("ER"):
            entry.append(line)
            ref.data = "\n".join(entry)
            references.append(ref)
            reading_entry = False
            ref = Reference("")
            entry = []
        # Start of abstract
        elif line.startswith("AB") and reading_entry:
            entry.append(line)
            ref.abstract = line[6:]
        # Continue reading the reference
        elif reading_entry:
            entry.append(line)

    return references


def call_gpt4o(prompt: str, system_prompt: str) -> str:
    client = OpenAI()

    completion = client.chat.completions.create(
        response_format={"type": "json_object"},  # enable json mode
        # model="gpt-4o-mini",
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    )

    result = completion.choices[0].message.content

    return result


def evaluate_references_with_llm(references: List[Reference], system_prompt: str) -> List[Reference]:
    """
    Run the LLM on the references and write the result to the N1 fields of the references.
    """

    # Randomize references
    # NOTE: FOR TESTING. Remove for production
    # import random
    # random.seed(1)
    # random.shuffle(references)

    new_refs = []
    references = references[5000:6000]  # first X for testing
    for i, ref in tqdm(enumerate(references), total=len(references), desc="Processing references", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"):

        try: 
            response = call_gpt4o(ref.data, system_prompt)
            response = json.loads(response)
        except Exception as e:
            new_refs.append(ref)
            print(f"LLM Error: {e}. Omitting LLM comments...")
            continue

        ref.llm_score = response["llm_score"]
        ref.llm_confidence = response["llm_confidence"]
        ref.llm_rationale_short = response["llm_rationale_short"]
        ref.llm_rationale_long = response["llm_rationale_long"]

        n1_fields = [f"N1  - {k}: {v}" for k, v in response.items()]

        data = ref.data
        # Insert the response at the second to last line before the ER line
        data = data.splitlines()
        data.insert(-1, "\n".join(n1_fields))
        data = "\n".join(data)
        # print(data)

        new_ref = replace(ref, data=data)
        new_refs.append(new_ref)

    return new_refs 

def export_references_to_csv(references: List[Reference], output_file: str):
    """
    Export the references to a CSV file.
    """
    
    with open(output_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "LLM Score", "LLM Confidence", "LLM Rationale Short", "LLM Rationale Long", "Abstract"])

        for ref in references:
            row = [ref.title, ref.llm_score, ref.llm_confidence, ref.llm_rationale_short, ref.llm_rationale_long, ref.abstract]
            writer.writerow(row)


def export_references_to_excel(references: List[Reference], output_file: str):
    """
    Export the references to an Excel file.
    """
    wb = Workbook()
    ws = wb.active

    # Define headers
    headers = ["Title", "LLM Score", "LLM Confidence", "LLM Rationale Short", 
              "LLM Rationale Long", "Abstract"]
    ws.append(headers)

    # Add data rows
    for ref in references:
        row = [
            ref.title,
            ref.llm_score,
            ref.llm_confidence,
            ref.llm_rationale_short,
            ref.llm_rationale_long,
            ref.abstract
        ]
        ws.append(row)

    # Adjust column widths for better readability
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 100)  # Cap width at 100 characters
        ws.column_dimensions[column_letter].width = adjusted_width

    # Save the workbook
    wb.save(output_file)
 
        

if __name__ == "__main__":
    input_file = "all_deduplicated.ris"
    print(f"Input: {input_file}")

    with open("system_prompt.txt", "r") as f:
        system_prompt = f.read()

    references = extract_references_from_ris(input_file)

    references = evaluate_references_with_llm(references, system_prompt)

    # export_references_to_csv(references, "references_with_llm_eval.csv")

    output_file = "references_with_llm_eval_5000-6000.xlsx"
    export_references_to_excel(references, output_file)

    print(f"Done. References written to {output_file}")
