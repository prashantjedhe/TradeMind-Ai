FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK stopwords (RAKE keyword extraction) + FinBERT weights baked in
# at build time so workers never block on downloads at runtime.
# HF_HOME lives OUTSIDE /app: /app is a host bind mount at runtime
# (see docker-compose volumes), which would hide anything baked under it.
ENV NLTK_DATA=/usr/local/share/nltk_data \
    HF_HOME=/opt/hf_cache \
    TOKENIZERS_PARALLELISM=false
# stopwords (RAKE stop-list) + punkt/punkt_tab (RAKE sentence tokenizer).
RUN python -m nltk.downloader -d /usr/local/share/nltk_data stopwords punkt punkt_tab && \
    python -c "import torch; from transformers import AutoTokenizer, AutoModelForSequenceClassification; t=AutoTokenizer.from_pretrained('ProsusAI/finbert'); m=AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); m.eval(); print('finbert verify:', sum(p.numel() for p in m.parameters()), 'params')"

COPY . .

EXPOSE 8000
