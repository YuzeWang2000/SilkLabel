#!/usr/bin/env python3
"""
PyInstaller 打包脚本
用于将 SilkLabel 应用程序打包成可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    """主函数：执行打包过程"""
    print("开始打包 SilkLabel 应用程序...")
    
    # 确定项目根目录
    project_root = Path(__file__).parent
    main_script = project_root / "main.py"
    
    if not main_script.exists():
        print("错误：找不到 main.py 文件")
        return False
    
    # PyInstaller 命令参数
    cmd = [
        "pyinstaller",
        "--onefile",                    # 打包成单个文件
        "--windowed",                   # Windows下不显示控制台窗口
        "--name=SilkLabel",             # 可执行文件名称
        "--icon=icon.ico",              # 图标文件（如果存在）
        "--add-data=classes.txt;.",     # 包含 classes.txt 文件
        "--clean",                      # 清理临时文件
        "--noconfirm",                  # 不要求确认覆盖
        str(main_script)
    ]
    
    # 检查图标文件是否存在，如果不存在则移除图标参数
    icon_path = project_root / "icon.ico"
    if not icon_path.exists():
        cmd.remove("--icon=icon.ico")
        print("提示：未找到 icon.ico 文件，将不使用自定义图标")
    
    # 执行打包命令
    print(f"执行命令: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=project_root, check=True)
        print("打包成功！")
        
        # 显示输出文件位置
        dist_dir = project_root / "dist"
        exe_file = dist_dir / "SilkLabel.exe"
        if exe_file.exists():
            print(f"可执行文件位置: {exe_file}")
            print(f"文件大小: {exe_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"打包失败，错误码: {e.returncode}")
        return False
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        return False

def clean_build():
    """清理构建文件"""
    project_root = Path(__file__).parent
    
    # 要清理的目录
    dirs_to_clean = ["build", "dist", "__pycache__"]
    
    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"清理目录: {dir_path}")
            shutil.rmtree(dir_path)
    
    # 清理 .spec 文件
    spec_files = list(project_root.glob("*.spec"))
    for spec_file in spec_files:
        print(f"删除文件: {spec_file}")
        spec_file.unlink()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SilkLabel 打包工具")
    parser.add_argument("--clean", action="store_true", help="清理构建文件")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_build()
        print("清理完成")
    else:
        success = main()
        if not success:
            sys.exit(1)
