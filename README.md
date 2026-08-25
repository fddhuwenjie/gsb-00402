# CBOM Analyzer - 密码资产清单分析平台

基于 YARA 特征文件，对开源代码进行密码学函数检测，自动生成密码资产清单（CBOM - Cryptographic Bill of Materials）。

## How to Run

### 环境要求
- Docker 20.10+
- Docker Compose v2+

### 一键启动

```bash
docker-compose up --build -d
```

启动后访问：
- **管理后台**: http://localhost:8081
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **数据库**: PostgreSQL @ localhost:5432

### 停止 / 清理

```bash
docker-compose down          # 停止
docker-compose down -v       # 停止并删除数据卷
```

### 方式二：命令行工具（无需 Docker）

```bash
cd backend
pip install -r requirements.txt

# 使用项目自带的测试样例进行分析
python cli.py -y ../test/test_rules.yar -c ../test/ -l python -o report.json

# 或指定自己的代码和特征文件
python cli.py -y crypto.yar -c ./your_code -l python -o report.json
```

### 运行单元测试

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

## Services

| 服务 | 技术栈 | 端口 | 说明 |
|------|--------|------|------|
| frontend-admin | React 18 + Ant Design 5 + Vite | 8081 | 管理后台 |
| backend | Python 3.12 + FastAPI + SQLAlchemy | 8000 | 后端API |
| db | PostgreSQL 16 | 5432 | 数据库 |

### 环境配置

所有敏感配置通过 `.env.docker` 文件注入（不硬编码在代码中）：

| 变量 | 说明 |
|------|------|
| `POSTGRES_DB` | 数据库名 |
| `POSTGRES_USER` | 数据库用户名 |
| `POSTGRES_PASSWORD` | 数据库密码 |
| `DATABASE_URL` | 后端数据库连接串 |
| `SECRET_KEY` | JWT 签名密钥 |

> **安全提示**：`.env.docker` 内含开发默认值仅用于本地演示。生产部署前 **必须** 替换所有密码和 `SECRET_KEY` 为强随机值，或使用 Docker secrets / 密钥管理服务。
>
> 生成随机密钥：`python -c "import secrets; print(secrets.token_urlsafe(64))"`

## 测试账号

系统首次启动时自动创建以下测试账号：

| 角色 | 用户名 | 密码 | 权限说明 |
|------|--------|------|----------|
| 管理员 | admin | admin123 | 全部权限：用户管理、特征文件上传/删除、分析任务管理 |
| 普通用户 | testuser | user123 | 查看特征文件、创建/查看分析任务 |

> **注意**：以上为开发测试凭据，生产环境应在首次登录后立即修改密码。

## 题目内容

### 项目概述

开发一个基于 YARA 特征文件的密码学代码分析平台，核心功能包括：

1. **YARA 特征文件管理**：上传、解析、管理 YARA 格式的密码函数特征文件
2. **多语言代码分析**：支持 C/C++、Python、Java、C#、Rust、Perl 等语言的代码扫描
3. **模糊匹配引擎**：采用前缀匹配、子串匹配、Levenshtein 距离等多种策略进行函数签名匹配
4. **CBOM 报告生成**：生成标准化 JSON 格式的密码资产清单报告
5. **RBAC 权限系统**：管理员与普通用户角色分离，管理员拥有用户管理、数据删除等特权

### 安全特性

| 安全项 | 实现方式 |
|--------|----------|
| CORS | 白名单域名控制，通过 `CORS_ORIGINS` 环境变量配置 |
| JWT Token | 2 小时过期，HS256 签名 |
| 文件上传 | 仅允许 `.yar` / `.yara` 扩展名，50MB 大小限制 |
| 路径穿越防护 | `code_path` 规范化后必须位于 `/app/scans` 目录下 |
| 权限控制 | 管理员专属接口返回 403，普通用户不可越权 |
| 敏感配置 | 密码、密钥通过环境变量注入，不硬编码在代码中 |
| 全局异常处理 | `GlobalExceptionHandler` 统一 API 响应格式 |

### 权限矩阵

| 操作 | 管理员 | 普通用户 |
|------|--------|----------|
| 仪表盘 | Yes | Yes |
| 查看特征文件 | Yes | Yes |
| 上传/删除特征文件 | Yes | No |
| 创建分析任务 | Yes | Yes |
| 查看分析报告 | Yes | Yes |
| 删除分析任务 | Yes | No |
| 用户管理（CRUD） | Yes | No |

### 自动化测试

项目包含完整的单元测试套件，使用 pytest 框架，所有测试与实现 API 严格对齐：

| 测试模块 | 覆盖内容 |
|----------|----------|
| `test_yara_parser.py` | `parse_content`/`parse_file` → `YaraRule` 数据类、meta 字段、多规则、容错 |
| `test_fuzzy_matcher.py` | `match_token`/`match_tokens_in_file`、精确/前缀/库前缀/子串/模糊匹配、阈值 |
| `test_analyzers.py` | `extract_tokens(file_path)` → `(token, line, context)`、`scan_directory`、所有 6 种语言 |
| `test_cbom_generator.py` | `generate()` → 报告结构、`total_crypto_components` 字段、组件聚合、风险评估 |
| `test_cli.py` | 端到端 CLI：JSON 输出、`--summary`、`-o` 文件、`--verbose`、错误码 |

### 核心特性

#### 模糊匹配策略
- **精确匹配**: 函数名完全一致，置信度 100%
- **前缀匹配**: 基于库前缀匹配（如 `mbedtls_ssl_` 前缀），自动关联同库变体
- **库级别前缀**: `mbedtls_ssl_xxx` 与 `mbedtls_mpi_xxx` 通过共享 `mbedtls_` 前缀关联
- **子串匹配**: 特征串在代码标识符中出现
- **模糊匹配**: 基于 SequenceMatcher 的编辑距离相似度

#### 可扩展架构
- 语言分析器采用插件式架构，每种语言一个独立文件
- 新增语言支持只需实现 `BaseAnalyzer` 接口并注册到 `ANALYZER_MAP`
- 已实现: C/C++, Python, Java, C#, Rust, Perl

### 命令行使用 (CLI)

```bash
python cli.py --yara <yara_files...> --code <code_path> --lang <language> [options]
```

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| --yara | -y | Yes | YARA特征文件路径，支持多个文件或目录 |
| --code | -c | Yes | 待分析的代码路径 |
| --lang | -l | Yes | 代码语言 (c/c++/cpp/python/java/c#/csharp/rust/perl) |
| --output | -o | No | 输出报告文件路径（默认stdout） |
| --threshold | -t | No | 模糊匹配阈值 0-1（默认0.6） |
| --summary | | No | 仅输出摘要信息 |
| --verbose | -v | No | 详细日志（通过 logging 模块输出到 stderr） |
| --version | | No | 显示版本号并退出 |

### 项目结构

```
├── backend/                    # FastAPI 后端服务
│   ├── app/
│   │   ├── analyzers/         # 语言分析器（可扩展）
│   │   ├── controllers/       # API 路由控制器
│   │   ├── core/              # 核心引擎（YARA解析/模糊匹配/CBOM生成）
│   │   ├── entities/          # 数据库实体
│   │   ├── exceptions/        # 全局异常处理
│   │   ├── repositories/      # 数据访问层
│   │   ├── schemas/           # DTO 数据传输对象
│   │   └── services/          # 业务逻辑层
│   ├── tests/                 # 单元测试套件
│   ├── cli.py                 # 独立命令行工具
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-admin/            # React 管理后台
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── components/        # 公共组件
│   │   └── pages/             # 页面组件
│   ├── Dockerfile
│   └── nginx.conf
├── test/                      # 测试用样例文件
│   ├── test.yar               # 示例 YARA 特征文件
│   ├── test_rules.yar         # 示例 YARA 规则
│   ├── test_code.py           # 示例 Python 待分析代码
│   └── test_match.py          # 模糊匹配验证用代码
├── db/
│   └── init.sql               # 数据库初始化脚本
├── .env.docker                # Docker 环境变量（密码/密钥）
├── .gitignore
├── docker-compose.yml
└── README.md
```

### API 接口

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /api/auth/login | Public | 用户登录 |
| POST | /api/auth/register | Public | 用户注册 |
| GET | /api/auth/me | Auth | 获取当前用户 |
| GET | /api/signatures | Auth | 特征文件列表 |
| POST | /api/signatures | Admin | 上传特征文件 |
| GET | /api/signatures/:id | Auth | 特征文件详情 |
| DELETE | /api/signatures/:id | Admin | 删除特征文件 |
| GET | /api/analyses | Auth | 分析任务列表 |
| POST | /api/analyses | Auth | 创建分析任务 |
| POST | /api/analyses/upload | Auth | 上传文件并创建分析任务 |
| GET | /api/analyses/:id | Auth | 分析任务详情 |
| GET | /api/analyses/:id/report | Auth | 获取 CBOM 报告 |
| DELETE | /api/analyses/:id | Admin | 删除分析任务 |
| GET | /api/dashboard/stats | Auth | 仪表盘统计 |
| GET | /api/users | Admin | 用户列表 |
| POST | /api/users | Admin | 创建用户 |
| PUT | /api/users/:id | Admin | 更新用户 |
| DELETE | /api/users/:id | Admin | 删除用户 |
| GET | /api/health | Public | 健康检查 |
