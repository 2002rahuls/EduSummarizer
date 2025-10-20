
from transformers import pipeline, AutoTokenizer, PegasusForConditionalGeneration
import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Device selection: use first CUDA device if available, otherwise cpu
device = 0 if torch.cuda.is_available() else -1  # 0 = first GPU, -1 = CPU


# Load tokenizer and model explicitly so we can see missing/unexpected keys.
MODEL_NAME = "google/pegasus-xsum"
try:
    logger.info(f"Loading tokenizer for {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    logger.info(f"Loading model {MODEL_NAME} (this may print missing/unexpected keys)...")
    model = PegasusForConditionalGeneration.from_pretrained(MODEL_NAME)
except Exception as e:
    logger.exception("Failed to load model/tokenizer. Check internet connection and transformers version.")
    raise

# Create a pipeline from the loaded model and tokenizer. This avoids silent re-initialization of weights.
summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=device)



# ----- 2. Chunking function for long texts -----
def chunk_text(text, max_tokens=1000):
    words = text.split()
    chunks, current = [], []
    token_count = 0
    for w in words:
        token_count += len(w.split())  # crude token estimate
        current.append(w)
        if token_count >= max_tokens:
            chunks.append(" ".join(current))
            current, token_count = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks



# ----- 3. Summarization function -----
def summarize_text(text, max_len=150, min_len=60):
    chunks = chunk_text(text)
    summaries = []
    for chunk in chunks:
        result = summarizer(chunk, max_length=max_len, min_length=min_len, do_sample=False)
        summaries.append(result[0]["summary_text"])
    return " ".join(summaries)

