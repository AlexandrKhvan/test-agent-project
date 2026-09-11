import os
from ingestion.vision_ocr import extract_text_from_image
from ingestion.document_parsers import extract_text

class ParserAgent:
    def parse_file(self, file_path: str) -> dict:
        filename = os.path.basename(file_path)
        file_extension = os.path.splitext(file_path)[1].lower()

        result = {
            "filename": filename,
            "file_type": file_extension,
            "content": None,
            "success": False,
            "error": None
        }

        try:
            if file_extension in [".png", ".jpg", ".jpeg", ".webp"]:
                result["content"] = extract_text_from_image(file_path)
                result["success"] = True
            elif file_extension in [".pdf", ".docx", ".md", ".pptx", ".tex", ".txt"]:
                result["content"] = extract_text(file_path, file_type=file_extension)
                result["success"] = True
            else:
                result["error"] = f"Unsupported file extension: {file_extension}"
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

        return result

def run_ingestion(file_path: str) -> dict:
    agent = ParserAgent()
    return agent.parse_file(file_path)
