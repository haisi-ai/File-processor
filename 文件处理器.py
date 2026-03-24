import json
import sys
import os
from contextlib import redirect_stdout
from io import StringIO
import logging
from tkinter import dialog

import dirsync
from dirsync import sync as dirsync_sync
import pandas as pd
import requests
import socket
import mimetypes
from datetime import datetime
import subprocess
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QStatusBar, QMenuBar, QAction, QFileDialog, QDialog, QFormLayout,
    QDialogButtonBox, QComboBox, QMessageBox, QCheckBox, QInputDialog, QRadioButton
)


def is_connected():
    """
    检查是否可以连接到互联网
    """
    try:
        # 连接到一个常见的互联网主机 (Google 的公共 DNS)
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False


class FileProcessorUI(QMainWindow):
    def __init__(self):
        """
        初始化文件处理器的用户界面。
        """

        self.current_version = "v1.0"  # 当前程序版本
        self.version_url = "https://raw.githubusercontent.com/haisi-ai/File-processor/refs/heads/main/version.txt"  # 版本文件的远程地址

        super().__init__()

        # 设置窗口标题和大小
        self.setWindowTitle("文件处理器")
        self.setWindowIcon(QIcon("logo.ico"))
        self.setGeometry(100, 100, 600, 400)

        # 初始化界面
        self.current_path = ""  # 用于存储当前选择的文件或文件夹路径
        self.init_ui()

    def init_ui(self):
        """
        初始化界面布局和组件。
        """
        # 主窗口组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()

        # 第一排：输入显示框和选择按钮
        first_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请输入文件或文件夹路径或点击选择...")
        self.select_path_button = QPushButton("选择")
        self.select_path_button.clicked.connect(self.select_path)
        first_row.addWidget(self.path_input)
        first_row.addWidget(self.select_path_button)

        # 第二排按钮
        second_row = QHBoxLayout()
        self.get_name_button = QPushButton("获取名称")
        self.rename_button = QPushButton("修改名称")
        # self.rename_button.setDisabled(True)
        self.rename_button.clicked.connect(self.change_rename)
        self.change_extension_button = QPushButton("修改后缀")
        self.get_name_button.clicked.connect(self.get_names)
        self.change_extension_button.clicked.connect(self.show_change_extension_dialog)
        second_row.addWidget(self.get_name_button)
        second_row.addWidget(self.rename_button)
        second_row.addWidget(self.change_extension_button)

        # 第三排按钮
        third_row = QHBoxLayout()
        self.create_file_button = QPushButton("创建文件")
        self.delete_file_button = QPushButton("删除文件")
        self.backup_file_button = QPushButton("备份文件")
        third_row.addWidget(self.create_file_button)
        third_row.addWidget(self.delete_file_button)
        third_row.addWidget(self.backup_file_button)
        # 绑定到创建文件按钮
        self.create_file_button.clicked.connect(self.create_files_from_txt)
        self.backup_file_button.clicked.connect(self.show_backup_dialog)
        # 第四排按钮
        fourth_row = QHBoxLayout()
        self.undefined_button_1 = QPushButton("待定义..")
        self.undefined_button_2 = QPushButton("待定义..")
        self.undefined_button_3 = QPushButton("待定义..")
        fourth_row.addWidget(self.undefined_button_1)
        fourth_row.addWidget(self.undefined_button_2)
        fourth_row.addWidget(self.undefined_button_3)

        # 日志输出框
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        # 添加到主布局
        main_layout.addLayout(first_row)
        main_layout.addLayout(second_row)
        main_layout.addLayout(third_row)
        main_layout.addLayout(fourth_row)
        main_layout.addWidget(QLabel("日志输出："))
        main_layout.addWidget(self.log_output)

        # 设置主窗口布局
        central_widget.setLayout(main_layout)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("欢迎使用文件处理器！")

        # 菜单栏
        menu_bar = QMenuBar()
        self.setMenuBar(menu_bar)

        # 添加菜单
        caidan_menu = menu_bar.addMenu("菜单")
        help_menu = menu_bar.addMenu("帮助")

        # 添加菜单项
        save_log_action = QAction("保存日志", self)
        save_log_action.setShortcut("Ctrl+S")
        caidan_menu.addAction(save_log_action)
        save_log_action.setStatusTip("保存当前日志到文件")

        update_action = QAction("检查更新", self)
        about_action = QAction("关于文件处理器", self)
        help_menu.addAction(update_action)
        help_menu.addAction(about_action)

        # 连接菜单项的信号
        save_log_action.triggered.connect(self.save_log) # 保存日志
        update_action.triggered.connect(self.show_update_dialog) # 检查更新
        about_action.triggered.connect(self.show_about_message) # 关于文件处理器

    def select_path(self):
        """
        打开文件或文件夹选择对话框，并将选择的路径显示在输入框中。
        """
        options = QFileDialog.Options()
        file_path = QFileDialog.getExistingDirectory(self, "选择文件夹", options=options)
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*.*)")

        if file_path:
            self.current_path = file_path  # 确保路径被正确保存
            self.path_input.setText(file_path)
            self.log_output.append(f"已选择路径: {file_path}")
        else:
            self.log_output.append("未选择任何路径")

    def get_names(self):
        """
        获取当前路径下的所有文件夹和文件的名称，并区分类型显示在日志框。
        """
        if not self.current_path or not os.path.exists(self.current_path):
            self.log_output.append("无效的路径，请选择有效的文件夹~!")
            return

        self.log_output.append(f"\n正在列出路径: {self.current_path}\n")

        # 调用递归函数开始处理文件夹和文件
        self._iterate_directory(self.current_path)

    def _iterate_directory(self, directory, indent=0):
        """
        遍历目录，递归列出所有文件和文件夹，并在日志框中输出缩进格式。
        :param directory: 当前遍历的目录路径
        :param indent: 当前层级的缩进
        """
        try:
            # 获取目录下的所有文件和文件夹
            items = os.listdir(directory)

            for item in items:
                item_path = os.path.join(directory, item)

                if os.path.isdir(item_path):  # 如果是文件夹
                    self.append_to_log(f"{'    ' * indent}[目录] {item}", "Blue") #蓝色文件夹或目录
                    # 递归调用处理子文件夹
                    self._iterate_directory(item_path, indent + 1)
                elif os.path.isfile(item_path):  # 如果是文件
                    # 获取文件的 MIME 类型
                    mime_type, _ = mimetypes.guess_type(item_path)
                    ext = os.path.splitext(item)[1].lower()

                    if mime_type and mime_type.startswith("image"):
                        color = "magenta"  # 品红色图像文件
                    elif mime_type and mime_type.startswith("text")or ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".odg", ".odf", ".rtf", ".tex", ".md", ".txt", ".log", ".ini", ".conf", ".cfg", ".yaml", ".yml",".json", ".xml", ".csv", ".tsv", ".xls",".eml"]:
                        color = "Slate Grey"  # 石板灰色文本文件
                    elif mime_type and mime_type.startswith("application/zip") or ext in [
                        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg", ".img", ".iso", ".arj", ".vdi", ".vhd", ".zipx", ".ace", ".cab", ".lz", ".lzma", ".tar.bz2", ".tar.gz", ".tar.lzma", ".tar.xz", ".tar.zst", ".tar.z", ".tar.Z",]:
                        color = "red"  # 红色压缩文件
                    elif ext in [".exe", ".bat", ".cmd", ".msi", ".sh", ".py", ".js", ".html", ".css", ".php", ".java", ".cpp", ".c", ".h", ".go", ".rb", ".pl", ".jar", ".ps1", ".vbs", ".vb", ".dmg", ".ts", ".tsx", ".app", ".pyw", ".pyi", ".pyc", ".pyo", ".pyd", ".pyz", ".ap", ".apk"]:
                        color = "green"  # 绿色可执行文件
                    elif ext in [".mp3",".wav",".flac",".aac",".alac",".m4a",".amr",".ogg",".ape",".wma",".opus",".midi"]:
                        color = "Pink"  # 粉色音频文件
                    elif ext in [".mp4", ".avi", ".mov", ".wmv", ".mkv", ".flv", ".webm", ".ogg", ".ogv", ".ogm", ".m4v", ".mpg", ".mpeg", ".m2v", ".mts", ".m2ts", ".ts", ".3gp", ".3g2", ".m3u8", ".m3u", ".m3u8", ]:
                        color = "Orange"  # 橙色视频文件
                    else:
                        color = "Charcoal Black"  # 碳黑其他文件

                    self.append_to_log(f"{'    ' * indent}{item}", color)
        except Exception as e:
            self.append_to_log(f"无法访问目录 {directory}: {e}", "black")

    def change_rename(self):
        """
        根据用户提供的 Excel 文件参照对比修改文件名。
        Excel 文件格式要求：
        - 第一列为当前文件名
        - 第二列为目标文件名
        """
        if not self.current_path:
            self.log_output.append("请先选择路径！")
            return

        # 让用户选择 Excel 文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if not file_path:
            self.log_output.append("未选择任何 Excel 文件！")
            return

        try:
            # 读取 Excel 文件
            df = pd.read_excel(file_path, engine='openpyxl')

            # 检查文件格式
            if df.shape[1] < 2:
                self.log_output.append("Excel 文件格式错误：至少需要两列！")
                return

            # 获取原始文件名和目标文件名
            original_names = df.iloc[:, 0].astype(str).tolist()  # 第一列
            target_names = df.iloc[:, 1].astype(str).tolist()  # 第二列

            # 遍历并修改文件名
            success_count = 0
            failure_count = 0
            for original, target in zip(original_names, target_names):
                old_path = os.path.join(self.current_path, original)
                new_path = os.path.join(self.current_path, target)

                try:
                    if os.path.exists(old_path):
                        os.rename(old_path, new_path)
                        self.log_output.append(f"重命名成功: {old_path} -> {new_path}")
                        success_count += 1
                    else:
                        self.log_output.append(f"文件不存在: {old_path}")
                        failure_count += 1
                except Exception as e:
                    self.log_output.append(f"重命名失败: {old_path} -> {new_path} 错误: {e}")
                    failure_count += 1

            # 输出总结
            self.log_output.append(f"重命名完成！成功: {success_count} 个, 失败: {failure_count} 个。")
        except Exception as e:
            self.log_output.append(f"读取 Excel 文件失败: {e}")

    def append_to_log(self, text, color="black"):
        """
        将指定颜色的文本追加到日志框中。
        :param text: str: 要追加的文本
        :param color: str: 文本颜色
        """
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(text + "\n")
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def show_change_extension_dialog(self):
        """
        显示修改后缀的对话框，支持用户输入或选择后缀。
        """
        if not self.current_path:
            self.log_output.append("请先选择路径！")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("修改文件后缀")

        # 表单布局
        form_layout = QFormLayout()

        # 创建可编辑的下拉框（源后缀和目标后缀）
        src_extension_input = QComboBox()
        src_extension_input.setEditable(True)  # 设置为可编辑
        src_extension_input.addItems(["txt", "log", "py", "exe", "rar"])  # 添加预设选项

        tgt_extension_input = QComboBox()
        tgt_extension_input.setEditable(True)  # 设置为可编辑
        tgt_extension_input.addItems(["txt", "log", "py", "exe", "rar"])  # 添加预设选项

        form_layout.addRow("源后缀：", src_extension_input)
        form_layout.addRow("修改为：", tgt_extension_input)

        # 按钮组
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self.change_file_extension(
            src_extension_input.currentText(),
            tgt_extension_input.currentText(),
            dialog
        ))
        button_box.rejected.connect(dialog.reject)

        form_layout.addWidget(button_box)
        dialog.setLayout(form_layout)
        dialog.exec_()

    def create_files_from_txt(self):
        """
        根据TXT文件的缩进关系，在选定目录下创建文件夹和文件。
        支持基于缩进关系，正确处理文件与文件夹的层级。
        """
        if not self.current_path:
            self.log_output.append("请先选择路径！")
            return

        # 选择TXT文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 TXT 文件", "", "Text Files (*.txt)"
        )
        if not file_path:
            self.log_output.append("未选择任何 TXT 文件！")
            return

        try:
            # 读取TXT文件
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            # 初始化路径栈和缩进层级
            path_stack = [self.current_path]  # 路径栈，用于存储当前层级路径
            previous_indent = 0  # 前一行缩进，用于计算层级关系

            for line in lines:
                # 跳过空行
                if not line.strip():
                    continue

                # 获取当前行的内容和缩进层级
                stripped_line = line.lstrip()
                current_indent = len(line) - len(stripped_line)

                # 调整路径栈以匹配当前缩进层级
                if current_indent > previous_indent:
                    # 进入更深层级，路径栈添加上一层路径
                    path_stack.append(current_path)
                elif current_indent < previous_indent:
                    # 返回上层，弹出路径栈
                    levels_up = (previous_indent - current_indent) // 4
                    for _ in range(levels_up):
                        path_stack.pop()

                # 更新当前路径
                current_path = os.path.join(path_stack[-1], stripped_line.strip())

                # 判断是文件还是文件夹
                if "." in stripped_line:  # 文件
                    if not os.path.exists(current_path):
                        with open(current_path, 'w') as f:
                            f.write("")  # 创建空文件
                        self.log_output.append(f"创建文件: {current_path}")
                    else:
                        self.log_output.append(f"文件已存在，跳过: {current_path}")
                else:  # 文件夹
                    if not os.path.exists(current_path):
                        os.makedirs(current_path)
                        self.log_output.append(f"创建文件夹: {current_path}")
                    else:
                        self.log_output.append(f"文件夹已存在，跳过: {current_path}")

                # 更新缩进层级
                previous_indent = current_indent

            self.log_output.append("所有文件和文件夹创建完成！")

        except Exception as e:
            self.log_output.append(f"处理TXT文件时出错: {e}")

    def change_file_extension(self, source_extension, target_extension, dialog):
        """
        修改文件夹内的所有文件后缀。
        """
        if not source_extension or not target_extension:
            self.log_output.append("源后缀或目标后缀不能为空！")
            return

        success_count = 0
        for root, _, files in os.walk(self.current_path):
            for file in files:
                if file.endswith(f".{source_extension}"):
                    old_file = os.path.join(root, file)
                    new_file = os.path.join(
                        root, file.replace(f".{source_extension}", f".{target_extension}")
                    )
                    os.rename(old_file, new_file)
                    self.log_output.append(f"修改后缀: {old_file} -> {new_file}")
                    success_count += 1

        if success_count == 0:
            self.log_output.append(f"未找到任何匹配 .{source_extension} 的文件。")
        else:
            self.log_output.append(f"成功修改 {success_count} 个文件的后缀！")

        dialog.accept()  # 关闭对话框

    def show_about_message(self, event=None):  # 去掉 event 或设置为可选参数
        """
        显示关于信息。
        """
        QMessageBox.about(
            self,
            "关于",
            f"文件处理器：{self.current_version}\n"
            "作者：海斯\n"
            "邮箱：haisi@mail.com"
        )

    def save_log(self):
        """
        保存日志到文件。
        """
        log_text = self.log_output.toPlainText()
        file_name, _ = QFileDialog.getSaveFileName(self, "保存日志", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, "w") as file:
                file.write(log_text)

    def show_update_dialog(self):
        """
        检查更新功能
        """
        try:
            import requests
            if not is_connected():
                QMessageBox.warning(self, "网络错误", "无法连接到网络，请检查网络连接。")
                return

            # 获取远程版本
            response = requests.get(self.version_url, timeout=10)
            response.raise_for_status()

            remote_version = response.text.strip()
            if remote_version > self.current_version:
                changelog_url = "https://raw.githubusercontent.com/Haisi-1536/Online-Calculator/refs/heads/main/changelog.txt"
                changelog_response = requests.get(changelog_url, timeout=10)
                changelog_response.raise_for_status()

                changelog = changelog_response.text.strip()

                # 创建富文本消息框
                message_box = QMessageBox(self)
                message_box.setWindowTitle("检查更新")
                message_box.setTextFormat(Qt.RichText)
                message_box.setText(
                    f"发现新版本: <b>{remote_version}</b>！<br><br>"
                    f"<b>更新内容:</b><br>{changelog}<br><br>"
                    f"请前往 <a href='https://github.com/Haisi-1536/Online-Calculator'>官网下载更新</a>。"
                )
                message_box.setStandardButtons(QMessageBox.Ok)
                message_box.exec_()
            else:
                QMessageBox.information(self, "检查更新", "当前已是最新版本！")
        except ImportError:
            QMessageBox.critical(self, "错误", "未找到 requests 模块，请安装后重试。")
        except requests.RequestException as e:
            QMessageBox.warning(self, "检查更新", f"无法连接到更新服务器: {e}")
        except Exception as e:
            QMessageBox.warning(self, "检查更新", f"更新检查失败: {str(e)}")

    # 下载更新文件
    def download_update(self, download_url, save_path):
        """
        下载更新文件
        """
        try:
            response = requests.get(download_url, stream=True)
            with open(save_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            QMessageBox.information(self, "更新成功", "更新文件已下载！")
        except Exception as e:
            QMessageBox.warning(self, "下载失败", f"更新文件下载失败: {str(e)}")

    def append_to_log(self, text, color="black"):
        """
        将指定颜色的文本追加到日志框中。
        :param text: str: 要追加的文本
        :param color: str: 文本颜色
        """
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(text + "\n")
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def show_backup_dialog(self):
        """
        显示文件备份窗口（非模态）。
        """
        if hasattr(self, "backup_dialog") and self.backup_dialog.isVisible(): # 检查对话框是否已显示
            self.backup_dialog.raise_()
            return

        self.backup_dialog = QDialog(self)
        self.backup_dialog.setWindowTitle("备份文件")
        self.backup_dialog.setModal(False)  # 设置为非模态对话框
        layout = QVBoxLayout()

        # 左右路径选择框
        left_layout = QHBoxLayout()
        left_label = QLabel("源路径：")
        self.left_path_input = QLineEdit()
        left_button = QPushButton("选择")
        left_button.clicked.connect(lambda: self.select_directory(self.left_path_input))
        left_layout.addWidget(left_label)
        left_layout.addWidget(self.left_path_input)
        left_layout.addWidget(left_button)

        right_layout = QHBoxLayout()
        right_label = QLabel("目标路径：")
        self.right_path_input = QLineEdit()
        right_button = QPushButton("选择")
        right_button.clicked.connect(lambda: self.select_directory(self.right_path_input))
        right_layout.addWidget(right_label)
        right_layout.addWidget(self.right_path_input)
        right_layout.addWidget(right_button)

        # 同步模式选项
        self.incremental_backup = QRadioButton("增量同步")
        self.sync_left_to_right = QRadioButton("单向同步")
        self.sync_mirror = QRadioButton("镜像同步")
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(self.incremental_backup)
        mode_layout.addWidget(self.sync_left_to_right)
        mode_layout.addWidget(self.sync_mirror)

        # 备份组显示框
        self.sync_group_list_widget = QVBoxLayout()
        self.load_sync_groups()  # 自动加载备份组

        group_list_layout = QVBoxLayout()
        group_list_label = QLabel("备份组：")
        group_list_layout.addWidget(group_list_label)
        group_list_layout.addLayout(self.sync_group_list_widget)

        # 按钮组
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        analyze_button = QPushButton("分析")
        start_button = QPushButton("开始")
        cancel_button = QPushButton("取消")

        save_button.clicked.connect(self.save_sync_group)
        # analyze_button.clicked.connect(self.analyze_difference)
        start_button.clicked.connect(self.start_backup)
        cancel_button.clicked.connect(self.backup_dialog.close)

        button_layout.addWidget(save_button)
        button_layout.addWidget(analyze_button)
        button_layout.addWidget(start_button)
        button_layout.addWidget(cancel_button)

        # 添加到布局
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        layout.addLayout(mode_layout)
        layout.addLayout(group_list_layout)
        layout.addLayout(button_layout)

        self.backup_dialog.setLayout(layout)
        self.backup_dialog.show()

    def load_sync_groups(self):
        """
        加载备份组并显示在界面上。
        """
        sync_groups = self.load_sync_groups_from_file()
        for name, data in sync_groups.items():
            self.add_sync_group_to_list(name, data)

    def add_sync_group_to_list(self, name, data):
        """
        将备份组添加到显示框。
        """
        group_widget = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.setText(name)
        checkbox.toggled.connect(lambda checked, n=name, d=data: self.populate_sync_group(n, d) if checked else None)

        delete_button = QPushButton("删除")
        delete_button.clicked.connect(lambda: self.delete_sync_group(name, group_widget))

        group_widget.addWidget(checkbox)
        group_widget.addWidget(QLabel(f"源路径: {data['source']}"))
        group_widget.addWidget(QLabel(f"目标路径: {data['target']}"))
        group_widget.addWidget(QLabel(f"模式: {data['mode']}"))
        group_widget.addWidget(delete_button)

        self.sync_group_list_widget.addLayout(group_widget)

    def populate_sync_group(self, name, data):
        """
        填充备份组信息到输入框。
        """
        self.left_path_input.setText(data["source"])
        self.right_path_input.setText(data["target"])
        mode = data["mode"]
        if mode == "增量同步":
            self.incremental_backup.setChecked(True)
        elif mode == "单向同步":
            self.sync_left_to_right.setChecked(True)
        elif mode == "镜像同步":
            self.sync_mirror.setChecked(True)

    def save_sync_group(self):
        """
        保存备份组到本地 JSON 文件。
        """
        source = self.left_path_input.text()
        target = self.right_path_input.text()
        mode = "增量同步" if self.incremental_backup.isChecked() else \
            "单向同步" if self.sync_left_to_right.isChecked() else \
                "镜像同步" if self.sync_mirror.isChecked() else None

        if not source or not target or not mode:
            self.append_to_log("请填写完整的源路径、目标路径和同步模式！", "red")
            return

        group_name, ok = QInputDialog.getText(self, "保存备份组", "请输入备份组名称：")
        if not ok or not group_name.strip():
            self.append_to_log("备份组名称不能为空！", "red")
            return

        group_data = {"source": source, "target": target, "mode": mode}
        sync_groups = self.load_sync_groups_from_file()
        sync_groups[group_name] = group_data
        self.save_sync_groups_to_file(sync_groups)
        self.add_sync_group_to_list(group_name, group_data)
        self.append_to_log(f"备份组 '{group_name}' 已保存！", "green")

    def delete_sync_group(self, name, widget):
        """
        删除备份组。
        """
        sync_groups = self.load_sync_groups_from_file()
        if name in sync_groups:
            del sync_groups[name]
            self.save_sync_groups_to_file(sync_groups)
            for i in reversed(range(widget.count())):
                widget.itemAt(i).widget().deleteLater()
            self.append_to_log(f"备份组 '{name}' 已删除！", "red")

    def load_sync_groups_from_file(self):
        try:
            with open("sync_groups.json", "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_sync_groups_to_file(self, sync_groups):
        with open("sync_groups.json", "w", encoding="utf-8") as file:
            json.dump(sync_groups, file, indent=4, ensure_ascii=False)

    def select_directory(self, input_field):
        """
        打开目录选择对话框并设置到输入框中。
        """
        directory = QFileDialog.getExistingDirectory(self, "选择目录")
        if directory:
            input_field.setText(directory)


    def start_backup(self):
        """
        启动备份任务，根据用户输入的路径和同步模式执行。
        """
        source = self.left_path_input.text()
        target = self.right_path_input.text()

        if not source or not target:
            self.append_to_log("请指定源路径和目标路径！", "red")
            return

        mode = None
        if self.incremental_backup.isChecked():
            mode = "增量同步"
        elif self.sync_left_to_right.isChecked():
            mode = "单向同步"
        elif self.sync_mirror.isChecked():
            mode = "镜像同步"

        if not mode:
            self.append_to_log("请选择一个同步选项！", "red")
            return

        self.append_to_log(f"启动 {mode}...", "green")
        self.execute_backup(source, target, mode)

    def execute_backup(self, source, target, mode):
        """
        根据同步模式执行相应的备份任务。
        """
        try:
            if mode == "增量同步":
                self.run_dirsync(source, target, action='sync', create=True, purge=False)
            elif mode == "单向同步":
                self.run_dirsync(source, target, action='sync', create=True, purge=True)
            elif mode == "镜像同步":
                # 镜像同步需要双向同步
                self.run_dirsync(source, target, action='sync', create=True, purge=True)
                self.run_dirsync(target, source, action='sync', create=True, purge=True)
        except Exception as e:
            self.append_to_log(f"执行 {mode} 任务时发生错误: {e}", "red")


    def run_dirsync(self, source, target, action, create=True, purge=False):
        """
        执行 dirsync 同步任务，并实时将日志刷新到主窗口日志框。
        :param source: 源路径
        :param target: 目标路径
        :param action: 同步操作类型 ('sync' or 'diff')
        :param create: 是否创建目标目录
        :param purge: 是否清理多余文件
        """
        log_file = os.path.join(os.getcwd(), "备份文件日志.txt")  # 日志保存路径
        logging.basicConfig(
            filename=log_file,
            filemode='a',
            format='%(asctime)s - %(message)s',
            level=logging.INFO
        )

        try:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.append_to_log(f"同步开始时间: {start_time}", "blue")

            # 捕获 dirsync 的日志
            log_output = StringIO()
            handler = logging.StreamHandler(log_output)
            logging.getLogger('dirsync').addHandler(handler)

            # 执行同步
            dirsync.sync(source, target, action=action, create=create, purge=purge, verbose=True)

            # 实时输出日志
            log_output.seek(0)
            for line in log_output:
                self.append_to_log(line.strip(), "blue")

            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.append_to_log(f"同步完成时间: {end_time}", "green")
            self.append_to_log("同步任务成功完成。", "green")

        except Exception as e:
            self.append_to_log(f"同步过程中发生异常: {str(e)}", "red")
        finally:
            # 保存日志到文件
            log_output.seek(0)
            with open(log_file, "a", encoding="utf-8") as file:
                file.write(log_output.read())

            # 移除 handler 防止重复输出
            logging.getLogger('dirsync').removeHandler(handler)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileProcessorUI()
    window.show()
    sys.exit(app.exec_())
