
import logging
import re
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded model variables
_MODEL_NAME = "google/pegasus-xsum" # Local path where the model is saved
_pipeline = None
_model_available = False
_device = -1


def _ensure_model_loaded():
    """Attempt to load the Pegasus model and pipeline. If the environment
    doesn't have PyTorch/transformers installed or model download fails, this
    function leaves `_model_available` as False and logs the issue.
    """
    global _pipeline, _model_available, _device
    if _model_available or _pipeline:
        return

    try:
        import torch
        from transformers import pipeline, AutoTokenizer, PegasusForConditionalGeneration
    except Exception as e:
        logger.warning("Transformers/PyTorch not available: %s", e)
        _model_available = False
        return

    _device = 0 if torch.cuda.is_available() else -1

    try:
        logger.info(f"Loading tokenizer and model for {_MODEL_NAME}...")
        tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        model = PegasusForConditionalGeneration.from_pretrained(_MODEL_NAME)
        _pipeline = pipeline("summarization", model=model, tokenizer=tokenizer, device=_device)
        _model_available = True
        logger.info("Pegasus model loaded successfully")
    except Exception as e:
        logger.exception("Failed to load Pegasus model/tokenizer: %s", e)
        _model_available = False


def chunk_text(text: str, max_tokens: int = 1000) -> List[str]:
    """Crude whitespace-based chunking for long texts."""
    words = text.split()
    chunks, current = [], []
    token_count = 0
    for w in words:
        token_count += 1  # crude token estimate: one word = one token
        current.append(w)
        if token_count >= max_tokens:
            chunks.append(" ".join(current))
            current, token_count = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


_STOPWORDS = {
    "the", "and", "is", "in", "it", "of", "to", "a", "that", "this",
    "for", "with", "on", "as", "are", "was", "were", "by", "an",
}


def _fallback_extractive_summary(text: str, max_len: int, min_len: int) -> str:
    """Simple extractive summarizer: score sentences by word frequency and
    return the top sentences. This is used when the Pegasus model is unavailable
    so the API remains runnable on machines without heavy ML deps.
    """
    # Split into sentences (simple heuristic)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return ""

    if len(sentences) == 1:
        return sentences[0]

    words = re.findall(r"\w+", text.lower())
    freqs = {}
    for w in words:
        if w in _STOPWORDS:
            continue
        freqs[w] = freqs.get(w, 0) + 1

    if not freqs:
        # fallback: return first few sentences
        return " ".join(sentences[:2])

    maxf = max(freqs.values())
    for k in freqs:
        freqs[k] = freqs[k] / maxf

    scored = []
    for i, s in enumerate(sentences):
        s_words = re.findall(r"\w+", s.lower())
        score = sum(freqs.get(w, 0) for w in s_words)
        scored.append((score, i, s))

    scored.sort(reverse=True)

    # Select top sentences until we have a short summary. Aim for ~max_len words.
    target_words = max_len
    selected = []
    selected_words = 0
    for score, idx, sent in scored:
        if selected_words >= target_words:
            break
        selected.append((idx, sent))
        selected_words += len(re.findall(r"\w+", sent))

    # Restore original order
    selected.sort()
    summary = " ".join(s for _, s in selected)

    # Ensure at least min_len words if possible
    if len(re.findall(r"\w+", summary)) < min_len:
        needed = min_len - len(re.findall(r"\w+", summary))
        # append next best sentence(s)
        for score, idx, sent in scored:
            if any(idx == ex_idx for ex_idx, _ in selected):
                continue
            selected.append((idx, sent))
            selected.sort()
            summary = " ".join(s for _, s in selected)
            if len(re.findall(r"\w+", summary)) >= min_len:
                break

    return summary


def summarize_text(text: str, max_len: int = 150, min_len: int = 60) -> str:
    """Summarize `text`. Attempts to use the Pegasus pipeline if available;
    otherwise falls back to a lightweight extractive summarizer so the API can
    run locally without external LLMs or heavy ML libraries.
    """
    _ensure_model_loaded()

    if _model_available and _pipeline is not None:
        chunks = chunk_text(text)
        summaries = []
        for chunk in chunks:
            result = _pipeline(chunk, max_length=max_len, min_length=min_len, do_sample=False)
            summaries.append(result[0]["summary_text"])
        return " ".join(summaries)

    logger.info("Pegasus model unavailable; using fallback extractive summarizer")
    return _fallback_extractive_summary(text, max_len, min_len)

