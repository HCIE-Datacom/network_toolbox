# NetTool — macOS Network Toolbox

多功能 macOS 网络工具箱，插件化架构，支持 NTP、FTP/SFTP、Ping/Traceroute/TCPing、子网计算、命令生成、iPerf 带宽测试。

## 功能模块

| 模块 | 功能 |
|------|------|
| NTP 工具 | NTP 客户端查询 + 本机 NTP 服务 |
| FTP 工具 | FTP/SFTP 客户端 + FTP 服务端 |
| PING 测试 | ICMP Ping / Traceroute / TCPing |
| 子网计算 | 子网划分 + 路由聚合 |
| 命令生成器 | 模板化批量命令生成，支持内置/自定义模板 |
| iPerf 带宽测试 | 纯 Python TCP/UDP 带宽测试，支持客户端/服务器模式 |

## 运行

```bash
pip3 install -r requirements.txt
python3 network_toolbox.py
```

或双击 `NetTool.app`。

## 协议

GNU General Public License v3.0 — 使用、修改、分发均须保持开源。

## 作者

Tang Wenbo (HCIE-Datacom) — © 2026
