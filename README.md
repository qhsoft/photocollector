# 照片和视频自动归集 (Python + PySide6)

这是一个使用 PySide6 实现的桌面程序，用于将照片和视频按拍摄年份归集到目标目录下的 `年/` 子目录中。程序特性：

- 选择源目录与目标目录
- 自动遍历子目录，查找常见照片/视频文件（jpg, png, mp4, mov 等）
- 优先从 EXIF 中读取照片拍摄时间；对 MP4/MOV 视频，解析文件原子（atom）获取创建时间；若都读取不到则回退到文件创建/修改时间
- 按 `目标目录/年/` 结构归集
- 支持复制或移动（可切换）
- 显示进度条和操作日志，并报告处理错误

## 安装依赖
在 Windows 上建议使用 venv：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行
激活虚拟环境后运行：

```powershell
python main.py
```

### 打包（Nuitka 示例）
仓库内包含 `build.bat`，用于用 Nuitka 打包为独立可执行文件。请先安装 Nuitka 与编译工具链，然后运行：

```powershell
# 激活虚拟环境后
.\.venv\Scripts\Activate.ps1
pip install nuitka
build.bat
```

注意：PySide6 应用打包可能需要额外处理资源和插件，Nuitka 提供 `--enable-plugin=pyside6` 插件用于帮助打包。

- FFprobe（属于 FFmpeg）是程序用来读取视频/媒体元数据的工具，请确保系统已安装 `ffprobe` 并在 PATH 中。Windows 下可以从 https://ffmpeg.org/ 下载并将 bin 目录加入 PATH，或者使用包管理器（例如 Chocolatey：`choco install ffmpeg`）。
- HEIC 或某些特殊图片/视频格式可能还需要额外解码器或工具（例如 libheif、MediaInfo）。
- 若需要按月份/天进一步归类，可在 `main.py` 中调整目标目录结构

欢迎根据需要提交 issue 或提出功能改进建议。