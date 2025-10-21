# EduSummarizer

A lightweight document summarization service. It accepts either raw text or a PDF upload, extracts text (with optional OCR for scanned PDFs), and summarizes the content using a local Pegasus summarization pipeline when available. If heavy ML dependencies aren't available, a small extractive fallback summarizer runs so the API remains usable on most machines.

This README explains how to set up the project on Windows (PowerShell examples included), install dependencies, run the API, use the endpoints, and enable optional features such as Tesseract OCR and Firestore persistence.

## Project layout

Top-level files and folders you'll interact with:

- `api/summarize_api.py` - FastAPI application and the HTTP endpoints
- `ocr/text_from_pdf_paths.py` - PDF text extraction with optional Tesseract OCR
- `summarizer/pegasus_summarizer.py` - Pegasus summarization wrapper with a lightweight fallback
- `requirements.txt` - Python dependencies

## Quick start (Windows PowerShell)

1. Create and activate a Python virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Upgrade pip and install dependencies:

```powershell
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
```

Notes:

- Installing `torch` and `transformers` downloads large packages and may take time and disk space. If you only want the API without model-based summarization, you can skip these; the project will use a fallback extractive summarizer.
- On Windows, some packages (notably `PyMuPDF` and `Pillow`) may require build tools or prebuilt wheels. If you hit issues, try installing wheels from unofficialwheel sites or use conda.

## Tesseract OCR (optional)

If you plan to extract text from scanned PDFs (images), install Tesseract and make sure it's on your PATH or provide the path via `--tesseract-cmd` where applicable.

Windows install (example using Chocolatey):

```powershell
choco install tesseract
```

Verify installation:

```powershell
tesseract --version
```

If Tesseract isn't on PATH you can provide the executable path when calling the CLI or set `pytesseract.pytesseract.tesseract_cmd` programmatically.

## Run the API locally

The FastAPI app is located at `api/summarize_api.py` and can be run with Uvicorn.

Start the API (PowerShell):

```powershell
# from project root
python .\api\summarize_api.py
```

This will start Uvicorn on `0.0.0.0:8000` by default. Visit `http://localhost:8000/docs` to open the interactive Swagger UI.

## API endpoints

1. Health check

- GET /health

Response:

```json
{ "status": "ok" }
```

2. Summarize

- POST /summarize

Accepts form data. Either send a `text` field or upload a `file`. If uploading a PDF and you want OCR for scanned pages, set `use_ocr` to `true`.

Form fields:

- `text` (string) - raw text to summarize (optional if `file` provided)
- `file` (file upload) - PDF or plain text file (optional if `text` provided)
- `use_ocr` (boolean) - when uploading a PDF, run OCR on pages without embedded text
- `model` (string) - name of the summarization model; currently only `pegasus` is supported locally

Response JSON:

```json
{
  "summary": "...",
  "saved_id": null
}
```

`saved_id` will be a Firestore document id if Firestore persistence is configured (see below); otherwise it will be `null`.

### Example requests (PowerShell / curl)

Send raw text:

```powershell
$body = @{
    text = "This is a long piece of text that I want summarized..."
    use_ocr = $false
}
Invoke-RestMethod -Uri "http://localhost:8000/summarize" -Method Post -Form $body
```

Upload a PDF with OCR enabled (PowerShell):

> PowerShell multipart form uploads can be awkward; if you run into issues use `curl` or Postman. Example `curl` usage is provided below.

CURL example (plain text):

```bash
curl -X POST "http://localhost:8000/summarize" -F "text=Your long text here"
```

CURL example (file upload, enable OCR):

```bash
curl -X POST "http://localhost:8000/summarize" -F "file=@document.pdf" -F "use_ocr=true"
```

## Firestore persistence (optional)

The API has optional support for saving summaries to Google Firestore. To enable it:

1. Install and configure `google-cloud-firestore` (already in `requirements.txt`).
2. Set the environment variable `FIRESTORE_PROJECT` to your GCP project id.
3. Ensure application credentials are available (for example, set `GOOGLE_APPLICATION_CREDENTIALS` to a service account JSON key file path).

When configured, each successful summarization stores a small document in the `summaries` collection and returns the generated `saved_id` in the response.

## Developer notes

- The summarizer uses `google/pegasus-xsum` by default. Upon first run, the model/tokenizer will be downloaded if `transformers` and `torch` are installed and a compatible device is available.
- If the Pegasus model can't be loaded (missing libraries, no GPU/CPU support, or network issues), the module falls back to a deterministic extractive summarizer so the endpoint still works for basic use-cases.

## Troubleshooting

- If you get import errors for `torch` or `transformers` and you don't need the model, remove them from the environment or create a new environment without them — the API will still work using the fallback.
- If PDF extraction finds no text and OCR is enabled but you see warnings about pytesseract, make sure Tesseract is installed and accessible.
- On Windows, long install times for `torch` are expected. Consider using a CPU-only wheel if you don't need CUDA.

## Testing OCR extraction locally

Extract text from a PDF directly (without the API) using the CLI in `ocr/text_from_pdf_paths.py`:

```powershell
python .\ocr\text_from_pdf_paths.py .\examples\document.pdf --ocr --output extracted.txt
```

## License & Credits

This project is a learning/demo project. Adapt, reuse, and extend as you like.

## What changed

This README was generated/updated to reflect current project files and how to run the API locally (Windows PowerShell examples). If you want a macOS/Linux command snippet set or more advanced examples (async client, Dockerfile, CI), tell me which you prefer and I will add them.

## Deploy to Google Cloud Run

Use Google Cloud Run to deploy this containerized service. The commands below assume you have the Google Cloud SDK installed, are logged in (`gcloud auth login`), and have selected the target project (`gcloud config set project YOUR_PROJECT_ID`).

1. Build the container image and push to Artifact Registry or Container Registry. Example using Cloud Build (recommended):

```powershell
# Build and push with Cloud Build (Cloud Build will create the image and push to gcr or artifact registry according to your project settings)
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/edusummarizer:latest .
```

Or build locally and push (replace registry path as needed):

```powershell
# Local build
docker build -t gcr.io/YOUR_PROJECT_ID/edusummarizer:latest .
# Push
docker push gcr.io/YOUR_PROJECT_ID/edusummarizer:latest
```

2. Deploy to Cloud Run:

```powershell
gcloud run deploy edusummarizer \
  --image gcr.io/YOUR_PROJECT_ID/edusummarizer:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --concurrency 1 \
  --max-instances 3 \
  --set-env-vars PORT=8080
```

Recommended flags explanation:

- `--region`: choose a region near your users (`us-central1` is an example).
- `--memory`: set to `1Gi` (or higher) because `transformers`/`torch` can use significant RAM. For production, consider 2Gi or 4Gi depending on model size.
- `--concurrency`: set low (1) if using models that are CPU/memory heavy so requests don't compete for RAM; higher concurrency can be used for lightweight fallback-only runs.
- `--max-instances`: limit to control costs and cold-start behavior.
- `--set-env-vars PORT=8080`: Cloud Run injects `PORT` automatically, but this makes it explicit; the Dockerfile reads `$PORT`.

Service account & permissions:

- Create a service account for the Cloud Run service if it needs to access Firestore or other GCP services:

```powershell
# Create service account
gcloud iam service-accounts create edusummarizer-sa --display-name "EduSummarizer service account"

# Grant Firestore (Datastore) user role as an example
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:edusummarizer-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

Then deploy with the service account:

```powershell
gcloud run deploy edusummarizer \
  --image gcr.io/YOUR_PROJECT_ID/edusummarizer:latest \
  --region us-central1 \
  --platform managed \
  --service-account edusummarizer-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 1Gi \
  --concurrency 1
```

Notes:

- If your app uses Firestore, either set the `GOOGLE_APPLICATION_CREDENTIALS` secret at deploy time or assign the service account the appropriate IAM role so Cloud Run can access Firestore directly.
- For heavy model usage, consider using a larger machine (2Gi/4Gi) or serving models separately (Vertex AI Prediction, a dedicated VM, or GKE with GPUs).
