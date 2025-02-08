import anyio\\\nimport pytest\\\\\nfrom mcp_python.client.session import ClientSession\\\\\nfrom mcp_python.types import (\\\\\n    ClientNotification,\\\\\n    InitializedNotification,\\\\\n    JSONRPCMessage,\\\\\n)\\\\\n\\\\n@pytest.mark.anyio\\\\\nasync def test_client_session_initialize():\\\\\n    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[JSONRPCMessage](1)\\\\\n    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[JSONRPCMessage](1)\\\\\n\\\\n    initialized_notification = None\\\\\n\\\\n    async def mock_server():\\\\\n        nonlocal initialized_notification\\\\\n\\\\n        jsonrpc_request = await client_to_server_receive.receive()\\\\\n        assert isinstance(jsonrpc_request.root, JSONRPCRequest)\\\n        request = ClientRequest.model_validate(jsonrpc_request.model_dump(by_alias=True, exclude_none=True, mode='json'))\\\\\n        assert isinstance(request.root, InitializeRequest)\\\n\\\\n        result = ServerResult(\\\n            InitializeResult(\\\n                protocolVersion=1,\\\\\n                capabilities=ServerCapabilities(\\\n                    logging=None,\\\\\n                    resources=None,\\\\\n                    tools=None,\\\\\n                    experimental=None,\\\\\n                    prompts=None,\\\\\n                ),\\\\\n                serverInfo=Implementation(name='mock-server', version='0.1.0'),\\\\\n            )\\\n        )\\\n\\\\n        async with server_to_client_send:\\\\\n            await server_to_client_send.send(JSONRPCMessage(JSONRPCResponse(jsonrpc='2.0', id=jsonrpc_request.root.id, result=result.model_dump(by_alias=True, exclude_none=True, mode='json'))))\\\\\n            jsonrpc_notification = await client_to_server_receive.receive()\\\\\n            assert isinstance(jsonrpc_notification.root, JSONRPCNotification)\\\n            initialized_notification = ClientNotification.model_validate(jsonrpc_notification.model_dump(by_alias=True, exclude_none=True, mode='json'))\\\\\n\\\\n    async def listen_session():\\\\\n        async for message in session.incoming_messages:\\\\\n            if isinstance(message, Exception):\\\\\n                raise message\\\\\n\\\\n    async with (ClientSession(server_to_client_receive, client_to_server_send) as session, anyio.create_task_group() as tg):\\\\\n        tg.start_soon(mock_server)\\\\\n        tg.start_soon(listen_session)\\\\\n        result = await session.initialize()\\\\\n\\\\n    assert isinstance(result, InitializeResult)\\\\\n    assert result.protocolVersion == 1\\\\\n    assert isinstance(result.capabilities, ServerCapabilities)\\\\\\n    assert result.serverInfo == Implementation(name='mock-server', version='0.1.0')\\\\\n\\\\n    assert initialized_notification\\\\\n    assert isinstance(initialized_notification.root, InitializedNotification)\\\\\n