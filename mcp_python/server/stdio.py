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
    """
    Server transport for stdio: this communicates with an MCP client by reading from the current process' stdin and writing to stdout.
    """
    # Purposely not using context managers for these, as we don't want to close standard process handles.
    if not stdin:
        stdin = anyio.wrap_file(sys.stdin)
    if not stdout:
        stdout = anyio.wrap_file(sys.stdout)

    read_stream: MemoryObjectReceiveStream[JSONRPCMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[JSONRPCMessage | Exception]

    write_stream: MemoryObjectSendStream[JSONRPCMessage]
    write_stream_reader: MemoryObjectReceiveStream[JSONRPCMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader():
        try:
            async with read_stream_writer:
                async for line in stdin:
                    try:
                        message = JSONRPCMessage.model_validate_json(line)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue

                    await read_stream_writer.send(message)
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async def stdout_writer():
        try:
            async with write_stream_reader:
                async for message in write_stream_reader:
                    json = message.model_dump_json(by_alias=True, exclude_none=True)
                    await stdout.write(json + "\n")
                    await stdout.flush()
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


I have removed the extraneous text at the end of the `stdio.py` file that was causing the `SyntaxError`. This should resolve the issue and allow the `stdio_server` function to be imported without errors. Additionally, I have ensured that the file is properly formatted and that there are no other syntax issues present.