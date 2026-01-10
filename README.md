# 麦麦思考插件

**此插件会增加token消耗，让回复变慢，请谨慎开启**
自1.1.0起使用llm判断是否回复，token消耗量在不回复时大大降低

帮助推理能力弱的模型更好地对逻辑内容进行推理，相比于thinking模型更快，且推理是可选的
使用此插件时最好将replyer模型或你将使用的模型设置一个token上限
如果你的模型很强那么这个插件可能不会帮到你

## 配置说明

### 插件信息 `[plugin]`

- `enabled`：是否启用插件（默认 true）
- `version`：插件版本
- `config_version`：配置文件版本
- `use_model`：使用的模型（默认 `replyer`）
- `model_prompt`：工具的部分提示词
- `tool_description`：工具的描述，为llm判断是否思考提供参照

## 项目信息

- 许可证：GPL-v3.0-or-later
- 主页/仓库：https://github.com/MaiM-with-u/maibot
- 反馈：请在仓库提交 Issue
