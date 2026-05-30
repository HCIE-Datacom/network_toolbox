# NetTool V100R008C00SPC600

## macOS

发布文件：

```text
macOS/NetTool-V100R008C00SPC600.dmg
```

说明：DMG 是 macOS 安装包。

安装方式：

1. 打开 DMG。
2. 将 `NetTool.app` 拖入 `Applications`。
3. 首次启动如遇未签名提示，请右键点击 App 后选择“打开”。

## Windows

构建输出：

```text
Windows/dist/NetTool-V100R008C00SPC600.exe
```

说明：EXE 需要在 Windows x64 机器上执行 `build.bat` 后生成。

离线构建目录：

```text
Windows/
```

如需在 Windows 上重新构建：

1. 拷贝 `Windows/` 目录到 Windows x64 机器。
2. 双击 `setup.bat` 安装离线依赖。
3. 双击 `build.bat` 生成 `dist\NetTool-V100R008C00SPC600.exe`。

## 版本信息

- 版本号：`V100R008C00SPC600`

## 作者与协议

- 作者：Tang Wenbo (HCIE-Datacom)
- 版权：Copyright (C) 2026 Tang Wenbo
- 协议：GNU General Public License v3.0 or later
