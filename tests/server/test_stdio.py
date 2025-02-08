import io\\nimport anyio\\nimport pytest\\nfrom mcp_python.server.stdio import stdio_server\\nfrom mcp_python.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse\\n\\n@pytest.mark.anyio\\nasync def test_stdio_server():\\n    stdin = io.StringIO()\\n    stdout = io.StringIO()\\n\\n    messages = [\\n        JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=1, method=\\"ping\\"))\\n    ]\\n\\n    for message in messages:\\n        stdin.write(message.model_dump_json() + \\\"\\n\\")\\\n    stdin.seek(0)\\\n\\n    async with stdio_server(stdin=anyio.AsyncFile(stdin), stdout=anyio.AsyncFile(stdout)) as (read_stream, write_stream):\\n        received_messages = []\\n        async with read_stream:\\n            async for message in read_stream:\\n                if isinstance(message, Exception):\\n                    raise message\\n                received_messages.append(message)\\\n\\n    assert len(received_messages) == 1\\n    assert received_messages[0] == JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\\"2.0\", id=1, method=\\"ping\\"))