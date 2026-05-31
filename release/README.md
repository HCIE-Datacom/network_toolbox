# NetTool V100R009C00SPC500

## 发布方式

安装包由 GitHub Actions 自动构建并上传到 GitHub Releases。源码仓库不再跟踪 DMG/EXE 安装包。

触发方式：

```bash
git tag <版本号>
git push origin main <版本号>
```

也可以在 GitHub Actions 页面手动运行 `Build and Release NetTool` 工作流。

## macOS

发布文件：

```text
NetTool-V100R009C00SPC500.dmg
```

安装方式：

1. 打开 DMG。
2. 将 `NetTool.app` 拖入 `Applications`。
3. 首次启动如遇未签名提示，请右键点击 App 后选择“打开”。

## Windows

发布文件：

```text
NetTool-V100R009C00SPC500.exe
```

说明：EXE 是 Windows x64 安装/运行文件。

离线构建目录：

```text
Windows/
```

如需在 Windows 上重新构建：

1. 拷贝 `Windows/` 目录到 Windows x64 机器。
2. 双击 `setup.bat` 安装离线依赖。
3. 双击 `build.bat` 生成 `dist\NetTool-V100R009C00SPC500.exe`。

## 版本信息

- 版本号：`V100R009C00SPC500`

## 更新说明

- 新增配置对比模块，支持普通文本配置文件左右逐行对比、差异高亮、空行补齐和文件拖入。
- PING 测试支持 Ping、Tracert、TCPing 最多 5 个目标并行检测。
- PING/Tracert/TCPing 输出增加时间戳、IPv4 输入校验、独立统计和结果保存。
- PING 测试新增实时保存开关，运行时可按目标实时写入 txt 文件。
- 系统网络模块优化管理员权限处理，Windows 下按需拉起提权 helper。

## 作者与协议

- 作者：Tang Wenbo (HCIE-Datacom)
- 版权：Copyright (C) 2026 Tang Wenbo
- 协议：GNU General Public License v3.0 or later
