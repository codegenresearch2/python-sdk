import logging\"nfrom contextlib import asynccontextmanager\"nfrom typing import Any\"nfrom urllib.parse import quote\"nfrom uuid import UUID, uuid4\"nimport anyio\"nfrom anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream\"nfrom pydantic import ValidationError\"nfrom sse_starlette import EventSourceResponse\"nfrom starlette.requests import Request\"nfrom starlette.responses import Response\"nfrom starlette.types import Receive, Scope, Send\"n\"nfrom mcp_python.types import JSONRPCMessage\"n\"nlogger = logging.getLogger(__name__)\"n\"n@asynccontextmanager\"nclass SseServerTransport:\"""