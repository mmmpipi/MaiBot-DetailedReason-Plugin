from typing import List, Tuple, Type

from src.plugin_system import (
    BasePlugin,
    BaseTool,
    ComponentInfo,
    ConfigField,
    ToolParamType,
    register_plugin,
    get_logger,
)
from src.plugin_system.apis import llm_api


logger = get_logger("detailed_reason")


class DetailedReasonTool(BaseTool):
    """详细推理工具"""

    name = "detailed_reason_tool"
    description = "当内容出现需要逻辑推理的数学，急转弯内容时使用此工具"
    parameters = [
        ("question", ToolParamType.STRING, "要推理的主要问题或内容", True, None),
        ("context", ToolParamType.STRING, "相关的上下文信息（可选）", False, None),
    ]
    available_for_llm = True

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
            prompt += "\n\n对以上内容易错的地方进行答疑，按问题复杂程度进行解答"

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
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "reason": {
            "use_model": ConfigField(type=str, default="replyer", description="使用的模型"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件包含的组件列表"""
        return [
            (DetailedReasonTool.get_tool_info(), DetailedReasonTool),
        ]
