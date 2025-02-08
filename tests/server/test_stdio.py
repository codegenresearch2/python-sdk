import io\\n\\nimport anyio\\nimport pytest\\n\\nfrom mcp_python.server.stdio import stdio_server\\nfrom mcp_python.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse\\n\\n\\n@pytest.mark.anyio\\nasync def test_stdio_server():\\n    stdin = io.StringIO()\\n    stdout = io.StringIO()\\n\\n    messages = [\\n        JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=1, method=\\"ping\\"))\\n        JSONRPCMessage(root=JSONRPCResponse(jsonrpc=\\"2.0\", id=2, result={})\\n    ]\\n\\n    for message in messages:\\n        stdin.write(message.model_dump_json(exclude_none=True) + \\\"\\n\")\\n    stdin.seek(0) \\n\\n    async with stdio_server(stdin=anyio.AsyncFile(stdin), stdout=anyio.AsyncFile(stdout)) as (read_stream, write_stream):\\n        received_messages = []\\n        async with read_stream:\\n            async for message in read_stream:\\n                if isinstance(message, Exception):\\n                    raise message\\n                received_messages.append(message) \\n                if len(received_messages) == 2:\\n                    break\\n\\n        assert len(received_messages) == 2\\n        assert received_messages[0] == JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=1, method=\\"ping\\"))\\n        assert received_messages[1] == JSONRPCMessage(root=JSONRPCResponse(jsonrpc=\\"2.0\", id=2, result={})\\n\\n        responses = [\\n            JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=3, method=\\"ping\\"))\\n            JSONRPCMessage(root=JSONRPCResponse(jsonrpc=\\"2.0\", id=4, result={})\\n        ]\\n\\n        async with write_stream:\\n            for response in responses:\\n                await write_stream.send(response) \\n\\n    stdout.seek(0) \\n    output_lines = stdout.readlines()\\n    assert len(output_lines) == 2\\n\\n    received_responses = [JSONRPCMessage.model_validate_json(line.strip()) for line in output_lines] \\n    assert len(received_responses) == 2\\n    assert received_responses[0] == JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=3, method=\\"ping\\"))\\n    assert received_responses[1] == JSONRPCMessage(root=JSONRPCResponse(jsonrpc=\\"2.0\", id=4, result={})\\n