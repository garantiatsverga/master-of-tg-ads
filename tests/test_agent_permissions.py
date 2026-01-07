"""Тестовый скрипт для проверки механизма ограничения доступа агентов к инструментам."""

import asyncio
from MCPServer import MCPServer, ToolRegistry, SimpleRetryPolicy, InMemoryCachePolicy
from agents.copywriter_agent import CopywriterAgent
from agents.banner_designer_agent import BannerDesignerAgent
from agents.qa_compliance_agent import QAComplianceAgent
from agents.prompt_agent import PromptAgent
import sys
from pathlib import Path

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock инструменты для тестирования
class MockTextGenerateTool:
    def __init__(self):
        self.name = "text.generate"
    
    async def execute(self, **kwargs) -> dict:
        return {"text": f"Generated text for prompt: {kwargs.get('prompt', '')}"}


class MockImageGenerateTool:
    def __init__(self):
        self.name = "image.generate"
    
    async def execute(self, **kwargs) -> dict:
        return {"image_url": f"http://example.com/image_{kwargs.get('prompt', 'default')}.jpg"}


class MockComplianceCheckTool:
    def __init__(self):
        self.name = "compliance.check"
    
    async def execute(self, **kwargs) -> dict:
        return {"is_approved": True, "issues": []}


async def test_agent_permissions():
    """Тестирование ограничения доступа агентов к инструментам"""
    print("Testing agent permissions...")
    
    # Создаем реестр инструментов
    registry = ToolRegistry()
    registry.register(MockTextGenerateTool())
    registry.register(MockImageGenerateTool())
    registry.register(MockComplianceCheckTool())
    
    # Создаем MCPServer
    mcp_server = MCPServer(
        registry=registry,
        retry_policy=SimpleRetryPolicy(),
        cache_policy=InMemoryCachePolicy()
    )
    
    # Устанавливаем разрешения для агентов
    mcp_server.set_agent_permissions("CopywriterAgent", ["text.generate"])
    mcp_server.set_agent_permissions("BannerDesignerAgent", ["image.generate"])
    mcp_server.set_agent_permissions("QAComplianceAgent", ["compliance.check"])
    mcp_server.set_agent_permissions("PromptAgent", [])
    
    # Создаем агентов
    copywriter = CopywriterAgent(mcp_server=mcp_server)
    designer = BannerDesignerAgent(mcp_server=mcp_server)
    qa_agent = QAComplianceAgent(mcp_server=mcp_server)
    prompt_agent = PromptAgent(mcp_server=mcp_server, rules={}, templates={})
    
    # Тест 1: CopywriterAgent может вызывать text.generate
    print("\nTest 1: CopywriterAgent calling text.generate")
    try:
        context = {"target_text_prompt": "Test prompt"}
        result = await copywriter.process(context)
        print(f"[+] Success: {result.get('final_advertising_text', 'No text')}")
    except Exception as e:
        print(f"[-] Failed: {e}")
    
    # Тест 2: CopywriterAgent НЕ может вызывать image.generate
    print("\nTest 2: CopywriterAgent trying to call image.generate (should fail)")
    try:
        # Прямой вызов инструмента, который не разрешён
        await mcp_server.call("image.generate", agent_name="CopywriterAgent", prompt="test")
        print("[-] Failed: Should have raised SecurityError")
    except Exception as e:
        print(f"[+] Success: Correctly blocked - {e}")
    
    # Тест 3: BannerDesignerAgent может вызывать image.generate
    print("\nTest 3: BannerDesignerAgent calling image.generate")
    try:
        context = {"target_image_prompt": "Test image prompt"}
        result = await designer.process(context)
        print(f"[+] Success: {result.get('banner_url', 'No URL')}")
    except Exception as e:
        print(f"[-] Failed: {e}")
    
    # Тест 4: BannerDesignerAgent НЕ может вызывать text.generate
    print("\nTest 4: BannerDesignerAgent trying to call text.generate (should fail)")
    try:
        await mcp_server.call("text.generate", agent_name="BannerDesignerAgent", prompt="test")
        print("[-] Failed: Should have raised SecurityError")
    except Exception as e:
        print(f"[+] Success: Correctly blocked - {e}")
    
    # Тест 5: QAComplianceAgent может вызывать compliance.check
    print("\nTest 5: QAComplianceAgent calling compliance.check")
    try:
        context = {"final_advertising_text": "Test text", "banner_url": "http://example.com/test.jpg"}
        result = await qa_agent.process(context)
        print(f"[+] Success: QA status - {result.get('qa_status', 'No status')}")
    except Exception as e:
        print(f"[-] Failed: {e}")
    
    # Тест 6: QAComplianceAgent НЕ может вызывать image.generate
    print("\nTest 6: QAComplianceAgent trying to call image.generate (should fail)")
    try:
        await mcp_server.call("image.generate", agent_name="QAComplianceAgent", prompt="test")
        print("[-] Failed: Should have raised SecurityError")
    except Exception as e:
        print(f"[+] Success: Correctly blocked - {e}")
    
    # Тест 7: PromptAgent не может вызывать никакие инструменты
    print("\nTest 7: PromptAgent trying to call text.generate (should fail)")
    try:
        await mcp_server.call("text.generate", agent_name="PromptAgent", prompt="test")
        print("[-] Failed: Should have raised SecurityError")
    except Exception as e:
        print(f"[+] Success: Correctly blocked - {e}")
    
    print("\n" + "="*50)
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_agent_permissions())