import PyPDF2
import re
import json
import os

def extract_qa_from_pdf(pdf_path):
    """
    Extracts question-answer pairs from a single PDF by treating Q numbers as block separators.
    """
    qa_dict = {}
    full_text = ""

    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                full_text += (page.extract_text() or "") + " "
    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found.")
        return {}
    except Exception as e:
        print(f"An error occurred while reading the PDF: {e}")
        return {}

    # Clean headers/footers
    cleaned_text = re.sub(r'UNIVERSITY DEPARTMENTS RAJASTHAN TECHNICAL UNIVERSITY, KOTA\s*\d+', '', full_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', cleaned_text)  # fix hyphen splits
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # normalize spaces

    # Find Q markers
    q_matches = list(re.finditer(r'Q(\d+)[\.:]', cleaned_text))
    if not q_matches:
        return {}

    q_matches.sort(key=lambda x: x.start())

    for i, q_match in enumerate(q_matches):
        q_start = q_match.start()
        q_num = int(q_match.group(1))

        q_end = q_matches[i + 1].start() if i + 1 < len(q_matches) else len(cleaned_text)
        qa_block = cleaned_text[q_start:q_end].strip()

        # Split into question and answer
        split_match = re.search(r'^(.*?)(?:Ans:|A:)(.*)', qa_block, re.DOTALL | re.IGNORECASE)
        if split_match:
            question_text = split_match.group(1).strip()
            answer_text = split_match.group(2).strip()
        else:
            question_text = qa_block.strip()
            answer_text = ""

        # Clean question text
        final_question = re.sub(r'Q\d+[\.:]?\s*', '', question_text).strip()
        answer_text = answer_text.replace("Ans:", "").replace("A:", "").strip()

        if final_question:
            qa_dict[final_question] = {
                "q_number": q_num,
                "question": final_question,
                "answer": answer_text
            }

    return qa_dict


def process_all_pdfs_in_directory(data_folder, output_json_path):
    all_qa_pairs = {}
    
    if not os.path.isdir(data_folder):
        print(f"Error: The directory '{data_folder}' was not found.")
        return

    for filename in os.listdir(data_folder):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(data_folder, filename)
            print(f"Processing file: {pdf_path}")
            
            qa_data = extract_qa_from_pdf(pdf_path)
            # Use the question as the key to prevent duplicates from different files
            for q, a in qa_data.items():
                all_qa_pairs[q] = a
            
    if all_qa_pairs:
        final_list = sorted(list(all_qa_pairs.values()), key=lambda x: x['q_number'])
        try:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(final_list, f, indent=4, ensure_ascii=False)
            print(f"Successfully combined and extracted {len(final_list)} unique Q&A pairs to {output_json_path}")
        except Exception as e:
            print(f"Error writing to JSON file: {e}")
    else:
        print("No Q&A pairs were extracted from any PDF files.")


if __name__ == "__main__":
    data_directory = "data"
    output_file = "combined_extracted_qa.json"
    process_all_pdfs_in_directory(data_directory, output_file)
