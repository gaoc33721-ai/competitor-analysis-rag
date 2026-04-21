import json
import os
from typing import List, Optional

import boto3
from botocore.config import Config
from langchain_core.embeddings import Embeddings


def get_default_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-central-1"


def get_llm_provider() -> str:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider:
        return provider
    if os.getenv("ECS_CONTAINER_METADATA_URI_V4") or os.getenv("AWS_EXECUTION_ENV"):
        return "bedrock"
    if os.getenv("MINIMAX_API_KEY"):
        return "minimax"
    return "bedrock"


def _bedrock_runtime_client(region_name: Optional[str] = None):
    region = region_name or get_default_region()
    timeout = int(os.getenv("AWS_BEDROCK_TIMEOUT_SECONDS") or "60")
    cfg = Config(read_timeout=timeout, connect_timeout=timeout, retries={"max_attempts": 3, "mode": "standard"})
    return boto3.client("bedrock-runtime", region_name=region, config=cfg)


def bedrock_converse(
    prompt: str,
    *,
    system: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    region_name: Optional[str] = None,
) -> str:
    mid = model_id or os.getenv("BEDROCK_TEXT_MODEL_ID") or "anthropic.claude-3-haiku-20240307-v1:0"
    client = _bedrock_runtime_client(region_name=region_name)

    kwargs = {
        "modelId": mid,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": int(max_tokens), "temperature": float(temperature)},
    }
    if system and system.strip():
        kwargs["system"] = [{"text": system}]

    resp = client.converse(**kwargs)
    content = resp.get("output", {}).get("message", {}).get("content", [])
    parts = []
    for c in content:
        if isinstance(c, dict) and "text" in c:
            parts.append(c["text"])
    return "".join(parts).strip()


class BedrockTextEmbeddings(Embeddings):
    def __init__(self, *, model_id: Optional[str] = None, region_name: Optional[str] = None):
        self.model_id = model_id or os.getenv("BEDROCK_EMBEDDING_MODEL_ID") or "amazon.titan-embed-text-v2:0"
        self.region_name = region_name or get_default_region()
        self._client = _bedrock_runtime_client(region_name=self.region_name)

    def _embed_one(self, text: str) -> List[float]:
        body = json.dumps({"inputText": text})
        resp = self._client.invoke_model(modelId=self.model_id, body=body)
        raw = resp["body"].read()
        data = json.loads(raw)

        if isinstance(data, dict) and "embedding" in data and isinstance(data["embedding"], list):
            return data["embedding"]
        if isinstance(data, dict) and "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"]:
            first = data["embeddings"][0]
            if isinstance(first, dict) and "embedding" in first:
                return first["embedding"]
            if isinstance(first, list):
                return first
        raise ValueError(f"Unexpected embedding response format: {list(data.keys()) if isinstance(data, dict) else type(data)}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)

