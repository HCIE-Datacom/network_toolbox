# NetTool V100R008C00SPC700

## macOS

发布文件：

```text
macOS/NetTool-V100R008C00SPC700.dmg
```

说明：DMG 是 macOS 安装包。

安装方式：

1. 打开 DMG。
2. 将 `NetTool.app` 拖入 `Applications`。
3. 首次启动如遇未签名提示，请右键点击 App 后选择“打开”。

## Windows

发布文件：

```text
Windows/NetTool-V100R008C00SPC700.exe
```

说明：EXE 是 Windows x64 安装/运行文件。

离线构建目录：

```text
Windows/
```

如需在 Windows 上重新构建：

1. 拷贝 `Windows/` 目录到 Windows x64 机器。
2. 双击 `setup.bat` 安装离线依赖。
3. 双击 `build.bat` 生成 `dist\NetTool-V100R008C00SPC700.exe`。

## 版本信息

- 版本号：`V100R008C00SPC700`

## 更新说明

- 修复 FTP 客户端远程文件下载流程。
- FTP 下载日志改为单行进度条更新，避免进度日志持续刷屏。
- FTP 服务端补充客户端连接、登录、上传和下载日志。
- FTP 服务端启动时自动处理 21 端口占用。
- FTP 远程/本地文件列表支持列宽自动适配、手动拖动和拖动范围限制。
- FTP 文件列表新增右键菜单和重命名操作。

## 作者与协议

- 作者：Tang Wenbo (HCIE-Datacom)
- 版权：Copyright (C) 2026 Tang Wenbo
- 协议：GNU General Public License v3.0 or later
