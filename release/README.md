# NetTool v1.5.0

## macOS

1. 打开 `macOS/NetTool-v1.5.0.dmg`
2. 拖入 `Applications`
3. 首次启动：**右键 → 打开**（绕过未签名提示）

---

## Windows

无需安装 Python，全部依赖已打包在内。

### 步骤

1. 把 `Windows/` 文件夹拷贝到 Windows 电脑上
2. 双击 `setup.bat` —— 安装依赖（仅需一次）
3. 双击 `build.bat` —— 打包生成 `NetTool.exe`
4. 输出在 `dist/NetTool/NetTool.exe`

### 目录结构

```
Windows/
├── setup.bat          # 步骤1：安装依赖
├── build.bat          # 步骤2：打包 exe
├── python/            # 嵌入式 Python 3.12
├── wheels/            # 所有依赖包（离线安装）
├── core/ modules/     # 源代码
├── data/              # MAC 厂商数据库
├── templates/         # 命令模板
└── image_icon.png     # App 图标
```
