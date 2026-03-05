# 硬件数据手册解析归档 Agent (hw_datasheet_agent)

专为嵌入式硬件工程师打造的自动化工具，自动解析硬件芯片/模组数据手册、通信协议文档，生成结构化、标准化的技术归档文档，大幅降低硬件开发前期的文档整理成本。

## 核心功能

✅ **多格式文档兼容**：支持 PDF/DOCX/TXT 格式的硬件手册智能加载与解析  
✅ **配置化管理**：API Key、输入输出路径、生成格式全配置化，无需修改代码  
✅ **多格式归档输出**：支持 Markdown/Word/Excel 三种格式的归档文档生成  
✅ **命令行增强**：支持通过命令行指定待解析文档，无需修改配置文件  
✅ **工程化能力**：完整的日志系统、进度可视化、异常处理兜底，稳定可靠  
✅ **Git 规范管理**：双分支开发规范，API Key 安全隔离，符合工业级开发流程  

## 快速开始

### 1. 环境准备

- Python 3.10 及以上版本  
- 有效的 DeepSeek API Key（可从 [DeepSeek 开放平台](https://platform.deepseek.com) 获取）

### 2. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yzlx-zm/hardware_datasheet_read_agent.git
cd hardware_datasheet_agent

# 安装依赖库
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置文件

#### Windows (PowerShell)

```powershell
copy config.yaml.example config.yaml
```

#### Linux / macOS

```bash
cp config.yaml.example config.yaml
```

然后打开 `config.yaml`，填入你的 DeepSeek API Key，按需调整其他配置项。

### 4. 放入待解析文档

将需要解析的硬件数据手册或通信协议文档放入 `input_docs` 目录。

### 5. 运行使用

#### 基本用法

```bash
python hw_datasheet_agent.py
```

该命令会使用配置文件中指定的默认文档。

#### 高级用法

1. 解析 `input_docs` 目录中的指定文档：
   ```bash
   python hw_datasheet_agent.py -f FS5708-PALM.pdf
   ```
2. 解析指定绝对路径的文档：
   ```bash
   python hw_datasheet_agent.py -f D:\硬件手册\3D人脸识别模组协议.pdf
   ```
3. 自定义输出文档名称：
   ```bash
   python hw_datasheet_agent.py -f FS5708-PALM.pdf -o "FS5708掌静脉模组通信协议归档"
   ```

### 6. 查看结果

生成的归档文档会自动保存在 `output_archive` 目录下，按时间戳创建子文件夹，包含 Markdown、Word 和 Excel 三种格式的文件。

## 项目目录结构

```
hardware_datasheet_read_agent/
├── input_docs/          # 待解析的硬件文档存放目录（目录结构可提交，内部文档不上传 Git）
├── output_archive/      # 自动生成：归档文档输出目录
├── agent_logs/          # 自动生成：程序运行日志目录
├── .gitignore           # Git 忽略规则配置
├── config.yaml          # 私密配置文件（不上传 Git）
├── config.yaml.example  # 配置文件模板（可上传 Git）
├── hw_datasheet_agent.py# 主程序核心代码
├── requirements.txt     # 项目依赖库列表
└── README.md            # 项目说明文档
```

## 配置文件说明

`config.yaml` 核心配置项：

| 配置项                      | 说明                                                          |
|-----------------------------|---------------------------------------------------------------|
| `llm.api_key`               | DeepSeek API Key                                               |
| `llm.model_name`            | 调用的模型名称，默认 `deepseek-chat`                           |
| `llm.temperature`           | 模型温度参数，越低输出越严谨，硬件文档建议 0.05–0.1           |
| `document.input_dir`        | 待解析文档的根目录，默认 `input_docs`                         |
| `document.input_file`       | 默认解析的文档文件名                                           |
| `document.output_base_name` | 输出文档基础名称，留空则自动根据输入文件名生成               |
| `document.output_formats`   | 输出格式列表，支持 `markdown`/`word`/`excel`                 |
| `archive.use_timestamp_folder` | 是否按时间戳创建归档子文件夹，避免文件覆盖                |
| `archive.archive_root_dir`  | 归档文档根目录，默认 `output_archive`                        |
| `logging.level`             | 日志级别，支持 `DEBUG`/`INFO`/`WARNING`/`ERROR`             |
| `logging.log_dir`           | 日志文件存放目录，默认 `agent_logs`                          |

## 许可证

本项目仅供学习和开发使用，请勿用于商业用途。
