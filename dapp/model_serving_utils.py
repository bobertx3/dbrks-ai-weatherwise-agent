from mlflow.deployments import get_deploy_client
from databricks.sdk import WorkspaceClient

def _get_endpoint_task_type(endpoint_name: str) -> str:
    """Get the task type of a serving endpoint."""
    w = WorkspaceClient()
    ep = w.serving_endpoints.get(endpoint_name)
    return ep.task

def is_endpoint_supported(endpoint_name: str) -> bool:
    """Check if the endpoint has a supported task type."""
    task_type = _get_endpoint_task_type(endpoint_name)
    supported_task_types = ["agent/v1/chat", "agent/v2/chat", "llm/v1/chat"]
    return task_type in supported_task_types

def _validate_endpoint_task_type(endpoint_name: str) -> None:
    """Validate that the endpoint has a supported task type."""
    if not is_endpoint_supported(endpoint_name):
        raise Exception(
            f"Detected unsupported endpoint type for this basic chatbot template. "
            f"This chatbot template only supports chat completions-compatible endpoints. "
            f"For a richer chatbot template with support for all conversational endpoints on Databricks, "
            f"see https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app"
        )

def _query_endpoint(endpoint_name: str, messages: list[dict[str, str]], max_tokens) -> list[dict[str, str]]:
    """Calls a model serving endpoint."""
    _validate_endpoint_task_type(endpoint_name)
    
    res = get_deploy_client('databricks').predict(
        endpoint=endpoint_name,
        inputs={'messages': messages, "max_tokens": max_tokens},
    )
    if "messages" in res:
        return res["messages"]
    elif "choices" in res:
        choice_message = res["choices"][0]["message"]
        choice_content = choice_message.get("content")
        
        # Case 1: The content is a list of structured objects
        if isinstance(choice_content, list):
            combined_content = "".join([part.get("text", "") for part in choice_content if part.get("type") == "text"])
            reformatted_message = {
                "role": choice_message.get("role"),
                "content": combined_content
            }
            return [reformatted_message]
        
        # Case 2: The content is a simple string
        elif isinstance(choice_content, str):
            return [choice_message]
    raise Exception("This app can only run against:"
                    "1) Databricks foundation model or external model endpoints with the chat task type (described in https://docs.databricks.com/aws/en/machine-learning/model-serving/score-foundation-models#chat-completion-model-query)"
                    "2) Databricks agent serving endpoints that implement the conversational agent schema documented "
                    "in https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent")

def query_endpoint(endpoint_name, messages, max_tokens):
    """
    Query a chat-completions or agent serving endpoint
    If querying an agent serving endpoint that returns multiple messages, this method
    returns the last message
    ."""
    return _query_endpoint(endpoint_name, messages, max_tokens)[-1]


# --- add to model_serving_utils.py ---

from typing import Dict, Iterable, Iterator, List, Any, Union
from mlflow.deployments import get_deploy_client

def iter_agent_events(endpoint_name: str,
                      messages: List[Dict[str, Any]],
                      max_tokens: int = 400) -> Iterator[Dict[str, Any]]:
    """
    Yields a normalized stream of events from a Databricks chat/agent endpoint.

    Event schema (examples):
      {"type":"assistant","message": {...}}         # assistant delta or full message
      {"type":"tool_call","message": {...}}         # assistant turn that includes tool_calls
      {"type":"tool_result","message": {...}}       # role='tool' message
      {"type":"final","messages": [ ... ]}          # fallback final message list (non-stream)
    """
    _validate_endpoint_task_type(endpoint_name)
    client = get_deploy_client("databricks")

    # 1) Try native streaming (if supported in your workspace build)
    try:
        stream = client.predict(
            endpoint=endpoint_name,
            inputs={"messages": messages, "max_tokens": max_tokens, "stream": True},
        )
        # Some clients yield dict events; others yield message shards.
        for item in stream:
            # Normalize several possible shapes:
            if isinstance(item, dict):
                # Common Databricks agent chunk: {"delta": {...}} or {"message": {...}}
                msg = item.get("delta") or item.get("message")
                if isinstance(msg, dict):
                    role = msg.get("role")
                    if role == "assistant":
                        if msg.get("tool_calls"):
                            yield {"type": "tool_call", "message": msg}
                        else:
                            yield {"type": "assistant", "message": msg}
                    elif role == "tool":
                        yield {"type": "tool_result", "message": msg}
                    else:
                        yield {"type": "other", "message": msg}
                else:
                    # Unknown chunk; surface raw for debugging
                    yield {"type": "raw", "chunk": item}
            else:
                # Generator returned a non-dict; surface raw
                yield {"type": "raw", "chunk": item}
        return
    except TypeError:
        # Client doesn't support stream=True → fall through to non-stream
        pass
    except Exception as e:
        # If streaming handshake fails for other reasons, keep going with fallback
        # (You can log e if you wish.)
        pass

    # 2) Fallback: single shot, then emit events in sequence so UI can still “step through”
    res = get_deploy_client("databricks").predict(
        endpoint=endpoint_name,
        inputs={"messages": messages, "max_tokens": max_tokens},
    )
    if "messages" in res:
        msgs = res["messages"]
    elif "choices" in res:
        msgs = [res["choices"][0]["message"]]
    else:
        yield {"type": "raw", "chunk": res}
        yield {"type": "final", "messages": []}
        return

    # Emit each message as the appropriate event type
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            if m.get("tool_calls"):
                yield {"type": "tool_call", "message": m}
            else:
                yield {"type": "assistant", "message": m}
        elif role == "tool":
            yield {"type": "tool_result", "message": m}
        else:
            yield {"type": "other", "message": m}

    yield {"type": "final", "messages": msgs}

