# 用户认证服务

该项目实现了一个基于 Python 标准库的用户认证系统，提供用户注册、登录、登出以及获取当前登录用户信息的接口。服务使用 SQLite 持久化数据，并通过 PBKDF2 对用户密码进行加密存储，保证了安全性。

## 快速开始

1. （可选）创建虚拟环境并安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 项目只依赖 `pytest`，用于运行自动化测试。

2. 运行服务：

```bash
python run.py
```

应用默认运行在 `http://127.0.0.1:5000`，使用的是标准库 `wsgiref.simple_server` 提供的 WSGI 服务器。

## API 说明

所有接口均返回 JSON 数据。

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| `POST` | `/auth/register` | 注册新用户，参数包含 `username` 和 `password`（至少 6 位）。|
| `POST` | `/auth/login` | 登录用户，成功后通过 Cookie 维护会话。|
| `POST` | `/auth/logout` | 登出当前用户并清理会话。|
| `GET` | `/auth/me` | 获取当前登录用户信息，未登录时返回 401。|

## 运行测试

使用 `pytest` 运行项目测试：

```bash
pytest
```

测试覆盖了注册、登录、登出及输入校验等关键流程。
