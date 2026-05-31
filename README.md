# NetTool

NetTool 是一个跨平台网络工具箱，基于 Python + PySide6 开发，当前版本为 `V100R008C00SPC700`。

## 功能

| 模块 | 说明 |
| --- | --- |
| NTP 工具 | NTP 客户端查询、本机 NTP 服务启动与日志记录 |
| FTP 工具 | FTP/SFTP 客户端、FTP 服务端、端口占用处理 |
| PING 测试 | ICMP Ping、Traceroute、TCPing |
| 子网计算 | 子网划分、CIDR 计算、路由聚合 |
| 命令生成器 | 基于内置或自定义模板批量生成网络配置命令 |
| iPerf 带宽测试 | 纯 Python TCP/UDP 带宽测试，支持客户端和服务器模式 |
| MAC 地址查询 | 基于本地 OUI 数据库查询厂商信息 |
| 系统网络 | 路由、hosts、网卡 IP 管理等系统网络配置工具 |
| 运行日志 | 汇总记录各模块运行、操作和错误日志 |

![NetTool 软件界面](docs/nettool-screenshot.png)

## macOS 首次打开

当前发布包未进行 Apple notarization 公证，macOS 首次打开时可能提示“Apple 无法验证 NetTool.app”。如果确认安装包来自本项目的 GitHub Releases，可以按下面方式打开：

1. 将 `NetTool.app` 拖入“应用程序”目录。
2. 在“应用程序”里右键或按住 `Control` 点击 `NetTool.app`，选择“打开”。
3. 在确认弹窗中再次点击“打开”。这个操作只需要首次启动时执行一次。

![macOS 右键打开 NetTool](docs/macos-open-right-click.png)

![macOS 确认打开 NetTool](docs/macos-open-confirm.png)

## 版本命名

项目使用 `VxxxRxxxCxxSPCxxx` 格式：

- `V`：主版本，代表架构或产品主线。
- `R`：发布版本，代表功能发布迭代。
- `C`：定制版本，默认 `C00`。
- `SPC`：补丁版本，代表修复和维护版本。

当前版本：`V100R008C00SPC700`。

## 本次更新

- FTP 客户端支持远程文件下载，下载开始后在日志中以单行进度条持续更新，完成后记录最终结果。
- FTP 服务端补充客户端连接、登录、上传和下载日志，便于追踪文件传输行为。
- FTP 服务端启动时会检测并释放被占用的 21 端口，处理逻辑与 NTP 服务保持一致。
- FTP 文件列表支持列宽自动适配窗口、手动拖动列宽，并限制列宽不会被拖到异常尺寸。
- FTP 文件列表增加右键菜单，支持上传、下载、删除、重命名、刷新和返回上级目录等操作。

## 开发运行

建议使用 Python 3.11+。

```bash
python3 -m pip install -r requirements.txt
python3 network_toolbox.py
```

macOS 下也可以直接运行开发版：

```bash
./run_macos_dev.command
```

## 目录结构

```text
network_toolbox.py       # 程序入口
core/                    # 主窗口、基础模块、图标、日志
modules/                 # 各功能模块
data/                    # 本地数据文件
templates/               # 命令生成器模板
docs/                    # 项目截图和文档资源
release/                 # 发布产物和离线构建目录
NetTool.spec             # macOS PyInstaller 打包配置
```

## 作者与协议

- 作者：Tang Wenbo (HCIE-Datacom)
- 版权：Copyright (C) 2026 Tang Wenbo
- 协议：GNU General Public License v3.0 or later
