import json
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# Normalize role names that appear in different JSON exports
_ROLE_ALIASES = {
    "human": ("human", "user"),
    "ai": ("ai", "assistant", "bot"),
    "system": ("system",),
}

def _normalize_role_value(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).lower()
    for canonical, aliases in _ROLE_ALIASES.items():
        if s in aliases or s == canonical:
            return canonical
    return None

def _msg_role(msg: Dict[str, Any]) -> Optional[str]:
    # Check common fields that carry role/type
    if "message" in msg:
        msg = msg.get("message", {})
    for key in ("type", "role", "sender", "from"):
        if key in msg:
            r = _normalize_role_value(msg.get(key))
            if r:
                return r
    # Fallback: sometimes LangChain messages are typed by class name in 'name' or missing field
    # If message contains 'tool_calls' or 'response_metadata' it's often an ai message
    if "tool_calls" in msg or "response_metadata" in msg:
        return "ai"
    return None

def _get_content_from_message(msg: Dict[str, Any]) -> Optional[str]:
    # Most JSONs use 'content'; some embed content differently - extend as needed
    return msg.get("message", {}).get("content", "")

# Core retrieval functions

def first_message_content(messages: List[Dict[str, Any]], target: str = "human") -> Optional[str]:
    """Return the content string of the first message with role `target` (human|ai|system)."""
    target = target.lower()
    for m in messages:
        if _msg_role(m) == target:
            return _get_content_from_message(m)
    return None

def last_message_content(messages: List[Dict[str, Any]], target: str = "ai") -> Optional[str]:
    """Return the content string of the last message with role `target` (human|ai|system)."""
    target = target.lower()
    for m in reversed(messages):
        if _msg_role(m) == target:
            return _get_content_from_message(m)
    return None

def first_langchain_message(messages: List[Dict[str, Any]], target: str = "user"):
    """Return the first message as a LangChain message object (HumanMessage/AIMessage/SystemMessage)."""
    target = target.lower()
    for m in messages:
        if _msg_role(m) == target:
            content = _get_content_from_message(m) or ""
            addl = m.get("additional_kwargs", {})
            if target == "human":
                return HumanMessage(content=content, additional_kwargs=addl)
            if target == "ai":
                return AIMessage(content=content, additional_kwargs=addl)
            if target == "system":
                return SystemMessage(content=content, additional_kwargs=addl)
    return None

def last_langchain_message(messages: List[Dict[str, Any]], target: str = "human"):
    """Return the last message as a LangChain message object (HumanMessage/AIMessage/SystemMessage)."""
    target = target.lower()
    for m in reversed(messages):
        if _msg_role(m) == target:
            content = _get_content_from_message(m) or ""
            addl = m.get("additional_kwargs", {})
            if target == "human":
                return HumanMessage(content=content, additional_kwargs=addl)
            if target == "ai":
                return AIMessage(content=content, additional_kwargs=addl)
            if target == "system":
                return SystemMessage(content=content, additional_kwargs=addl)
    return None

# Example usage with your JSON
json_str = '{"messages": [{"content":"hi","type":"human"},{"content":"hello","type":"ai"},{"content":"how can I help?","type":"human"}]}'
data = json.loads(json_str)
msgs = data.get("messages", [])

print("first human content:", first_message_content(msgs, "human"))
print("last human content:", last_message_content(msgs, "human"))
print("first AI LangChain message:", first_langchain_message(msgs, "ai"))
print("last human LangChain message:", last_langchain_message(msgs, "human"))