# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zotero-arXiv-Daily is an automated paper recommendation system that:
- Retrieves papers from a user's Zotero library
- Fetches new arXiv papers based on specified categories
- Ranks papers by relevance using embedding similarity
- Generates AI-powered TL;DR summaries and extracts affiliations
- Sends daily email digests with recommended papers

The system is designed to run as a GitHub Action workflow with zero cost for public repositories.

## Development Commands

### Running Locally
```bash
# Set all required environment variables first
export ZOTERO_ID=xxxx
export ZOTERO_KEY=xxxx
export ARXIV_QUERY=cs.AI+cs.CV+cs.LG+cs.CL
export SMTP_SERVER=smtp.example.com
export SMTP_PORT=465
export SENDER=sender@example.com
export RECEIVER=receiver@example.com
export SENDER_PASSWORD=xxxx

# Optional variables
export MAX_PAPER_NUM=50
export USE_LLM_API=0
export LANGUAGE=English

# Run the main workflow
uv run main.py

# Run in debug mode (retrieves only 5 papers regardless of date)
uv run main.py --debug
```

### Docker Deployment
```bash
# Build and run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## Architecture

### Core Pipeline (main.py)

1. **Data Retrieval**
   - `get_zotero_corpus()`: Fetches all papers from user's Zotero library via pyzotero API
   - Papers are filtered by type (conferencePaper, journalArticle, preprint) and must have abstracts
   - Collection paths are resolved for filtering
   - `get_arxiv_paper()`: Fetches new arXiv papers using RSS feed and arxiv API
   - In production: only retrieves papers with `arxiv_announce_type == 'new'`
   - In debug mode: retrieves 5 papers from cs.AI sorted by submission date

2. **Filtering**
   - `filter_corpus()`: Applies gitignore-style patterns to exclude specific Zotero collections
   - Uses `gitignore-parser` library for pattern matching against collection paths

3. **Ranking**
   - `rerank_paper()` in recommender.py: Uses sentence-transformer embeddings to compute similarity
   - Calculates weighted average similarity with time decay (newer Zotero papers weighted higher)
   - Model: 'avsolatorio/GIST-small-Embedding-v0'
   - Formula: `score = (similarity_matrix * time_decay_weight).sum() * 10`

4. **LLM Processing**
   - `set_global_llm()`: Configures either OpenAI-compatible API or local Qwen2.5-3B model
   - Local model: downloads GGUF quantized model (q4_k_m) from HuggingFace on first run

5. **Email Generation**
   - `render_email()`: Creates HTML email from papers
   - `send_email()`: Sends via SMTP with TLS/SSL fallback

### ArxivPaper Class (paper.py)

Wraps arxiv.Result with enhanced features:

- **Cached Properties** (computed once and cached):
  - `arxiv_id`: Extracts version-less arXiv ID
  - `code_url`: Queries paperswithcode.com API for implementation links
  - `tex`: Downloads and parses LaTeX source files from arXiv
    - Identifies main .tex file using .bbl file or document environment
    - Removes comments and processes \input/\include directives
    - Returns dict with individual files and combined "all" content
  - `tldr`: Generates **bilingual** one-sentence summary using LLM (returns dict with 'en' and 'zh' keys)
    - Extracts introduction and conclusion sections from LaTeX
    - Removes figures, tables, and citations
    - Truncates prompt to 4000 tokens using tiktoken
    - Prompt asks for both English and Chinese summaries in format "EN: ... ZH: ..."
    - Regex parsing extracts both languages; falls back to raw text if parsing fails
  - `affiliations`: Extracts author affiliations from LaTeX using LLM
    - Searches author regions in LaTeX preamble
    - LLM parses and returns list of top-level affiliations only

### LLM Abstraction (llm.py)

- Global singleton pattern: `GLOBAL_LLM` configured via `set_global_llm()`
- Two backends:
  - **OpenAI-compatible API**: Uses openai library, configurable base_url and model
  - **Local llama.cpp**: Downloads Qwen2.5-3B-Instruct-GGUF (q4_k_m, ~3GB)
    - Context window: 5000 tokens
    - 4 threads for CPU inference
- `generate()`: Unified interface for chat completions with retry logic (3 attempts)

### Email Rendering (construct_email.py)

- **Daily Summary Generation**: `generate_daily_summary()` creates overview of all papers
  - Uses full paper titles and abstracts (up to 12k tokens)
  - LLM generates bilingual summary (EN + ZH) covering main topics, trends, and highlights
  - Displayed at top of email in green-bordered summary box
- **Bilingual TLDR Support**: Papers show summaries in both English and Chinese
  - `get_block_html()` handles both dict (bilingual) and str (legacy) formats
  - Format: "EN: ... ZH: ..."
- HTML template with inline CSS for email client compatibility
- Star rating system based on relevance score (6-8 scale, 5 stars max)
- Paper blocks include: title, authors (truncated if >5), affiliations, arXiv ID, bilingual TLDR, PDF/Code links
- 10-second sleep between papers to rate-limit LLM API calls

## Important Implementation Details

### Environment Variable Handling
- main.py uses a custom `add_argument()` wrapper that:
  - Reads from environment variables (uppercased argument names)
  - Treats empty strings as None (handles GitHub Actions unset variables)
  - Converts bool types: 'true', '1' → True, others → False

### LaTeX Processing
- Multiple fallback strategies for finding main .tex file:
  1. Match .bbl filename
  2. Search for `\begin{document}` block
  3. If ambiguous, skip tex parsing (use abstract only)
- Regex-based cleaning: removes comments, figures, tables, citations, consecutive whitespace
- Handles `\input{}` and `\include{}` directives by replacing with file contents

### Error Handling
- HTTP 404 on arXiv source downloads is normal (some papers have no LaTeX source)
- Affiliation extraction failures are logged at debug level and return None
- LLM API calls have 3-retry logic with 3-second delays

### Token Management
- All prompts truncated to 4000 tokens using gpt-4o tokenizer (tiktoken)
- Daily summary uses up to 12000 tokens to process all paper abstracts
- This ensures compatibility across different LLM backends

## GitHub Actions Workflow

### Main Workflow (.github/workflows/main.yml)
- Runs daily at 22:00 UTC (cron: '0 22 * * *')
- Can be manually triggered via workflow_dispatch
- Uses `uv` (v0.5.4) for dependency management
- Supports dynamic repository checkout via `vars.REPOSITORY` and `vars.REF`

### Test Workflow (.github/workflows/test.yml)
- Manual trigger only
- Always runs with `--debug` flag (retrieves 5 papers regardless of date)

## Contributing Guidelines

- All PRs should merge to the `dev` branch, not `main`
- The project uses AGPLv3 license
- Python 3.11+ required (see pyproject.toml)
