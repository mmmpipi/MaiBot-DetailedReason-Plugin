from typing import Any, Dict, List, Optional, Tuple, Type

from src.plugin_system import (
    BasePlugin,
    BaseTool,
    ComponentInfo,
    ConfigField,
    ToolParamType,
    register_plugin,
    get_logger,
)
from src.plugin_system.apis import config_api, llm_api, message_api, tool_api
from src.plugin_system.base.base_events_handler import BaseEventHandler
from src.plugin_system.base.component_types import CustomEventHandlerResult, EventType, MaiMessages


logger = get_logger("detailed_reason")


class DetailedReasonHandler(BaseEventHandler):
    event_type = EventType.POST_LLM
    handler_name = "detailed_reason_handler"
    handler_description = "检测是否有逻辑类问题并思考"
    weight = 100
    intercept_message = True

    def find_content(self, content: str) -> Tuple[bool, str | None]:
        if content.startswith("true"):
            text = content[4:]
            return True, text
        elif content.startswith("false"):
            return False, None
        else:
            logger.warning("未能提取参数")
            return False, None

    async def execute(
        self, message: MaiMessages | None
    ) -> Tuple[bool, bool, Optional[str], Optional[CustomEventHandlerResult], Optional[MaiMessages]]:
        if not message or not message.llm_prompt or not message.stream_id:
            return True, True, None, None, None

        logger.info("开始判断消息")

        text_message = message.plain_text

        logger.info("原始消息内容：" + text_message)

        ask_prompt = f"""
请在下列消息中查找是否含有数学，脑筋急转弯等需要逻辑推理的问题：

消息内容:{text_message}

如果你发现了有需要解答的问题，输出true，并紧跟着你发现的问题；
以下是示例的问题：
- 5根半筷子有几个端
- 9.8和9.11哪个大
如果你没有发现需要解答的问题，输出false
**示例**
true9.8和9.11哪个大
true5根半筷子有几个端
false
"""
        try:
            models = llm_api.get_available_models()

            task_cfg = models.get(self.get_config("reason_event.use_model"))
            if not task_cfg:
                logger.warning("模型配置不可用")
                return True, True, None, None, None
            success, content, _, _ = await llm_api.generate_with_model(
                prompt=ask_prompt, model_config=task_cfg, request_type="detailed_reason.event.post"
            )

            if not (success and content):
                logger.warning("模型请求失败")
                return True, True, None, None, None

            logger.info("模型原始回复：" + content)

            need_ask, question = self.find_content(content)
            if not need_ask:
                return True, True, None, None, None
            tool = tool_api.get_tool_instance("detailed_reason_tool")
            if not tool:
                logger.warning("未能获取工具")
                return True, True, None, None, None
            result = await tool.direct_execute(question=question)

            new_prompt = result["content"] + "\n\n" + message.llm_prompt
            message.modify_llm_prompt(new_prompt, suppress_warning=True)

            return True, True, None, None, message

        except Exception as e:
            logger.error(f"执行失败: {e}")
            return True, True, None, None, None


class DetailedReasonTool(BaseTool):
    """详细推理工具"""

    name = "detailed_reason_tool"
    description = "推理需要严谨推理的数学问题"
    parameters = [
        ("question", ToolParamType.STRING, "要推理的主要问题或内容", True, None),
        ("context", ToolParamType.STRING, "相关的上下文信息（可选）", False, None),
    ]
    available_for_llm = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = self.get_config("reason.tool_description", self.description)
        self.available_for_llm = self.get_config("reason.available_for_llm", False)

    async def execute(self, function_args: dict) -> dict:
        """执行工具"""
        question = function_args.get("question", "")
        context = function_args.get("context", "")

        if not question:
            return {"name": self.name, "content": "请提供要推理的主要内容"}

        try:
            models = llm_api.get_available_models()
            task_cfg = models.get(self.get_config("reason.use_model"))
            if not task_cfg:
                logger.warning("模型配置不可用")
                return {"name": self.name, "content": "模型配置不可用"}

            prompt = question
            if context:
                prompt += f"\n\n[补充上下文]\n{context}"
            prompt += "\n\n" + self.get_config("reason.model_prompt", "对以上内容进行细节答疑")

            logger.info("思考调用prompt：" + prompt)

            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=task_cfg,
                request_type="detailed_reason.tool",
            )
            content = content.strip() + "\n\n**以上是你的推理过程，请优先参考**\n"
            if success and content:
                return {"name": self.name, "content": content.strip()}
            return {"name": self.name, "content": "生成解释失败"}

        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"name": self.name, "content": f"执行出错: {str(e)}"}


@register_plugin
class DetailedReasonPlugin(BasePlugin):
    plugin_name: str = "detailed_reason"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = "config.toml"

    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件基本信息",
        "reason": "思考配置",
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="detailed_reason", description="插件名称"),
            "version": ConfigField(type=str, default="1.1.0", description="插件版本"),
            "config_version": ConfigField(type=str, default="1.1.0", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "reason": {
            "use_model": ConfigField(type=str, default="replyer", description="使用的模型"),
            "model_prompt": ConfigField(type=str, default="对以上内容进行细节答疑", description="模型提示词尾部"),
            "tool_description": ConfigField(
                type=str,
                default="推理需要严谨推理的数学问题",
                description="工具的描述，为llm判断是否思考提供参照",
            ),
            "available_for_llm": ConfigField(type=bool, default=False, description="是否提供给工具调用模型"),
        },
        "reason_event": {
            "use_model": ConfigField(type=str, default="utils", description="使用的模型"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件包含的组件列表"""
        return [
            (DetailedReasonTool.get_tool_info(), DetailedReasonTool),
            (DetailedReasonHandler.get_handler_info(), DetailedReasonHandler),
        ]
