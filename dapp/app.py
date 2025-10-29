# app.py — WeatherWise Agent (style + live Databricks agent streaming + progress)
import os
import json
import streamlit as st
from typing import Any, Dict, Iterator, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# BASIC CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WeatherWise Agent",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# SESSION
# ──────────────────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, Any]] = []
if "tool_log" not in st.session_state:
    st.session_state.tool_log: List[Dict[str, Any]] = []
if "chat_input_seed" not in st.session_state:
    st.session_state.chat_input_seed = 0  # avoid duplicate widget IDs

# Databricks endpoint name (environment)
SERVING_ENDPOINT = os.getenv("SERVING_ENDPOINT")

# ──────────────────────────────────────────────────────────────────────────────
# THEME (CSS)
# ──────────────────────────────────────────────────────────────────────────────
def get_theme_css(dark_mode=True):
    if dark_mode:
        bg_color = "#1a1a1a"; text_color = "#e8e8e8"; header_bg = "#0d0d0d"; header_border = "#2a2a2a"
        user_msg_bg = "#2d2d2d"; user_msg_border = "#3a3a3a"; thought_color = "#888"
        tool_bg = "#1e2837"; tool_border = "#2a3441"; tool_param_bg = "#151e2b"
        code_bg = "#2d2d2d"; t_bg = "#2d2d2d"; t_text = "#e8e8e8"; t_brd = "#3a3a3a"
    else:
        bg_color = "#f5f5f5"; text_color = "#2c2c2c"; header_bg = "#ffffff"; header_border = "#e0e0e0"
        user_msg_bg = "#f0f0f0"; user_msg_border = "#d0d0d0"; thought_color = "#666"
        tool_bg = "#ffffff"; tool_border = "#e0e0e0"; tool_param_bg = "#f8f8f8"
        code_bg = "#f0f0f0"; t_bg = "#ffffff"; t_text = "#2c2c2c"; t_brd = "#d0d0d0"

    return f"""
<style>
  .stApp {{ background-color:{bg_color}; color:{text_color}; }}
  #MainMenu, footer, header {{ visibility:hidden; }}

  .main .block-container {{
    max-width: 850px; padding: 4rem 3rem 6rem 3rem;  /* bottom padding for input */
  }}

  .title-section {{ text-align:center; margin:80px 0 60px 0; }}
  .main-title {{
    font-size:48px; font-weight:700; color:{text_color}; margin-bottom:20px;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  }}
  .subtitle {{ font-size:18px; color:{thought_color}; font-weight:400; }}

  .chat-container {{ max-width:750px; margin:0 auto; padding:20px 0; }}

  .app-header {{
    position:fixed; top:20px; left:20px; z-index:1000; display:flex; align-items:center; gap:10px;
    background:{header_bg}; padding:8px 16px; border-radius:20px; border:1px solid {header_border};
    box-shadow:0 2px 8px rgba(0,0,0,.1);
  }}
  .app-status {{ width:8px; height:8px; background:#10a37f; border-radius:50%; display:inline-block; }}
  .app-title {{ color:{text_color}; font-size:14px; font-weight:600; margin:0; }}

  .stButton {{ position:fixed; bottom:20px; left:20px; z-index:1001; }}
  .stButton > button {{
    background:{header_bg}; border:1px solid {header_border}; border-radius:50%;
    width:40px; height:40px; padding:0; font-size:18px; color:{text_color};
    box-shadow:0 2px 8px rgba(0,0,0,.1); display:flex; align-items:center; justify-content:center;
  }}
  .stButton > button:hover {{ opacity:.8; }}

  .message {{ margin-bottom:32px; }}
  .user-message {{
    background:{user_msg_bg}; color:{text_color}; padding:14px 18px; border-radius:18px; display:inline-block;
    max-width:85%; line-height:1.5; font-size:15px; margin-bottom:24px; border:1px solid {user_msg_border};
  }}
  .assistant-section {{ margin-bottom:36px; }}
  .thought-label {{ color:{thought_color}; font-size:13px; font-style:italic; margin-bottom:10px; }}

  .assistant-text {{ color:{text_color}; line-height:1.7; font-size:15px; margin-top:8px; }}
  .assistant-text p {{ margin-bottom:16px; }}

  .tool-call {{
    background:{tool_bg}; border:1px solid {tool_border}; border-radius:8px; padding:12px 16px; margin:12px 0; font-size:13px;
  }}
  .tool-name {{ color:#10a37f; font-weight:600; font-family:'SF Mono','Monaco','Courier New',monospace; margin-bottom:8px; word-break:break-word; }}
  .tool-params {{
    color:{thought_color}; font-family:'SF Mono','Monaco','Courier New',monospace; font-size:12px; margin:6px 0; padding:8px;
    background:{tool_param_bg}; border-radius:4px; overflow-x:auto; white-space:pre-wrap; word-break:break-word;
  }}
  .tool-result {{ color:{thought_color}; font-size:12px; margin-top:8px; font-style:italic; white-space:pre-wrap; word-break:break-word; }}

  /* Blend/clear any band under chat input */
  [data-testid="stBottomBlockContainer"],
  [data-testid="stChatInput"],
  .stChatInputContainer,
  .stChatMessageInputContainer {{ background:transparent !important; box-shadow:none !important; border-top:none !important; }}

  [data-testid="stChatInput"] textarea {{
    background-color:{t_bg} !important;
    color:{t_text} !important;
    border:1px solid {t_brd} !important;
    border-radius:20px !important;
  }}
</style>
"""

st.markdown(get_theme_css(st.session_state.dark_mode), unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HEADER BADGE + CENTER HERO
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="app-header">
  <span class="app-status"></span>
  <div class="app-title">Jackson & Jackson</div>
</div>
<div class="title-section">
  <div class="main-title">WeatherWise Agent</div>
  <div class="subtitle">I'm here to help with your medtech supply chain activities</div>
</div>
""",
    unsafe_allow_html=True,
)

# Theme toggle
if st.button("🌙" if not st.session_state.dark_mode else "☀️", key="theme_toggle"):
    st.session_state.dark_mode = not st.session_state.dark_mode
    st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# RENDER HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def render_user_message(content: str):
    st.markdown(
        f"""<div class="message"><div class="user-message">{content}</div></div>""",
        unsafe_allow_html=True,
    )

def render_assistant_message_html(html: str):
    st.markdown(
        f"""<div class="assistant-section"><div class="assistant-text">{html}</div></div>""",
        unsafe_allow_html=True,
    )

def render_tool_card(tool_name: str, params: dict | str, result: Optional[str] = None):
    if isinstance(params, (dict, list)):
        try:
            params_text = json.dumps(params, ensure_ascii=False, indent=2)
        except Exception:
            params_text = str(params)
    else:
        params_text = str(params)
    result_html = f'<div class="tool-result">→ {result}</div>' if result else ""
    st.markdown(
        f"""
<div class="tool-call">
  <div class="tool-name">{tool_name}</div>
  <div class="tool-params">{params_text}</div>
  {result_html}
</div>
""",
        unsafe_allow_html=True,
    )

def _coerce_json(s):
    if isinstance(s, str):
        try:
            return json.loads(s)
        except Exception:
            return s
    return s

def normalize_stream_item(item: Any) -> List[Dict[str, Any]]:
    """Map various agent stream shapes → unified events."""
    out: List[Dict[str, Any]] = []
    if not isinstance(item, dict):
        return out
    msg = item.get("delta") or item.get("message") or item.get("chunk") or item

    # tool result
    if isinstance(msg, dict) and msg.get("role") == "tool":
        out.append({"type": "tool_result", "message": msg})
        return out

    # assistant delta (content and/or tool_calls)
    if isinstance(msg, dict) and msg.get("role") == "assistant":
        if msg.get("tool_calls"):
            out.append({"type": "tool_call", "message": msg})
        if msg.get("content"):
            out.append({"type": "assistant", "message": msg})
        return out

    # sometimes tool_calls live directly on the chunk
    if isinstance(msg, dict) and "tool_calls" in msg:
        out.append({"type": "tool_call", "message": {"role": "assistant", **msg}})
        return out

    # explicit final marker
    if isinstance(msg, dict) and (msg.get("is_final") or msg.get("event") == "final"):
        out.append({"type": "final", "messages": msg.get("messages", [])})
        return out

    return out

def stream_events(endpoint_name: str,
                  messages: List[Dict[str, Any]],
                  max_tokens: int = 700) -> Iterator[Dict[str, Any]]:
    """Yield normalized streaming events; fallback to non-stream."""
    from mlflow.deployments import get_deploy_client
    client = get_deploy_client("databricks")

    try:
        stream = client.predict(
            endpoint=endpoint_name,
            inputs={"messages": messages, "max_tokens": max_tokens, "stream": True},
        )
        for raw in stream:
            for ev in normalize_stream_item(raw):
                yield ev
        yield {"type": "final", "messages": []}
        return
    except Exception:
        pass

    # fallback (non-stream)
    res = client.predict(
        endpoint=endpoint_name,
        inputs={"messages": messages, "max_tokens": max_tokens},
    )
    if isinstance(res, dict) and "messages" in res:
        yield {"type": "final", "messages": res["messages"]}
        return
    if isinstance(res, dict) and "choices" in res:
        yield {"type": "final", "messages": [res["choices"][0]["message"]]}
        return
    yield {"type": "final", "messages": [{"role": "assistant", "content": "(No response)"}]}

# ──────────────────────────────────────────────────────────────────────────────
# CHAT HISTORY
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for m in st.session_state.messages:
    if m["role"] == "user":
        render_user_message(m["content"])
    elif m["role"] == "assistant":
        render_assistant_message_html(m["content"])

# Persistent Tool Calls log (always visible)
tool_log_container = st.container()
with tool_log_container:
    if st.session_state.tool_log:
        st.markdown("#### Tool Calls")
        for entry in st.session_state.tool_log:
            render_tool_card(entry["name"], entry.get("args", {}), entry.get("result"))

# Warn if endpoint missing
if not SERVING_ENDPOINT:
    st.warning("Set the SERVING_ENDPOINT environment variable to your Databricks agent endpoint name.")

# ──────────────────────────────────────────────────────────────────────────────
# LIVE INPUT (single, keyed to avoid duplicate-ID errors)
# ──────────────────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask anything…", key=f"chat_input_{st.session_state.chat_input_seed}")

if prompt and SERVING_ENDPOINT:
    # User bubble
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_user_message(prompt)

    # “Thinking…” + progress (moves on tokens and tool events)
    thinking_ph = st.empty()
    thinking_ph.markdown('<div class="thought-label">Thinking…</div>', unsafe_allow_html=True)
    prog_ph = st.progress(0.02)      # start a little above zero so it’s visible
    prog = {"v": 0.02}               # mutable tracker

    def bump(step=0.08, cap=0.96):
        prog["v"] = min(cap, prog["v"] + step)
        try:
            prog_ph.progress(prog["v"])
        except Exception:
            pass

    # Assistant area
    assistant_ph = st.empty()
    assistant_text_accum = ""

    # Stream
    try:
        for ev in stream_events(SERVING_ENDPOINT, st.session_state.messages, max_tokens=700):
            etype = ev.get("type")

            if etype == "assistant":
                piece = ev["message"].get("content") or ""
                if piece:
                    if assistant_text_accum and not assistant_text_accum.endswith(("\n", " ")):
                        assistant_text_accum += " "
                    assistant_text_accum += piece
                    assistant_ph.markdown(
                        f'<div class="assistant-section"><div class="assistant-text">{assistant_text_accum}</div></div>',
                        unsafe_allow_html=True,
                    )
                    bump(0.02)

            elif etype == "tool_call":
                for tc in (ev["message"].get("tool_calls") or []):
                    fn = (tc.get("function") or {}).get("name", "tool")
                    args = _coerce_json((tc.get("function") or {}).get("arguments"))
                    thinking_ph.markdown(
                        f'<div class="thought-label">Calling <b>{fn}</b>…</div>',
                        unsafe_allow_html=True,
                    )
                    # persist + re-render tool log immediately
                    st.session_state.tool_log.append({"name": fn, "args": args})
                    with tool_log_container:
                        st.markdown("#### Tool Calls")
                        for entry in st.session_state.tool_log:
                            render_tool_card(entry["name"], entry.get("args", {}), entry.get("result"))
                    bump(0.12)

            elif etype == "tool_result":
                name = ev["message"].get("name") or "tool"
                content = ev["message"].get("content")
                result_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
                # attach to most recent matching call if possible
                for entry in reversed(st.session_state.tool_log):
                    if entry["name"] == name and "result" not in entry:
                        entry["result"] = result_text
                        break
                else:
                    st.session_state.tool_log.append({"name": name, "args": "(result)", "result": result_text})
                with tool_log_container:
                    st.markdown("#### Tool Calls")
                    for entry in st.session_state.tool_log:
                        render_tool_card(entry["name"], entry.get("args", {}), entry.get("result"))
                bump(0.12)

            elif etype == "final":
                thinking_ph.empty()
                prog_ph.progress(1.0)
                final_msgs = ev.get("messages", [])
                final_assistant = next(
                    (m for m in reversed(final_msgs)
                     if m.get("role") == "assistant" and not m.get("tool_calls")),
                    None,
                )
                final_text = (final_assistant or {}).get("content") or assistant_text_accum or "(no text)"
                st.session_state.messages.append({"role": "assistant", "content": final_text})
                assistant_ph.markdown(
                    f'<div class="assistant-section"><div class="assistant-text">{final_text}</div></div>',
                    unsafe_allow_html=True,
                )
                break
    except Exception:
        # Fallback (non-stream)
        from mlflow.deployments import get_deploy_client
        client = get_deploy_client("databricks")
        res = client.predict(
            endpoint=SERVING_ENDPOINT,
            inputs={"messages": st.session_state.messages, "max_tokens": 700},
        )
        thinking_ph.empty()
        prog_ph.progress(1.0)
        if isinstance(res, dict) and "messages" in res:
            final_text = next(
                (m.get("content") for m in reversed(res["messages"]) if m.get("role") == "assistant"),
                "(No response)",
            )
        elif isinstance(res, dict) and "choices" in res:
            final_text = res["choices"][0]["message"].get("content", "(No response)")
        else:
            final_text = "(No response)"
        st.session_state.messages.append({"role": "assistant", "content": final_text})
        assistant_ph.markdown(
            f'<div class="assistant-section"><div class="assistant-text">{final_text}</div></div>',
            unsafe_allow_html=True,
        )

    # Bump the input key so reruns don’t hit duplicate element IDs
    st.session_state.chat_input_seed += 1

# Close chat container
st.markdown("</div>", unsafe_allow_html=True)