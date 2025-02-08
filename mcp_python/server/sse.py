import logging\"nfrom contextlib import asynccontextmanager\"nfrom typing import Any\"nfrom urllib.parse import quote\"nfrom uuid import UUID, uuid4\"nimport anyio\"nfrom anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream\"nfrom pydantic import ValidationError\"nfrom sse_starlette import EventSourceResponse\"nfrom starlette.requests import Request\"nfrom starlette.responses import Response\"nfrom starlette.types import Receive, Scope, Send\"n\nfrom mcp_python.types import JSONRPCMessage\n\nlogger = logging.getLogger(__name__)\n\n\nclass SseServerTransport:\"""\n SSE server transport for MCP. This class provides _two_ ASGI applications, suitable to be used with a framework like Starlette and a server like Hypercorn:\"""\n\n _endpoint: str\n _read_stream_writers: dict[UUID, MemoryObjectSendStream[JSONRPCMessage | Exception]]\n\n def __init__(self, endpoint: str) -> None:\"""\n Creates a new SSE server transport, which will direct the client to POST messages to the relative or absolute URL given.\"""\n\n super().__init__()\n self._endpoint = endpoint\n self._read_stream_writers = {}\n logger.debug(f"SseServerTransport initialized with endpoint: {endpoint}")\n\n @asynccontextmanager\n async def connect_sse(self, scope: Scope, receive: Receive, send: Send):\"""\n Sets up a new SSE stream to send server messages to the client.\"""\n if scope['type'] != 'http':\n logger.error('connect_sse received non-HTTP request')\n raise ValueError('connect_sse can only handle HTTP requests')\n\n logger.debug('Setting up SSE connection')\n read_stream: MemoryObjectReceiveStream[JSONRPCMessage | Exception]\n read_stream_writer: MemoryObjectSendStream[JSONRPCMessage | Exception]\n\n write_stream: MemoryObjectSendStream[JSONRPCMessage]\n write_stream_reader: MemoryObjectReceiveStream[JSONRPCMessage]\n\n read_stream_writer, read_stream = anyio.create_memory_object_stream(0)\n write_stream, write_stream_reader = anyio.create_memory_object_stream(0)\n\n session_id = uuid4()\n session_uri = f"{quote(self._endpoint)}?session_id={session_id.hex}"\n self._read_stream_writers[session_id] = read_stream_writer\n logger.debug(f"Created new session with ID: {session_id}")\n\n sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream(0, dict[str, Any])\n\n async def sse_writer():\n logger.debug('Starting SSE writer')\n async with sse_stream_writer, write_stream_reader:\n await sse_stream_writer.send({'event': 'endpoint', 'data': session_uri})\n logger.debug(f"Sent endpoint event: {session_uri}")\n\n async for message in write_stream_reader:\n logger.debug(f"Sending message via SSE: {message}")\n await sse_stream_writer.send({"event": 'message', "data": message.model_dump_json(by_alias=True, exclude_none=True)})\n\n response = EventSourceResponse(content=sse_stream_reader, data_sender_callable=sse_writer)\n logger.debug('Starting SSE response task')\n async with anyio.create_task_group() as tg:\n tg.start_soon(response, scope, receive, send)\n\n logger.debug('Yielding read and write streams')\n yield (read_stream, write_stream)\n\n async def handle_post_message(self, scope: Scope, receive: Receive, send: Send) -> None:\"""\n Handles incoming POST messages that link to a previously-established SSE session.\"""\n logger.debug('Handling POST message')\n request = Request(scope, receive)\n\n session_id_param = request.query_params.get('session_id')\n if session_id_param is None:\n logger.warning('Received request without session_id')\n response = Response('session_id is required', status_code=400)\n return await response(scope, receive, send)\n\n try:\n session_id = UUID(hex=session_id_param)\n logger.debug(f"Parsed session ID: {session_id}")\n except ValueError:\n logger.warning(f"Received invalid session ID: {session_id_param}")\n response = Response('Invalid session ID', status_code=400)\n return await response(scope, receive, send)\n\n writer = self._read_stream_writers.get(session_id)\n if not writer:\n logger.warning(f"Could not find session for ID: {session_id}")\n response = Response('Could not find session', status_code=404)\n return await response(scope, receive, send)\n\n json = await request.json()\n logger.debug(f"Received JSON: {json}")\n\n try:\n message = JSONRPCMessage.model_validate(json)\n logger.debug(f"Validated client message: {message}")\n except ValidationError as err:\n logger.error(f"Failed to parse message: {err}")\n response = Response('Could not parse message', status_code=400)\n await response(scope, receive, send)\n await writer.send(err)\n return\n\n logger.debug(f"Sending message to writer: {message}")\n response = Response('Accepted', status_code=202)\n await response(scope, receive, send)\n await writer.send(message)\n