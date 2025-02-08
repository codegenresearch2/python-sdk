python\# mcp_python/shared/session.py\\nimport anyio.lowlevel\\nfrom anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream\\nfrom pydantic import BaseModel\\nfrom mcp_python.shared.exceptions import McpError\\nfrom mcp_python.types import (\\n    ClientNotification, ClientRequest, ClientResult,\\n    ErrorData, JSONRPCError, JSONRPCMessage, JSONRPCNotification,\\n    JSONRPCRequest, JSONRPCResponse, RequestParams, ServerNotification,\\n    ServerRequest, ServerResult)\\\\\n\\nSendRequestT = TypeVar('SendRequestT', ClientRequest, ServerRequest)\\\\\nSendResultT = TypeVar('SendResultT', ClientResult, ServerResult)\\\\\nSendNotificationT = TypeVar('SendNotificationT', ClientNotification, ServerNotification)\\\\\nReceiveRequestT = TypeVar('ReceiveRequestT', ClientRequest, ServerRequest)\\\\\nReceiveResultT = TypeVar('ReceiveResultT', bound=BaseModel)\\\\\nReceiveNotificationT = TypeVar('ReceiveNotificationT', ClientNotification, ServerNotification)\\\\\n\\nRequestId = str | int\\n\\nclass RequestResponder(Generic[ReceiveRequestT, SendResultT]):\\n    """Implements a request responder for MCP sessions."""\\n    def __init__(self,\\n        request_id: RequestId,\\n        request_meta: RequestParams.Meta | None,\\n        request: ReceiveRequestT,\\n        session: 'BaseSession',\\n    ) -> None:\"\"\"Initializes the RequestResponder with the given request details.\"\"\"\\n        self.request_id = request_id\\n        self.request_meta = request_meta\\n        self.request = request\\n        self._session = session\\n        self._responded = False\\n\\n    async def respond(self, response: SendResultT | ErrorData) -> None:\"\"\"Responds to the request with the given response or error data.\"\"\"\\n        assert not self._responded, 'Request already responded to'\\n        self._responded = True\\n\\n        await self._session._send_response(request_id=self.request_id, response=response)\\\\\n\\nclass BaseSession(AbstractAsyncContextManager, Generic[SendRequestT, SendNotificationT, SendResultT, ReceiveRequestT, ReceiveNotificationT]):\\n    """Implements an MCP session on top of read/write streams."""\\n    _response_streams: dict[RequestId, MemoryObjectSendStream[JSONRPCResponse | JSONRPCError]]\\n    _request_id: int\\n\\n    def __init__(self,\\n        read_stream: MemoryObjectReceiveStream[JSONRPCMessage | Exception],\\n        write_stream: MemoryObjectSendStream[JSONRPCMessage],\\n        receive_request_type: type[ReceiveRequestT],\\n        receive_notification_type: type[ReceiveNotificationT],\\n    ) -> None:\"\"\"Initializes the BaseSession with the given streams and types.\"\"\"\\n        self._read_stream = read_stream\\n        self._write_stream = write_stream\\n        self._response_streams = {}\\n        self._request_id = 0\\n        self._receive_request_type = receive_request_type\\n        self._receive_notification_type = receive_notification_type\\n\\n        self._incoming_message_stream_writer, self._incoming_message_stream_reader = anyio.create_memory_object_stream[RequestResponder[ReceiveRequestT, SendResultT] | ReceiveNotificationT | Exception]();\\n\\n    async def __aenter__(self):\\n        """Enters the context manager, starting the session."""\\n        self._task_group = anyio.create_task_group()\\n        await self._task_group.__aenter__()\\n        self._task_group.start_soon(self._receive_loop)\\n        return self\\n\\n    async def __aexit__(self, exc_type, exc_val, exc_tb):\\n        """Exits the context manager, stopping the session."""\\n        self._task_group.cancel_scope.cancel()\\n        return await self._task_group.__aexit__(exc_type, exc_val, exc_tb)\\\\\n\\n    async def send_request(self,\\n        request: SendRequestT,\\n        result_type: type[ReceiveResultT],\\n    ) -> ReceiveResultT:\"\"\"Sends a request and waits for a response.\"\"\"\\n        request_id = self._request_id\\n        self._request_id = request_id + 1\\n\\n        response_stream, response_stream_reader = anyio.create_memory_object_stream[JSONRPCResponse | JSONRPCError](1)\\n        self._response_streams[request_id] = response_stream\\n\\n        jsonrpc_request = JSONRPCRequest(jsonrpc='2.0', id=request_id, **request.model_dump(by_alias=True, exclude_none=True, mode='json'))\\n\\n        await self._write_stream.send(JSONRPCMessage(jsonrpc_request))\\n\\n        response_or_error = await response_stream_reader.receive()\\n        if isinstance(response_or_error, JSONRPCError):\\n            raise McpError(response_or_error.error)\\\\\n        else:\\n            return result_type.model_validate(response_or_error.result)\\\\\n\\n    async def send_notification(self, notification: SendNotificationT) -> None:\"\"\"Sends a notification to the session.\"\"\"\\n        jsonrpc_notification = JSONRPCNotification(jsonrpc='2.0', **notification.model_dump(by_alias=True, exclude_none=True, mode='json'))\\n\\n        await self._write_stream.send(JSONRPCMessage(jsonrpc_notification))\\n\\n    async def _send_response(self,\\n        request_id: RequestId,\\n        response: SendResultT | ErrorData,\\n    ) -> None:\"\"\"Sends a response or error to the request.\"\"\"\\n        if isinstance(response, ErrorData):\\n            jsonrpc_error = JSONRPCError(jsonrpc='2.0', id=request_id, error=response)\\n            await self._write_stream.send(JSONRPCMessage(jsonrpc_error))\\n        else:\\n            jsonrpc_response = JSONRPCResponse(jsonrpc='2.0', id=request_id, result=response.model_dump(by_alias=True, exclude_none=True, mode='json'))\\n            await self._write_stream.send(JSONRPCMessage(jsonrpc_response))\\n\\n    async def _receive_loop(self) -> None:\"\"\"Continually receives and processes messages from the session.\"\"\"\\n        async with (self._read_stream, self._write_stream, self._incoming_message_stream_writer):\\n            async for message in self._read_stream:\\n                if isinstance(message, Exception):\\n                    await self._incoming_message_stream_writer.send(message)\\\\\n                elif isinstance(message.root, JSONRPCRequest):\\n                    validated_request = self._receive_request_type.model_validate(message.root.model_dump(by_alias=True, exclude_none=True, mode='json'))\\n                    responder = RequestResponder(request_id=message.root.id,\\n                        request_meta=validated_request.root.params._meta if validated_request.root.params else None,\\n                        request=validated_request,\\n                        session=self)\\\\\n\\n                    await self._received_request(responder)\\\\\n                    if not responder._responded:\\n                        await self._incoming_message_stream_writer.send(responder)\\\\\n                elif isinstance(message.root, JSONRPCNotification):\\n                    notification = self._receive_notification_type.model_validate(message.root.model_dump(by_alias=True, exclude_none=True, mode='json'))\\n\\n                    await self._received_notification(notification)\\\\\n                    await self._incoming_message_stream_writer.send(notification)\\\\\n                else: # Response or error\\n                    stream = self._response_streams.pop(message.root.id, None)\\\\\n                    if stream:\\n                        await stream.send(message.root)\\\\\n                    else:\\n                        await self._incoming_message_stream_writer.send(RuntimeError(f'Received response with an unknown request ID: {message}'))\\n\\n    async def _received_request(self,\\n        responder: RequestResponder[ReceiveRequestT, SendResultT]\\\\\n    ) -> None:\"\"\"Handles a received request.\"\"\"\\n        pass\\n\\n    async def _received_notification(self, notification: ReceiveNotificationT) -> None:\"\"\"Handles a received notification.\"\"\"\\n        pass\\n\\n    async def send_progress_notification(self,\\n        progress_token: str | int,\\n        progress: float,\\n        total: float | None = None,\\n    ) -> None:\"\"\"Sends a progress notification.\"\"\"\\n        pass\\n\\n    @property\\n    def incoming_messages(self) -> MemoryObjectReceiveStream[RequestResponder[ReceiveRequestT, SendResultT] | ReceiveNotificationT | Exception]:\\n        """Returns the incoming messages stream.\"\"\"\\n        return self._incoming_message_stream_reader\\n