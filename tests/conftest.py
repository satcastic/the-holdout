"""Force offline mode for every test, before any src module reads settings."""

import os

os.environ["LLM_MODE"] = "fake"
os.environ["VECTOR_BACKEND"] = "memory"
os.environ["CHECKPOINTER"] = "memory"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["PINECONE_API_KEY"] = ""
