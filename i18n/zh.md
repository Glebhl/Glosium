# LexiForge

LexiForge 是一个基于 `PySide6`、`Qt WebEngine` 和 HTML/CSS/JavaScript 的桌面语言学习原型。应用会通过 OpenAI 生成词汇卡片，然后基于所选内容启动课程流程。

## 当前能力

- 通过 OpenAI Responses API 生成词汇卡片
- 支持 explanation、matching、translation、filling 和 question 类型的课程任务
- 提供用于卡片、宏观计划和临时课程计划的开发 fixtures

## 项目结构

```text
LexiForge/
|-- main.py                         # 应用入口
|-- app/                            # 应用基础设施与共享运行时工具
|   |-- backend.py                  # 通过 Qt 连接 Python 与 UI
|   |-- router.py                   # 页面导航
|   |-- logging_config.py           # 日志配置
|   |-- exception_logging.py        # 全局异常与回调日志
|   `-- language_registry.py        # 语言注册表与辅助函数
|-- dev_fixtures/                   # 本地 fixture 数据与加载配置
|   |-- settings.py
|   |-- cards.json
|   |-- macro_plan.txt
|   `-- lesson.json
|-- llm_gateway/                    # OpenAI 封装与缓存
|-- pipeline/                       # 卡片、课程计划与任务生成
|-- prompts/                        # Prompt 模板
`-- ui/
    |-- controllers/                # 页面控制器
    |-- services/                   # UI 层辅助服务
    |-- views/                      # HTML/CSS/JS 页面
    `-- assets/                     # 字体、图标与共享样式
```

## 快速开始

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
