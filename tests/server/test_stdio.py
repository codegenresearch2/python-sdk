import io\n\nimport anyio\nimport pytest\n\nfrom mcp_python.server.stdio import stdio_server\nfrom mcp_python.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse\n\n\n@pytest.mark.anyio\nasync def test_stdio_server():\n    stdin = io.StringIO()\n    stdout = io.StringIO()\n\n    messages = [\n        JSONRPCMessage(root=JSONRPCRequest(jsonrpc=\