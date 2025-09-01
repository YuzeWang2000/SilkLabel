# SilkLabel 打包说明

## 打包方法

### 方法一：使用打包脚本（推荐）
```bash
# 使用 uv 运行打包脚本
uv run build_exe.py

# 或者如果已经激活了环境
python build_exe.py
```

### 方法二：直接使用 PyInstaller
```bash
# 基础打包命令
pyinstaller --onefile --windowed --name=SilkLabel --add-data="classes.txt;." main.py

# 使用配置文件打包
pyinstaller SilkLabel.spec
```

### 方法三：使用 uv 运行
```bash
uv run pyinstaller SilkLabel.spec
```

## 打包选项说明

- `--onefile`: 打包成单个可执行文件
- `--windowed`: Windows下隐藏控制台窗口
- `--name=SilkLabel`: 设置可执行文件名称
- `--add-data="classes.txt;."`: 包含数据文件
- `--clean`: 清理临时文件
- `--noconfirm`: 不要求确认覆盖

## 输出文件

打包完成后，可执行文件将位于 `dist/` 目录中：
- `dist/SilkLabel.exe` - 主程序文件

## 清理构建文件

```bash
python build_exe.py --clean
```

## 注意事项

1. 确保 `classes.txt` 文件在项目根目录
2. 如果有图标文件 `icon.ico`，会自动包含
3. 打包后的文件较大，这是正常的（包含了 PyQt6 运行时）
4. 首次运行可能需要一些时间来解压和初始化
