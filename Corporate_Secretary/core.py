import os
import json
import time
import datetime
from pathlib import Path
from docxtpl import DocxTemplate

from google import genai

client = None

def find_env_file(start_path):
    current = Path(start_path).absolute()
    while True:
        env_file = current / ".env"
        if env_file.exists():
            return env_file
        if current.parent == current:
            return None
        current = current.parent

def setup_gemini():
    global client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        env_path = find_env_file(__file__)
        if env_path:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.strip().split("=")[1].strip('"\'')
                        os.environ["GEMINI_API_KEY"] = api_key
                        break
    if not api_key:
        print("CRITICAL: GEMINI_API_KEY environment variable not found. Exiting.")
        exit(1)
    client = genai.Client(api_key=api_key)

SYSTEM_PROMPT_TEMPLATE = """You are an executive assistant extracting operational data to populate a formal meeting minutes template.
You are generating the meeting minutes strictly for: {target_month_year}.

Review the provided files. One is a Master File containing data for the whole year. You must ONLY extract and use the information from that Master File that corresponds to {target_month_year}. Ignore all other months. Combine this extracted data with the specific monthly files provided.

CRITICAL FORMATTING RULE: Whenever a section contains multiple distinct updates, topics, or actions, you MUST format the string using bullet points (using the '•' symbol) and clear line breaks. Do not write long, dense paragraphs.

Synthesize the information and output ONLY a valid JSON object using this exact schema:
{{
"meeting_date": "Month Year",
"production_updates": "Synthesize key updates using bullet points (•) for multiple items...",
"quality_updates": "Synthesize strictly from Ecolab reports using bullet points (•)...",
"hr_updates": "Synthesize HR/payroll updates using bullet points (•)...",
"financial_kpis": "Summarize KPI data. If missing, output 'No KPI data reviewed this month.'",
"future_goals": "List forward-looking goals using bullet points (•)...",
"topics_discussed": "Elaborate on the topics/products discussed using bullet points (•)..."
}}
Do not include markdown formatting or extra text outside the JSON object."""

def parse_month_year(folder_name):
    try:
        parts = folder_name.replace("-", "_").split("_")
        if len(parts) == 2 and len(parts[0]) == 4 and parts[1].isdigit():
            year = parts[0]
            month_num = int(parts[1])
            month_name = datetime.date(1900, month_num, 1).strftime('%B')
            return f"{month_name} {year}"
    except Exception:
        pass
    return folder_name.replace("_", " ")

def get_master_files(root_dir):
    master_dir = root_dir / "master_data"
    valid_exts = ['.xlsx', '.xls', '.docx', '.doc', '.pdf', '.csv']
    masters = []
    if master_dir.exists():
        for file_path in master_dir.iterdir():
            if file_path.name.startswith("~$") or file_path.name.startswith("."):
                continue
            if file_path.is_file() and file_path.suffix.lower() in valid_exts:
                masters.append(file_path)
    return masters

def process_batch(root_dir, folder_path, master_files):
    target_month_year = parse_month_year(folder_path.name)
    print(f"\nProcessing folder: {folder_path.name} (Target: {target_month_year})")
    
    uploaded_files = []
    valid_exts = ['.pdf', '.xlsx', '.xls', '.txt', '.csv', '.doc', '.docx']
    
    if master_files:
        print("Uploading Master files...")
        for mf in master_files:
            try:
                if mf.suffix.lower() == '.csv':
                    gfile = client.files.upload(file=str(mf), config={'mime_type': 'text/csv'})
                else:
                    gfile = client.files.upload(file=str(mf))
                uploaded_files.append(gfile)
            except Exception as e:
                print(f"Failed to upload master file {mf.name}: {e}")
    else:
        print("Warning: No master file found in master_data/")
        
    for file_path in folder_path.iterdir():
        if file_path.name.startswith("~$") or file_path.name.startswith("."):
            continue
        if file_path.is_file() and file_path.suffix.lower() in valid_exts:
            print(f"Uploading monthly file: {file_path.name}...")
            try:
                if file_path.suffix.lower() == '.csv':
                    gfile = client.files.upload(file=str(file_path), config={'mime_type': 'text/csv'})
                else:
                    gfile = client.files.upload(file=str(file_path))
                uploaded_files.append(gfile)
            except Exception as e:
                print(f"Failed to upload {file_path.name}: {e}")
                
    if not uploaded_files:
        print("No valid files to process in this folder or master_data/.")
        return
        
    try:
        time.sleep(2)
        print("Invoking gemini-2.5-pro model...")
        dynamic_prompt = SYSTEM_PROMPT_TEMPLATE.format(target_month_year=target_month_year)
        
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=uploaded_files,
            config={
                "system_instruction": dynamic_prompt,
                "response_mime_type": "application/json"
            }
        )
        
        result_text = response.text
        if result_text.startswith("```json"):
            result_text = result_text.split("```json")[1].rsplit("```", 1)[0].strip()
        elif result_text.startswith("```"):
            result_text = result_text.split("```")[1].rsplit("```", 1)[0].strip()
            
        data = json.loads(result_text)
        print("Successfully parsed Gemini JSON output.")
        
        template_path = root_dir / "template" / "template.docx"
        if not template_path.exists():
            print(f"Warning: Template missing at {template_path}. Cannot generate document.")
            return
            
        doc = DocxTemplate(str(template_path))
        doc.render(data)
        
        month_index = folder_path.name.replace(" ", "_")
        output_filename = f"{month_index}_Minutes.docx"
        output_path = root_dir / "outputs" / output_filename
        doc.save(str(output_path))
        print(f"SUCCESS: Saved generated meeting minutes to -> {output_path}")
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from response: {e}")
        if 'response' in locals():
            print("Raw response text:")
            print(response.text)
    except Exception as e:
        print(f"An unexpected error occurred during synthesis: {e}")
        
    finally:
        print("Cleaning up remote files on Gemini...")
        for gfile in uploaded_files:
            try:
                client.files.delete(name=gfile.name)
            except Exception as e:
                print(f"Failed to delete {gfile.name}: {e}")
        print("Cleanup complete.")

def main():
    setup_gemini()
    
    root_dir = Path(__file__).parent
    
    data_ingest = root_dir / "data_ingest"
    master_data = root_dir / "master_data"
    
    data_ingest.mkdir(exist_ok=True)
    master_data.mkdir(exist_ok=True)
    (root_dir / "template").mkdir(exist_ok=True)
    (root_dir / "outputs").mkdir(exist_ok=True)
    
    print("====================================")
    print("Corporate Secretary Agent Initialized")
    print("====================================")
    
    master_files = get_master_files(root_dir)
    
    dirs = [d for d in data_ingest.iterdir() if d.is_dir()]
    if not dirs:
        print(f"No batched chronological folders found in {data_ingest}.")
        print("Please create subfolders (e.g., '2025_01') and drop your files inside.")
        return
        
    for subfolder in dirs:
        process_batch(root_dir, subfolder, master_files)
        print("-" * 50)
        
if __name__ == "__main__":
    main()
