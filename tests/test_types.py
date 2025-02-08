from mcp_python.types import ClientRequest, JSONRPCMessage, JSONRPCRequest


def test_jsonrpc_request():
    json_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": 1,
            "capabilities": {
                "batch": None,
                "sampling": None
            },
            "clientInfo": {
                "name": "mcp_python",
                "version": "0.1.0"
            }
        }
    }

    request = JSONRPCMessage.model_validate(json_data)
    assert isinstance(request.root, JSONRPCRequest)
    ClientRequest.model_validate(request.model_dump(by_alias=True, exclude_none=True))

    assert request.root.jsonrpc == "2.0"
    assert request.root.id == 1
    assert request.root.method == "initialize"
    assert request.root.params is not None
    assert request.root.params["protocolVersion"] == 1