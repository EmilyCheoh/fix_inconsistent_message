from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._conversation_ref = None
        self._send_count = 0
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """Store conversation reference and reset send counter."""
        self._conversation_ref = getattr(req, "conversation", None)
        self._send_count = 0
        logger.info(f"⚠️补救⚠️ on_llm_request: conversation type={type(self._conversation_ref).__name__}")
        # Inspect conversation object
        if self._conversation_ref:
            conv_attrs = [a for a in dir(self._conversation_ref) if not a.startswith("_")]
            logger.info(f"⚠️补救⚠️ conversation attrs: {conv_attrs}")

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """After each send, increment counter. On 2nd send, inspect conversation for tool_call text."""
        self._send_count += 1
        logger.info(f"⚠️补救⚠️ after_message_sent #{self._send_count}")

        if self._send_count < 2:
            return

        # 2nd send = agent loop complete. Try to read conversation context.
        conv = self._conversation_ref
        if not conv:
            logger.warning("⚠️补救⚠️ No conversation reference stored.")
            return

        # Try common attribute names for message history
        messages = None
        for attr_name in ["messages", "contexts", "history", "chat_history", "message_list"]:
            messages = getattr(conv, attr_name, None)
            if messages:
                logger.info(f"⚠️补救⚠️ Found messages via conv.{attr_name}, count={len(messages)}")
                break

        if not messages:
            # Try calling it
            for method_name in ["get_messages", "get_history", "get_contexts"]:
                method = getattr(conv, method_name, None)
                if callable(method):
                    try:
                        messages = method()
                        logger.info(f"⚠️补救⚠️ Found messages via conv.{method_name}(), count={len(messages)}")
                        break
                    except Exception as e:
                        logger.info(f"⚠️补救��️ conv.{method_name}() failed: {e}")

        if not messages:
            logger.warning("⚠️补救⚠️ Could not find messages in conversation object.")
            # Log all attributes for next debug round
            conv_attrs = [a for a in dir(conv) if not a.startswith("_")]
            logger.info(f"⚠️补救⚠️ conv attrs: {conv_attrs}")
            return

        # Search for assistant message with generate_image tool_call
        for i, msg in enumerate(reversed(messages)):
            # Handle both dict and object forms
            if isinstance(msg, dict):
                role = msg.get("role", "")
                tool_calls = msg.get("tool_calls", None)
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "")
                tool_calls = getattr(msg, "tool_calls", None)
                content = getattr(msg, "content", "")

            if role != "assistant" or not tool_calls:
                continue

            # Check if any tool_call is generate_image
            has_gen_image = False
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {}).get("name", "")
                else:
                    fn = getattr(getattr(tc, "function", None), "name", "")
                if fn == "generate_image":
                    has_gen_image = True
                    break

            if not has_gen_image:
                continue

            # Found it. Extract text.
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    p["text"] if isinstance(p, dict) else getattr(p, "text", "")
                    for p in content
                    if (isinstance(p, dict) and p.get("type") == "text") or
                       (hasattr(p, "type") and getattr(p, "type") == "text")
                )

            logger.info(f"⚠️补救⚠️ FOUND tool_call msg. text={repr(text[:100]) if text else 'EMPTY'}")

            if text and text.strip():
                await event.send(event.plain_result(text.strip()))
                logger.info("⚠️补救⚠️ Text sent to user.")
            else:
                logger.warning("⚠️补救⚠️ tool_call message found but text is empty.")
            return

        logger.info("⚠️补救⚠️ No assistant message with generate_image tool_call found in context.")
