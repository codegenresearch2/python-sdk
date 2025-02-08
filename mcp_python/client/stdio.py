import sys
from contextlib import asynccontextmanager

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field

from mcp_python.types import JSONRPCMessage


class StdioServerParameters(BaseModel):
    command: str
    """The executable to run to start the server."""

    args: list[str] = Field(default_factory=list)
    """Command line arguments to pass to the executable."""

    env: dict[str, str] = Field(default_factory=dict)
    """
    The environment to use when spawning the process.

    The environment is NOT inherited from the parent process by default.
    """


@asynccontextmanager
async def stdio_client(server: StdioServerParameters):
    """
    Client transport for stdio: this will connect to a server by spawning a process and communicating with it over stdin/stdout.
    """
    read_stream: MemoryObjectReceiveStream[JSONRPCMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[JSONRPCMessage | Exception]

    write_stream: MemoryObjectSendStream[JSONRPCMessage]
    write_stream_reader: MemoryObjectReceiveStream[JSONRPCMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    process = await anyio.open_process(
        [server.command, *server.args],
        env=server.env,
        stderr=sys.stderr
    )

    async def stdout_reader():
        assert process.stdout, "Opened process is missing stdout"

        try:
            async with read_stream_writer:
                buffer = ""
                async for chunk in TextReceiveStream(process.stdout):
                    lines = (buffer + chunk).split("\n")
                    buffer = lines.pop()

                    for line in lines:
                        try:
                            message = JSONRPCMessage.model_validate_json(line)
                        except Exception as exc:
                            await read_stream_writer.send(exc)
                            continue

                        await read_stream_writer.send(message)
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async def stdin_writer():
        assert process.stdin, "Opened process is missing stdin"

        try:
            async with write_stream_reader:
                async for message in write_stream_reader:
                    json = message.model_dump_json(by_alias=True)
                    await process.stdin.send((json + "\n").encode())
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async with (
        anyio.create_task_group() as tg,
        process,
    ):
        tg.start_soon(stdout_reader)
        tg.start_soon(stdin_writer)
        yield read_stream, write_stream
