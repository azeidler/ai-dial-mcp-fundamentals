import asyncio
import json
import os

from mcp import Resource
from mcp.types import Prompt

from mcp_client import MCPClient
from dial_client import DialClient
from models.message import Message, Role
from prompts import SYSTEM_PROMPT


# https://remote.mcpservers.org/fetch/mcp
# Pay attention that `fetch` doesn't have resources and prompts

async def main():
    # 1. Create MCP client and open connection to the MCP server
    async with MCPClient(mcp_server_url="http://localhost:8005/mcp") as mcp_client:
        
        # 2. Get Available MCP Resources and print them
        resources = await mcp_client.get_resources()
        print("📚 Available MCP Resources:")
        for resource in resources:
            print(f"  - {resource.name}: {resource.uri}")
        print()
        
        # 3. Get Available MCP Tools, assign to tools variable, print as well
        tools = await mcp_client.get_tools()
        print("🔧 Available MCP Tools:")
        for tool in tools:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")
        print()
        
        # 4. Create DialClient
        dial_api_key = os.getenv("DIAL_API_KEY")
        dial_endpoint = os.getenv("DIAL_ENDPOINT")
        
        if not dial_api_key or not dial_endpoint:
            raise ValueError("DIAL_API_KEY and DIAL_ENDPOINT must be set in environment variables")
        
        dial_client = DialClient(
            api_key=dial_api_key,
            endpoint=dial_endpoint,
            tools=tools,
            mcp_clients=mcp_client
        )
        
        # 5. Create list with messages and add SYSTEM_PROMPT
        messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]
        
        # 6. Add Prompts from MCP server as User messages
        prompts = await mcp_client.get_prompts()
        print("💡 Available MCP Prompts:")
        for prompt in prompts:
            print(f"  - {prompt.name}: {prompt.description}")
            # Get the actual prompt content and add as user message
            prompt_content = await mcp_client.get_prompt(prompt.name)
            messages.append(Message(role=Role.USER, content=f"Guidance for {prompt.name}:\n{prompt_content}"))
        print()
        
        # 7. Create console chat (infinite loop + ability to exit + preserve message history)
        print("=" * 60)
        print("👤 User Management Agent")
        print("=" * 60)
        print("Type 'exit' or 'quit' to end the conversation\n")
        
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
            messages.append(Message(role=Role.USER, content=user_input))
            
            # Get AI response
            try:
                ai_response = await dial_client.get_completion(messages)
                messages.append(ai_response)
                print()
            except Exception as e:
                print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
