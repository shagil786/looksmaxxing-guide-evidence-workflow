# Online mode

The project supports a real TinyFish retrieval and small-model path without changing the offline evaluator:

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://llm.onerouter.pro/v1
export LOOKSMAXXING_MODEL=qwen/qwen3.8-27b:free
export TINYFISH_API_KEY=your-rotated-tinyfish-key
python3 run_online.py "Does creatine cause hair loss?"
```

The TinyFish MCP web agent performs the online search; the host integration passes its result into `TinyFishSearch`. Search results and fetched pages are filtered to the medical/editorial allowlist before they enter model context. Page fetches are capped at 120 KB and 2,500 characters per source. The model request uses the OpenAI-compatible Chat Completions API with JSON output; credentials are never logged. The online writer returns structured JSON for conversion into the existing `Brief` contract.

Online smoke tests are intentionally opt-in because they require a restarted agent session with TinyFish connected and user-owned model credentials. The default tests use replay fixtures.

For local setup, copy `.env.example` to `.env` and load it with your shell or a dotenv loader. Never commit `.env`; rotate any key that has been pasted into chat or source control.
