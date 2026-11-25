"""AI planning brief: the mAI Gateway client, prompts, the stage pipeline, its cache and output parsing.

    models.py     which mAI models the app may use and the tools each one has
    client.py     the only module that calls an LLM (OpenAI Responses API via the Posit mAI Gateway)
    prompt.py     system and stage prompts
    documents.py  plan-document download (SSRF-guarded), text extraction and passage selection
    pipeline.py   one unit x one score theme x one release, stage by stage
    cache.py      stage results on disk and, when the table exists, in Unity Catalog
    parse.py      stage text -> sections, bullets and citations for the page
"""
