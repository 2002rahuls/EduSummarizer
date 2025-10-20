import sys
from pathlib import Path

# Ensure project root is on sys.path so `import summarizer` works when the
# module is executed directly (for example: `python api/summarize_api.py`).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import Optional
import os
import tempfile
import uuid
import logging

from summarizer.pegasus_summarizer import summarize_text
from ocr.text_from_pdf_paths import extract_text_from_pdf

try:
	from google.cloud import firestore
	_HAS_FIRESTORE = True
except Exception:
	firestore = None
	_HAS_FIRESTORE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EduSummarizer API")


def save_to_firestore(document: dict) -> Optional[str]:
	"""Save a summary document to Firestore if configured.

	Returns the generated document id or None if not saved.
	"""
	if not _HAS_FIRESTORE:
		logger.debug("Firestore client not available; skipping save")
		return None

	project = os.environ.get("FIRESTORE_PROJECT")
	if not project:
		logger.debug("FIRESTORE_PROJECT not set; skipping save")
		return None

	client = firestore.Client(project=project)
	col = client.collection("summaries")
	doc_ref = col.document()
	doc_ref.set(document)
	return doc_ref.id


@app.get("/health")
def health():
	return {"status": "ok"}


@app.post("/summarize")
async def summarize(
	text: Optional[str] = Form(None),
	file: Optional[UploadFile] = File(None),
	use_ocr: bool = Form(False),
	model: str = Form("pegasus"),
):
	"""Accept either raw text or a PDF upload. If a PDF is uploaded and use_ocr
	is true, run OCR on pages without embedded text.
	"""
	if not text and not file:
		return JSONResponse({"error": "Provide either 'text' form field or an uploaded file."}, status_code=400)

	source = None
	extracted_text = text

	if file:
		# Save uploaded file to a temp location
		suffix = os.path.splitext(file.filename)[1] or ".pdf"
		tmp_path = os.path.join(tempfile.gettempdir(), f"upload-{uuid.uuid4()}{suffix}")
		with open(tmp_path, "wb") as f:
			content = await file.read()
			f.write(content)
		source = file.filename

		if suffix.lower() == ".pdf":
			try:
				extracted_text = extract_text_from_pdf(tmp_path, ocr=use_ocr)
			except Exception as exc:
				logger.exception("Failed to extract text from uploaded PDF")
				return JSONResponse({"error": "Failed to extract text from PDF", "detail": str(exc)}, status_code=500)
		else:
			# treat as plain text file
			try:
				extracted_text = open(tmp_path, "r", encoding="utf-8").read()
			except Exception:
				extracted_text = content.decode("utf-8", errors="ignore")

	if not extracted_text or not extracted_text.strip():
		return JSONResponse({"error": "No text could be extracted from input."}, status_code=400)

	# For now only pegasus model available locally
	if model != "pegasus":
		logger.info("Requested model %s not available locally, falling back to pegasus", model)

	try:
		summary = summarize_text(extracted_text)
	except Exception as exc:
		logger.exception("Summarization failed")
		return JSONResponse({"error": "Summarization failed", "detail": str(exc)}, status_code=500)

	doc = {
		"id": str(uuid.uuid4()),
		"source_filename": source,
		"model": "pegasus",
		"summary": summary,
		"original_excerpt": (extracted_text[:200] + "...") if len(extracted_text) > 200 else extracted_text,
	}

	saved_id = None
	try:
		saved_id = save_to_firestore(doc)
	except Exception:
		logger.exception("Failed to save to Firestore; continuing without persistence")

	response = {"summary": summary, "saved_id": saved_id}
	return response


if __name__ == "__main__":
	import uvicorn

	uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

