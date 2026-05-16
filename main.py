import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._contexts_ref = None  # live reference to req.contexts
        self._send_count = 0
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """Store live contexts reference and reset send counter."""
        self._contexts_ref = getattr(req, "contexts", None)
        self._send_count = 0
        logger.info(f"⚠️补救⚠️ on_llm_request: contexts type={type(self._contexts_ref).__name__}, "
                    f"len={len(self._contexts_ref) if self._contexts_ref else 0}")

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """After 2nd send, check live contexts for generate_image tool_call text."""
        self._send_count += 1

        if self._send_count < 2:
            return

        contexts = self._contexts_ref
        if not contexts:
            logger.warning("⚠️补救⚠️ No contexts reference.")
            return

        logger.info(f"⚠️补救⚠️ after_message_sent #2: contexts len={len(contexts)}")

        # Log last 5 messages for debugging
        for i, msg in enumerate(contexts[-5:]):
            if isinstance(msg, dict):
                role = msg.get("role", "?")
                has_tc = "tool_calls" in msg
                content_preview = str(msg.get("content", ""))[:60]
                logger.info(f"⚠️补救⚠️ contexts[-{5-i}]: role={role}, has_tool_calls={has_tc}, content={content_preview}")

        # Search from end for assistant message with generate_image
        for msg in reversed(contexts):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            tool_calls = msg.get("tool_calls", None)

            if role != "assistant" or not tool_calls:
                continue

            has_gen_image = False
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn_name = tc.get("function", {}).get("name", "")
                    if fn_name == "generate_image":
                        has_gen_image = True
                        break

            if not has_gen_image:
                continue

            # Extract text
            content = msg.get("content", "")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text_parts = []
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        text_parts.append(p.get("text", ""))
                text = "\n".join(text_parts)

            logger.info(f"⚠️补救⚠️ FOUND tool_call msg. text={repr(text[:120]) if text else 'EMPTY'}")

            if text and text.strip():
                await event.send(event.plain_result(text.strip()))
                logger.info("⚠️补救⚠️ Correct text sent.")
            else:
                logger.warning("⚠️补救⚠️ Found message but text is empty.")
            return

        logger.info("⚠️补救⚠️ No generate_image tool_call found in live contexts.")
