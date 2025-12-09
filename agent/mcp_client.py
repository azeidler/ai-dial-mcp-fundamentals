from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent, GetPromptResult, ReadResourceResult, Resource, TextResourceContents, BlobResourceContents, Prompt
from pydantic import AnyUrl


class MCPClient:
    """Handles MCP server connection and tool execution"""

    def __init__(self, mcp_server_url: str) -> None:
        self.mcp_server_url = mcp_server_url
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None

    async def __aenter__(self):
        # 1. Call streamablehttp_client method with mcp_server_url
        self._streams_context = streamablehttp_client(self.mcp_server_url)
        
        # 2. Enter streams context
        read_stream, write_stream, _ = await self._streams_context.__aenter__()
        
        # 3. Create ClientSession
        self._session_context = ClientSession(read_stream, write_stream)
        
        # 4. Enter session context
        self.session = await self._session_context.__aenter__()
        
        # 5. Initialize session and print result
        init_result = await self.session.initialize()
        print(f"✅ MCP Server initialized: {init_result}\n")
        
        # 6. Return self
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Shutdown method - properly close contexts
        if self.session and self._session_context:
            await self._session_context.__aexit__(exc_type, exc_val, exc_tb)
        if self._streams_context:
            await self._streams_context.__aexit__(exc_type, exc_val, exc_tb)

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        
        # 1. Call list_tools
        tools = await self.session.list_tools()
        
        # 2. Return list with dicts according to DIAL specification
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in tools.tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a specific tool on the MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        # 1. Call tool on MCP server
        tool_result: CallToolResult = await self.session.call_tool(tool_name, tool_args)
        
        # 2. Get content at index 0
        content = tool_result.content[0]
        
        # 3. Print result
        print(f"    ⚙️: {content}\n")
        
        # 4. Return based on content type
        if isinstance(content, TextContent):
            return content.text
        else:
            return content

    async def get_resources(self) -> list[Resource]:
        """Get available resources from MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")
        
        try:
            resources_result = await self.session.list_resources()
            return resources_result.resources
        except Exception as e:
            print(f"⚠️ Error getting resources: {e}")
            return []

    async def get_resource(self, uri: AnyUrl) -> str | bytes:
        """Get specific resource content"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")

        # 1. Get resource by uri
        resource_result: ReadResourceResult = await self.session.read_resource(uri)
        
        # 2. Get contents at index 0
        content = resource_result.contents[0]
        
        # 3. Return based on content type
        if isinstance(content, TextResourceContents):
            return content.text
        elif isinstance(content, BlobResourceContents):
            return content.blob
        else:
            return str(content)

    async def get_prompts(self) -> list[Prompt]:
        """Get available prompts from MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")
        
        try:
            prompts_result = await self.session.list_prompts()
            return prompts_result.prompts
        except Exception as e:
            print(f"⚠️ Error getting prompts: {e}")
            return []

    async def get_prompt(self, name: str) -> str:
        """Get specific prompt content"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")
        
        # 1. Get prompt by name
        prompt_result: GetPromptResult = await self.session.get_prompt(name)
        
        # 2. Create variable for combined content
        combined_content = ""
        
        # 3. Iterate through messages
        for message in prompt_result.messages:
            if hasattr(message, 'content'):
                if isinstance(message.content, TextContent):
                    combined_content += message.content.text + "\n"
                elif isinstance(message.content, str):
                    combined_content += message.content + "\n"
        
        # 4. Return combined content
        return combined_content
