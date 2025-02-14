import sys
from contextlib import asynccontextmanager

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp_python.types import JSONRPCMessage


@asynccontextmanager
async def stdio_server(
    stdin: anyio.AsyncFile | None = None, stdout: anyio.AsyncFile | None = None
):
    """\n    Server transport for stdio: this communicates with an MCP client by reading from the current process' stdin and writing to stdout.\n    """
    # Purposely not using context managers for these, as we don't want to close standard process handles.\n    if not stdin:\n        stdin = anyio.wrap_file(sys.stdin)\n    if not stdout:\n        stdout = anyio.wrap_file(sys.stdout)\n\n    read_stream: MemoryObjectReceiveStream[JSONRPCMessage | Exception]\n    read_stream_writer: MemoryObjectSendStream[JSONRPCMessage | Exception]\n\n    write_stream: MemoryObjectSendStream[JSONRPCMessage]\n    write_stream_reader: MemoryObjectReceiveStream[JSONRPCMessage]\n\n    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)\n    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)\n\n    async def stdin_reader():\n        try:\n            async with read_stream_writer:\n                async for line in stdin:\n                    try:\n                        message = JSONRPCMessage.model_validate_json(line)\n                    except Exception as exc:\n                        await read_stream_writer.send(exc)\n                        continue\n\n                    await read_stream_writer.send(message)\n        except anyio.ClosedResourceError:\n            await anyio.lowlevel.checkpoint()\n\n    async def stdout_writer():\n        try:\n            async with write_stream_reader:\n                async for message in write_stream_reader:\n                    json = message.model_dump_json(by_alias=True, exclude_none=True)\n                    await stdout.write(json + "\n")\n                    await stdout.flush()\n        except anyio.ClosedResourceError:\n            await anyio.lowlevel.checkpoint()\n\n    async with anyio.create_task_group() as tg:\n        tg.start_soon(stdin_reader)\n        tg.start_soon(stdout_writer)\n        yield read_stream, write_stream