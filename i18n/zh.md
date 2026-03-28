# LexiForge

## 概览

LexiForge 是一个由 AI 辅助的桌面语言学习原型，基于 `PySide6`、`Qt WebEngine` 和 HTML/CSS/JavaScript UI 构建。应用允许学习者描述自己想学的内容，流式展示由 OpenAI 生成的词汇卡片，然后通过两阶段课程流水线用这些卡片构建课程。

## 项目结构

```text
LexiForge/
|-- main.py                         # 应用入口
|-- settings.yaml                   # 语言、模型和流水线选项的运行时配置
|-- app/                            # 应用外壳、路由、日志和配置辅助模块
|   |-- backend.py
|   |-- router.py
|   |-- settings.py
|   |-- logging_config.py
|   |-- exception_logging.py
|   `-- language_registry.py
|-- models/                         # 词卡、宏观计划步骤和生成练习的类型化模型
|-- pipeline/                       # 词汇生成、宏观课程规划、任务生成与解析
|-- llm_gateway/                    # OpenAI 客户端封装和缓存辅助工具
|-- prompts/                        # 生成流水线使用的提示词模板
|-- dev_fixtures/                   # 用于开发和调试的可选本地 fixtures
|-- ui/
|   |-- controllers/                # 屏幕控制器，包括设置、加载和课程流程
|   |-- services/                   # 后台 worker 和 UI 侧服务
|   |-- views/                      # HTML/CSS/JS 页面
|   `-- assets/                     # 共享主题文件和静态资源
`-- i18n/                           # 项目的本地化文档
```

## 工作流程

1. 学习者在设置页面输入学习请求。
2. 应用生成词汇卡片，并在到达时显示在 UI 中。
3. 当学习者开始课程时，应用会打开加载页面。
4. 后台 worker 会根据所选卡片创建课程宏观计划。
5. 任务生成器再把该计划展开为课程流程页面中的具体练习。

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Glebhl/LexiForge.git
cd LexiForge
```

### 2. 创建并激活虚拟环境

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

在项目根目录创建一个 `.env` 文件：

```env
OPENAI_API_KEY=your_openai_api_key_here
```

如果没有 `OPENAI_API_KEY`，词卡生成和实时课程生成将无法工作。

### 5. 调整运行时设置

编辑 `settings.yaml` 以选择课程语言、学习者等级、模型分配和流水线选项：

```yaml
lesson:
  language: en
  lerner_language: ru
  learner_level: B2
models:
  card_generation: gpt-5.4-nano
  lesson_planning: o3
  task_generation: gpt-5.4-mini
  answer_matcher: gpt-5.4-nano
pipeline:
  card_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  lesson_planning:
    reasoning_effort: low
    text_verbosity: null
    service_tier: flex
  task_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  answer_matcher:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
```

### 6. 运行应用

```bash
python main.py
```

## 开发说明

- `dev_fixtures` 可以在开发期间预加载词卡，或用 fixture 数据替换实时课程生成。
- `prompts/en/` 中的提示词文件同时驱动宏观规划和任务生成。

调试时可以把以下参数加入 `.env`：

```env
GLOSIUM_DEV_CARDS=1
GLOSIUM_DEV_MACRO_PLAN=1
GLOSIUM_DEV_LESSON=1
GLOSIUM_DEV_CARDS_FILE=dev_fixtures/cards.json
GLOSIUM_DEV_MACRO_PLAN_FILE=dev_fixtures/macro_plan.txt
GLOSIUM_DEV_LESSON_FILE=dev_fixtures/lesson.json
```

## 状态

该项目仍处于原型阶段。当前版本支持 AI 驱动的词汇生成、课程宏观规划和任务内容生成。

## 路线图

计划中的下一步包括：

- 添加 AI 引导和错误解释
- 支持更多语言
- 添加语法支持
- 添加除英文之外的本地化
- 添加进度跟踪

## 贡献

欢迎提交 issue、建议和 pull request。
