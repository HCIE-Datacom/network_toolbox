# NetTool

NetTool 是一个跨平台网络工具箱，基于 Python + PySide6 开发，当前版本为 `V100R008C00SPC600`。

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

## 版本命名

项目使用 `VxxxRxxxCxxSPCxxx` 格式：

- `V`：主版本，代表架构或产品主线。
- `R`：发布版本，代表功能发布迭代。
- `C`：定制版本，默认 `C00`。
- `SPC`：补丁版本，代表修复和维护版本。

当前版本：`V100R008C00SPC600`。

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

## 打包

最新发布文件请到 [GitHub Releases](https://github.com/HCIE-Datacom/network_toolbox/releases) 下载。

macOS 打包产物：

```text
release/macOS/NetTool-V100R008C00SPC600.dmg
```

说明：DMG 是 macOS 安装包，打开后将 `NetTool.app` 拖入 `Applications`。

Windows 打包产物：

```text
release/Windows/NetTool-V100R008C00SPC600.exe
```

说明：EXE 是 Windows 独立可执行文件，可直接运行。

Windows 离线构建目录位于 `release/Windows/`，在 Windows x64 机器上执行：

```bat
setup.bat
build.bat
```

`build.bat` 会生成：

```text
dist\NetTool-V100R008C00SPC600.exe
```

## 目录结构

```text
network_toolbox.py       # 程序入口
core/                    # 主窗口、基础模块、图标、日志
modules/                 # 各功能模块
data/                    # 本地数据文件
templates/               # 命令生成器模板
release/                 # 发布产物和离线构建目录
NetTool.spec             # macOS PyInstaller 打包配置
```

## 作者与协议

- 作者：Tang Wenbo (HCIE-Datacom)
- 版权：Copyright (C) 2026 Tang Wenbo
- 协议：GNU General Public License v3.0 or later
