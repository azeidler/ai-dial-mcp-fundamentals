import json
from collections import defaultdict
from typing import Any

from openai import AsyncAzureOpenAI

from models.message import Message, Role
from mcp_client import MCPClient


class DialClient:
    """Handles AI model interactions and integrates with MCP client(s)"""

    def __init__(self, api_key: str, endpoint: str, tools: list[dict[str, Any]], mcp_clients: dict[str, MCPClient] | MCPClient):
        self.tools = tools
        # Support both single MCP client (backwards compatible) and multiple clients
        if isinstance(mcp_clients, MCPClient):
            self.mcp_clients = {"default": mcp_clients}
        else:
            self.mcp_clients = mcp_clients
        
        self.openai = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2025-01-01-preview"
        )

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        for delta in tool_deltas:
            idx = delta.index
            if delta.id: tool_dict[idx]["id"] = delta.id
            if delta.function.name: tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function.arguments: tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type: tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _stream_response(self, messages: list[Message]) -> Message:
        """Stream OpenAI response and handle tool calls"""
        stream = await self.openai.chat.completions.create(
            **{
                "model": "gpt-4o",
                "messages": [msg.to_dict() for msg in messages],
                "tools": self.tools,
                "temperature": 0.0,
                "stream": True
            }
        )

        content = ""
        tool_deltas = []

        print("🤖: ", end="", flush=True)

        async for chunk in stream:
            delta = chunk.choices[0].delta

            # Stream content
            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content

            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

        print()
        return Message(
            role=Role.AI,
            content=content,
            tool_calls=self._collect_tool_calls(tool_deltas) if tool_deltas else []
        )

    async def get_completion(self, messages: list[Message]) -> Message:
        """Process user query with streaming and tool calling"""
        ai_message: Message = await self._stream_response(messages)

        # Check if any tool calls are present and perform them
        if ai_message.tool_calls:
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            # recursively calling agent with tool messages
            return await self.get_completion(messages)

        return ai_message

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """Execute tool calls using MCP client(s)"""
        # 1. Iterate through tool_calls
        for tool_call in ai_message.tool_calls:
            # 2. Get tool name and arguments
            tool_name = tool_call["function"]["name"]
            tool_args_json = tool_call["function"]["arguments"]
            tool_call_id = tool_call["id"]
            
            try:
                # Parse JSON arguments
                tool_args = json.loads(tool_args_json)
                
                # 3. Find the appropriate MCP client for this tool
                mcp_client = self._find_mcp_client_for_tool(tool_name)
                
                if not mcp_client:
                    raise ValueError(f"No MCP client found for tool: {tool_name}")
                
                # Call MCP client tool
                print(f"    🔧 Calling tool: {tool_name}")
                result = await mcp_client.call_tool(tool_name, tool_args)
                
                # Add successful tool message
                messages.append(Message(
                    role=Role.TOOL,
                    content=str(result),
                    tool_call_id=tool_call_id,
                    name=tool_name
                ))
            except Exception as e:
                # Add error tool message as fallback
                error_message = f"Error calling tool {tool_name}: {str(e)}"
                print(f"    ❌ {error_message}")
                messages.append(Message(
                    role=Role.TOOL,
                    content=error_message,
                    tool_call_id=tool_call_id,
                    name=tool_name
                ))
    
    def _find_mcp_client_for_tool(self, tool_name: str) -> MCPClient | None:
        """Find which MCP client has the requested tool"""
        # For single client (backwards compatibility)
        if "default" in self.mcp_clients and len(self.mcp_clients) == 1:
            return self.mcp_clients["default"]
        
        # For multiple clients, check each tool list
        for client_name, client in self.mcp_clients.items():
            # Check if this tool exists in any of the registered tools
            for tool in self.tools:
                if tool["function"]["name"] == tool_name:
                    # In a more sophisticated implementation, you'd track which client
                    # provides which tool. For now, we try each client until one works.
                    return client
        
        # If we have multiple clients, try the first one that might work
        # In production, you'd want a proper tool->client mapping
        return list(self.mcp_clients.values())[0] if self.mcp_clients else None