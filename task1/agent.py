# agent.py
"""Цикл агента (Agent Loop)"""

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from llm import get_llm, SYSTEM_PROMPT
from tools import get_tools
from logger import log


def run_agent(user_message: str) -> str:
    """Запускает агента с задачей"""
    llm = get_llm()
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)

    tools_by_name = {t.name: t for t in tools}

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # Нет вызовов инструментов = агент закончил
        if not response.tool_calls:
            log.agent(response.content)
            return response.content

        # Выполняем инструменты
        for tool_call in response.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]

            log.tool_call(name, args)

            result = tools_by_name[name].invoke(args)
            log.tool_result(result)

            messages.append(ToolMessage(
                content=result,
                tool_call_id=tool_call["id"]
            ))
