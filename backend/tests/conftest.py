import os

os.environ["SSA_DATABASE_URL"] = ""
os.environ["SSA_OPENAI_API_KEY"] = ""
os.environ["SSA_QDRANT_URL"] = ""
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["SSA_LANGCHAIN_TRACING_V2"] = "false"
os.environ["SSA_AUTH_USERNAME"] = "advisor"
os.environ["SSA_AUTH_PASSWORD"] = "advisor-demo"
os.environ["SSA_AUTH_TOKEN_SECRET"] = "test-only-auth-secret"
