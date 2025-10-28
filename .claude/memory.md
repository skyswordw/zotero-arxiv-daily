# Project Memory

## Recent Major Updates (2025-10-28)

### Features Implemented

#### 1. Bilingual TLDR Support (EN + ZH)
- **Location**: `paper.py` - `ArxivPaper.tldr` property
- **Implementation**: Single LLM call generates both English and Chinese summaries
- **Format**: Returns `dict[str, str]` with keys 'en' and 'zh'
- **Parsing**: Uses regex to extract "EN: ... ZH: ..." format
- **Backward Compatibility**: `construct_email.py:get_block_html()` handles both dict and str formats
- **Display**: Shows both languages in email with "EN:" and "ZH:" labels

#### 2. Daily Summary Generation
- **Location**: `construct_email.py:generate_daily_summary()`
- **Context**: Uses up to 12k tokens to process all paper titles and abstracts
- **Output**: Bilingual summary (EN + ZH) covering:
  - Main research areas and topics
  - Notable trends and emerging directions
  - 2-3 highlighted papers worth special attention
- **Display**: Green-bordered box at top of email with "📊 Daily Summary | 每日总结" header
- **Function**: `get_summary_html()` generates the HTML block

#### 3. Parallel Processing Optimization
- **Location**: `construct_email.py:preload_paper_data()`
- **Implementation**: ThreadPoolExecutor with 5 workers
- **Targets**: Preloads TLDR, affiliations, and code_url concurrently
- **Performance**: ~5x speedup for typical workloads
  - Before: ~80s per paper (serial) = 67 minutes for 50 papers
  - After: ~16s per paper (parallel) = 14 minutes for 50 papers
- **Benefits**: Removed 10-second sleep delays, all data cached before rendering
- **Progress**: Uses tqdm progress bar "Loading paper data"

#### 4. Documentation
- **CLAUDE.md**: Comprehensive development guide added
  - Project overview and architecture
  - Development commands (local + Docker)
  - Core pipeline explanation
  - Implementation details (environment variables, LaTeX processing, error handling)
  - GitHub Actions workflow documentation

#### 5. Test Workflow
- **File**: `.github/workflows/test_dev.yml`
- **Name**: "Test workflow (dev)"
- **Purpose**: Test dev branch features from main branch UI
- **Difference from test.yml**: Always checks out dev branch, ignores REPOSITORY/REF variables

### Technical Details

#### Error Handling
- `code_url` queries to paperswithcode.com may return empty responses (DEBUG level)
- These are normal when papers don't have code implementations
- Impact: Only affects Code button visibility, other features unaffected

#### LLM Configuration
- Supports both API and local models
- API: OpenAI-compatible endpoints (configurable base_url)
- Local: Qwen2.5-3B-Instruct-GGUF (q4_k_m, ~3GB)
- Bilingual prompts tested and working with both backends

#### Git Workflow
- **dev branch**: Active development branch for new features
- **main branch**: Stable production code
- All PRs should target dev branch first
- Current state: All features merged to main (commit 59175b4)

### Environment Variables
All existing environment variables still work:
- ZOTERO_ID, ZOTERO_KEY, ARXIV_QUERY (required)
- SMTP_SERVER, SMTP_PORT, SENDER, RECEIVER, SENDER_PASSWORD (required)
- MAX_PAPER_NUM, USE_LLM_API, OPENAI_API_KEY, OPENAI_API_BASE, MODEL_NAME (optional)
- LANGUAGE (optional, but note: bilingual TLDR now always generates EN+ZH regardless)

### Known Issues
None critical. Minor DEBUG logs from paperswithcode.com API are expected and harmless.

### Performance Metrics
- Parallel loading: 5 papers processed in ~14 seconds (vs ~80 seconds serial)
- Daily summary generation: ~15-30 seconds depending on paper count
- Total time for 50 papers: ~14 minutes (vs ~67 minutes before optimization)

### Next Steps / Future Improvements
- Consider configurable worker count for parallel processing
- Add retry logic for paperswithcode.com API failures
- Potential to add more language support beyond EN/ZH
- Consider caching embeddings for frequently accessed papers
