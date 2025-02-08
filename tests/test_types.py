from mcp_python.types import JSONRPCMessage, JSONRPCRequest\\\ndef test_jsonrpc_request():\\\n    json_data = {\"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {\"protocolVersion": 1, "capabilities": {\"batch": None, "sampling": None}, "clientInfo": {\"name": "mcp_python", "version": "0.1.0"}}} \\\n    request = JSONRPCMessage.model_validate(json_data)\\\\\\n    assert isinstance(request.root, JSONRPCRequest)\\\\\\n    assert request.root.jsonrpc == "2.0"\\\\\\n    assert request.root.id == 1\\\\\\n    assert request.root.method == "initialize"\\\\\\n    assert request.root.params is not None\\\\\\n    assert request.root.params["protocolVersion"] == 1