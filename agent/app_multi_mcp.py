import asyncio
import json
import os

from mcp import Resource
from mcp.types import Prompt

from mcp_client import MCPClient
from dial_client import DialClient
from models.message import Message, Role
from prompts import SYSTEM_PROMPT


# OPTIONAL: Support multiple MCP servers
# This version demonstrates how to connect to multiple MCP servers simultaneously

async def main():
    # Dictionary to hold multiple MCP clients
    mcp_clients = {}
    all_tools = []
    all_messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]
    
    # MCP servers to connect to
    mcp_servers = {
        "users-management": "http://localhost:8005/mcp",
        "fetch": "https://remote.mcpservers.org/fetch/mcp"
    }
    
    print("🔌 Connecting to MCP servers...\n")
    
    # Connect to each MCP server
    for server_name, server_url in mcp_servers.items():
        try:
            print(f"Connecting to {server_name} at {server_url}...")
            mcp_client = MCPClient(mcp_server_url=server_url)
            await mcp_client.__aenter__()
            mcp_clients[server_name] = mcp_client
            
            # Get resources
            resources = await mcp_client.get_resources()
            if resources:
                print(f"  📚 Resources from {server_name}:")
                for resource in resources:
                    print(f"    - {resource.name}: {resource.uri}")
            
            # Get tools
            tools = await mcp_client.get_tools()
            print(f"  🔧 Tools from {server_name}:")
            for tool in tools:
                print(f"    - {tool['function']['name']}: {tool['function']['description']}")
            all_tools.extend(tools)
            
            # Get prompts
            prompts = await mcp_client.get_prompts()
            if prompts:
                print(f"  💡 Prompts from {server_name}:")
                for prompt in prompts:
                    print(f"    - {prompt.name}: {prompt.description}")
                    # Get the actual prompt content and add as user message
                    prompt_content = await mcp_client.get_prompt(prompt.name)
                    all_messages.append(Message(
                        role=Role.USER, 
                        content=f"Guidance for {prompt.name} from {server_name}:\n{prompt_content}"
                    ))
            
            print()
        except Exception as e:
            print(f"  ❌ Failed to connect to {server_name}: {e}\n")
    
    if not mcp_clients:
        print("❌ No MCP servers connected. Exiting.")
        return
    
    # Create DialClient with multiple MCP clients
    dial_api_key = os.getenv("DIAL_API_KEY")
    dial_endpoint = os.getenv("DIAL_ENDPOINT")
    
    if not dial_api_key or not dial_endpoint:
        raise ValueError("DIAL_API_KEY and DIAL_ENDPOINT must be set in environment variables")
    
    dial_client = DialClient(
        api_key=dial_api_key,
        endpoint=dial_endpoint,
        tools=all_tools,
        mcp_clients=mcp_clients
    )
    
    # Create console chat
    print("=" * 60)
    print("👤 Multi-MCP User Management Agent")
    print("=" * 60)
    print("Type 'exit' or 'quit' to end the conversation")
    print("You can now search users AND fetch web information!\n")
    
    try:
        while True:
            # Get user input
            user_input = input("👤 You: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit']:
                print("\n👋 Goodbye!")
                break
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Add user message to history
            all_messages.append(Message(role=Role.USER, content=user_input))
            
            # Get AI response
            try:
                ai_response = await dial_client.get_completion(all_messages)
                all_messages.append(ai_response)
                print()
            except Exception as e:
                print(f"❌ Error: {e}\n")
    finally:
        # Clean up - close all MCP clients
        print("\n🔌 Disconnecting from MCP servers...")
        for server_name, client in mcp_clients.items():
            try:
                await client.__aexit__(None, None, None)
                print(f"  ✅ Disconnected from {server_name}")
            except Exception as e:
                print(f"  ⚠️ Error disconnecting from {server_name}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
