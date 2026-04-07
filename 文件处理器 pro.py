import json
import sys
import os
from io import StringIO
import logging
import shutil
from datetime import datetime

import dirsync
import pandas as pd
import requests
import socket
import mimetypes
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor, QIcon, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QStatusBar, QMenuBar, QAction,
    QFileDialog, QDialog, QFormLayout, QDialogButtonBox, QComboBox, QMessageBox,
    QCheckBox, QInputDialog, QRadioButton, QGroupBox, QGridLayout, QProgressBar,
    QSplitter, QFrame, QTabWidget, QListWidget, QListWidgetItem
)


def is_connected():
    """检查是否可以连接到互联网"""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False


class BackupThread(QThread):
    """备份线程，避免界面卡顿"""
    log_signal = pyqtSignal(str, str)  # 消息, 颜色
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source, target, mode):
        super().__init__()
        self.source = source
        self.target = target
        self.mode = mode

    def run(self):
        try:
            if self.mode == "增量同步":
                self.run_dirsync(self.source, self.target, action='sync', create=True, purge=False)
            elif self.mode == "单向同步":
                self.run_dirsync(self.source, self.target, action='sync', create=True, purge=True)
            elif self.mode == "镜像同步":
                self.run_dirsync(self.source, self.target, action='sync', create=True, purge=True)
                self.run_dirsync(self.target, self.source, action='sync', create=True, purge=True)
            self.finished_signal.emit(True, "备份完成！")
        except Exception as e:
            self.finished_signal.emit(False, f"备份失败: {str(e)}")

    def run_dirsync(self, source, target, action, create=True, purge=False):
        log_output = StringIO()
        handler = logging.StreamHandler(log_output)
        logging.getLogger('dirsync').addHandler(handler)

        try:
            dirsync.sync(source, target, action=action, create=create, purge=purge, verbose=True)
            log_output.seek(0)
            for line in log_output:
                self.log_signal.emit(line.strip(), "blue")
        finally:
            logging.getLogger('dirsync').removeHandler(handler)


class FileProcessorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_version = "v2.0"
        self.version_url = "https://raw.githubusercontent.com/haisi-ai/File-processor/refs/heads/main/version.txt"
        self.current_path = ""
        self.init_ui()
        self.setup_stylesheet()

    def setup_stylesheet(self):
        """设置界面样式表"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #4CAF50;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #c0c0c0;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
            QStatusBar {
                background-color: #2c3e50;
                color: white;
            }
        """)

    def init_ui(self):
        """初始化界面布局"""
        self.setWindowTitle("文件处理器 Pro")
        self.setWindowIcon(QIcon("logo.ico"))
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 使用分割器
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧功能区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 路径选择区域
        path_group = QGroupBox("路径选择")
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请选择文件或文件夹路径...")
        self.select_path_button = QPushButton("浏览")
        self.select_path_button.clicked.connect(self.select_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.select_path_button)
        path_group.setLayout(path_layout)
        left_layout.addWidget(path_group)

        # 使用标签页组织功能
        self.tab_widget = QTabWidget()

        # 文件操作标签页
        self.create_file_tab()
        # 备份标签页
        self.create_backup_tab()
        # 批量处理标签页
        self.create_batch_tab()

        left_layout.addWidget(self.tab_widget)

        # 右侧日志区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))

        log_button_layout = QHBoxLayout()
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        save_log_btn = QPushButton("保存日志")
        save_log_btn.clicked.connect(self.save_log)
        log_button_layout.addWidget(clear_log_btn)
        log_button_layout.addWidget(save_log_btn)

        log_layout.addWidget(self.log_output)
        log_layout.addLayout(log_button_layout)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 600])

        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(main_splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 菜单栏
        self.create_menu_bar()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def create_menu_bar(self):
        """创建菜单栏"""
        menu_bar = QMenuBar()
        self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("文件")
        help_menu = menu_bar.addMenu("帮助")

        save_log_action = QAction("保存日志", self)
        save_log_action.setShortcut("Ctrl+S")
        save_log_action.triggered.connect(self.save_log)
        file_menu.addAction(save_log_action)

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        update_action = QAction("检查更新", self)
        update_action.triggered.connect(self.show_update_dialog)
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about_message)
        help_menu.addAction(update_action)
        help_menu.addAction(about_action)

    def create_file_tab(self):
        """创建文件操作标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 第一行按钮
        btn_layout1 = QHBoxLayout()
        self.get_name_btn = QPushButton("📁 获取名称")
        self.get_name_btn.clicked.connect(self.get_names_to_excel)
        self.rename_btn = QPushButton("✏️ 修改名称")
        self.rename_btn.clicked.connect(self.change_rename)
        self.change_ext_btn = QPushButton("📝 修改后缀")
        self.change_ext_btn.clicked.connect(self.change_extension_by_excel)
        btn_layout1.addWidget(self.get_name_btn)
        btn_layout1.addWidget(self.rename_btn)
        btn_layout1.addWidget(self.change_ext_btn)

        # 第二行按钮
        btn_layout2 = QHBoxLayout()
        self.create_file_btn = QPushButton("📄 创建文件/文件夹")
        self.create_file_btn.clicked.connect(self.create_from_excel)
        self.delete_file_btn = QPushButton("🗑️ 删除文件")
        self.delete_file_btn.clicked.connect(self.delete_files_by_excel)
        self.process_all_btn = QPushButton("⚡ 一键处理")
        self.process_all_btn.clicked.connect(self.process_all_in_one)
        btn_layout2.addWidget(self.create_file_btn)
        btn_layout2.addWidget(self.delete_file_btn)
        btn_layout2.addWidget(self.process_all_btn)

        layout.addLayout(btn_layout1)
        layout.addLayout(btn_layout2)
        layout.addStretch()

        self.tab_widget.addTab(tab, "文件操作")

    def create_backup_tab(self):
        """创建备份标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 路径设置
        path_group = QGroupBox("备份路径设置")
        path_layout = QGridLayout()

        path_layout.addWidget(QLabel("源路径:"), 0, 0)
        self.left_path_input = QLineEdit()
        path_layout.addWidget(self.left_path_input, 0, 1)
        left_btn = QPushButton("浏览")
        left_btn.clicked.connect(lambda: self.select_directory(self.left_path_input))
        path_layout.addWidget(left_btn, 0, 2)

        path_layout.addWidget(QLabel("目标路径:"), 1, 0)
        self.right_path_input = QLineEdit()
        path_layout.addWidget(self.right_path_input, 1, 1)
        right_btn = QPushButton("浏览")
        right_btn.clicked.connect(lambda: self.select_directory(self.right_path_input))
        path_layout.addWidget(right_btn, 1, 2)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # 同步模式
        mode_group = QGroupBox("同步模式")
        mode_layout = QHBoxLayout()
        self.incremental_backup = QRadioButton("增量同步")
        self.sync_left_to_right = QRadioButton("单向同步")
        self.sync_mirror = QRadioButton("镜像同步")
        self.incremental_backup.setChecked(True)
        mode_layout.addWidget(self.incremental_backup)
        mode_layout.addWidget(self.sync_left_to_right)
        mode_layout.addWidget(self.sync_mirror)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 备份组管理
        group_group = QGroupBox("备份组管理")
        group_layout = QVBoxLayout()

        self.sync_group_list = QListWidget()
        self.load_sync_groups()
        group_layout.addWidget(self.sync_group_list)

        group_btn_layout = QHBoxLayout()
        save_group_btn = QPushButton("保存当前设置为备份组")
        save_group_btn.clicked.connect(self.save_sync_group)
        load_group_btn = QPushButton("加载选中备份组")
        load_group_btn.clicked.connect(self.load_selected_group)
        delete_group_btn = QPushButton("删除选中备份组")
        delete_group_btn.clicked.connect(self.delete_selected_group)
        group_btn_layout.addWidget(save_group_btn)
        group_btn_layout.addWidget(load_group_btn)
        group_btn_layout.addWidget(delete_group_btn)
        group_layout.addLayout(group_btn_layout)

        group_group.setLayout(group_layout)
        layout.addWidget(group_group)

        # 备份按钮
        backup_btn = QPushButton("🚀 开始备份")
        backup_btn.setStyleSheet("QPushButton { background-color: #2196F3; font-size: 14px; padding: 10px; }")
        backup_btn.clicked.connect(self.start_backup)
        layout.addWidget(backup_btn)

        self.tab_widget.addTab(tab, "文件备份")

    def create_batch_tab(self):
        """创建批量处理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel(
            "Excel 文件格式说明：\n"
            "• 列A: 源文件名/路径\n"
            "• 列B: 新文件名（用于重命名）\n"
            "• 列C: 新后缀（用于修改后缀）\n"
            "• 列D: 是否删除（填写 'delete' 或 '是' 标记删除）\n\n"
            "提示：可以只填写需要操作的列，其他列留空即可。"
        )
        info_label.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 4px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        create_template_btn = QPushButton("📋 创建模板Excel")
        create_template_btn.clicked.connect(self.create_template_excel)
        btn_layout.addWidget(create_template_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "批量处理")

    def select_path(self):
        """选择文件或文件夹路径"""
        options = QFileDialog.Options()
        file_path = QFileDialog.getExistingDirectory(self, "选择文件夹", options=options)
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*.*)")

        if file_path:
            self.current_path = file_path
            self.path_input.setText(file_path)
            self.append_to_log(f"已选择路径: {file_path}", "green")
        else:
            self.append_to_log("未选择任何路径", "orange")

    def get_names_to_excel(self):
        """获取所有文件/文件夹名称并导出到Excel"""
        if not self.current_path or not os.path.exists(self.current_path):
            self.append_to_log("请先选择有效的路径！", "red")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存Excel文件", "", "Excel文件 (*.xlsx)")
        if not save_path:
            return

        self.append_to_log("正在扫描目录...", "blue")

        data = []
        for root, dirs, files in os.walk(self.current_path):
            rel_path = os.path.relpath(root, self.current_path)
            if rel_path == ".":
                rel_path = ""

            for dir_name in dirs:
                full_path = os.path.join(root, dir_name)
                data.append({
                    "相对路径": os.path.join(rel_path, dir_name) if rel_path else dir_name,
                    "完整路径": full_path,
                    "名称": dir_name,
                    "类型": "文件夹",
                    "大小": "",
                    "修改时间": datetime.fromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%d %H:%M:%S")
                })

            for file_name in files:
                full_path = os.path.join(root, file_name)
                file_size = os.path.getsize(full_path)
                size_str = self.format_size(file_size)
                ext = os.path.splitext(file_name)[1].lower()
                file_type = self.get_file_type(ext)

                data.append({
                    "相对路径": os.path.join(rel_path, file_name) if rel_path else file_name,
                    "完整路径": full_path,
                    "名称": file_name,
                    "类型": file_type,
                    "大小": size_str,
                    "修改时间": datetime.fromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%d %H:%M:%S")
                })

        df = pd.DataFrame(data)
        df.to_excel(save_path, index=False)
        self.append_to_log(f"已导出 {len(data)} 个项目到: {save_path}", "green")

    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def get_file_type(self, ext):
        """获取文件类型分类"""
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp']
        audio_exts = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        doc_exts = ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.md']
        archive_exts = ['.zip', '.rar', '.7z', '.tar', '.gz']

        if ext in image_exts:
            return "图片"
        elif ext in audio_exts:
            return "音频"
        elif ext in video_exts:
            return "视频"
        elif ext in doc_exts:
            return "文档"
        elif ext in archive_exts:
            return "压缩包"
        elif ext in ['.exe', '.msi', '.sh', '.bat', '.py']:
            return "可执行文件"
        else:
            return "其他"

    def change_rename(self):
        """根据Excel文件批量重命名"""
        if not self.current_path:
            self.append_to_log("请先选择路径！", "red")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
            if df.shape[1] < 2:
                self.append_to_log("Excel文件至少需要两列（原文件名 -> 新文件名）", "red")
                return

            success_count = 0
            for idx, row in df.iterrows():
                old_name = str(row.iloc[0])
                new_name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""

                if not new_name or new_name == "nan":
                    continue

                old_path = os.path.join(self.current_path, old_name)
                new_path = os.path.join(self.current_path, new_name)

                if os.path.exists(old_path):
                    try:
                        os.rename(old_path, new_path)
                        self.append_to_log(f"重命名: {old_name} -> {new_name}", "green")
                        success_count += 1
                    except Exception as e:
                        self.append_to_log(f"重命名失败 {old_name}: {e}", "red")
                else:
                    self.append_to_log(f"文件不存在: {old_name}", "orange")

            self.append_to_log(f"重命名完成！成功: {success_count} 个", "green")
        except Exception as e:
            self.append_to_log(f"读取Excel失败: {e}", "red")

    def change_extension_by_excel(self):
        """根据Excel文件批量修改后缀"""
        if not self.current_path:
            self.append_to_log("请先选择路径！", "red")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
            # 支持两列：原文件名 -> 新后缀，或三列：原文件名 -> 原后缀 -> 新后缀
            success_count = 0

            for idx, row in df.iterrows():
                old_name = str(row.iloc[0])
                new_ext = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""

                if not new_ext or new_ext == "nan":
                    continue

                # 确保后缀有点号
                if not new_ext.startswith('.'):
                    new_ext = '.' + new_ext

                old_path = os.path.join(self.current_path, old_name)
                base_name = os.path.splitext(old_name)[0]
                new_path = os.path.join(self.current_path, base_name + new_ext)

                if os.path.exists(old_path):
                    try:
                        os.rename(old_path, new_path)
                        self.append_to_log(f"修改后缀: {old_name} -> {base_name}{new_ext}", "green")
                        success_count += 1
                    except Exception as e:
                        self.append_to_log(f"修改失败 {old_name}: {e}", "red")
                else:
                    self.append_to_log(f"文件不存在: {old_name}", "orange")

            self.append_to_log(f"后缀修改完成！成功: {success_count} 个", "green")
        except Exception as e:
            self.append_to_log(f"读取Excel失败: {e}", "red")

    def create_from_excel(self):
        """根据Excel文件批量创建文件和文件夹"""
        if not self.current_path:
            self.append_to_log("请先选择路径！", "red")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
            items = df.iloc[:, 0].astype(str).tolist()

            success_count = 0
            for item in items:
                if item == "nan":
                    continue

                item_path = os.path.join(self.current_path, item)

                if '.' in os.path.basename(item):  # 是文件
                    os.makedirs(os.path.dirname(item_path), exist_ok=True)
                    if not os.path.exists(item_path):
                        with open(item_path, 'w', encoding='utf-8') as f:
                            pass
                        self.append_to_log(f"创建文件: {item}", "green")
                        success_count += 1
                else:  # 是文件夹
                    if not os.path.exists(item_path):
                        os.makedirs(item_path)
                        self.append_to_log(f"创建文件夹: {item}", "green")
                        success_count += 1

            self.append_to_log(f"创建完成！成功: {success_count} 个", "green")
        except Exception as e:
            self.append_to_log(f"创建失败: {e}", "red")

    def delete_files_by_excel(self):
        """根据Excel文件批量删除文件"""
        if not self.current_path:
            self.append_to_log("请先选择路径！", "red")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)

            # 查找删除标记列
            delete_col = None
            for col in df.columns:
                if 'delete' in str(col).lower() or '删除' in str(col):
                    delete_col = col
                    break

            if delete_col is None and df.shape[1] >= 2:
                # 默认使用第二列作为删除标记
                delete_col = df.columns[1]

            success_count = 0
            for idx, row in df.iterrows():
                file_name = str(row.iloc[0])
                delete_flag = str(row[delete_col]).lower() if delete_col in row else ""

                if delete_flag in ['delete', '是', 'yes', 'true', '1']:
                    file_path_full = os.path.join(self.current_path, file_name)

                    if os.path.exists(file_path_full):
                        try:
                            if os.path.isfile(file_path_full):
                                os.remove(file_path_full)
                            else:
                                shutil.rmtree(file_path_full)
                            self.append_to_log(f"已删除: {file_name}", "green")
                            success_count += 1
                        except Exception as e:
                            self.append_to_log(f"删除失败 {file_name}: {e}", "red")
                    else:
                        self.append_to_log(f"文件不存在: {file_name}", "orange")

            self.append_to_log(f"删除完成！已删除: {success_count} 个", "green")
        except Exception as e:
            self.append_to_log(f"处理失败: {e}", "red")

    def process_all_in_one(self):
        """一键处理：整合所有功能到一个Excel"""
        if not self.current_path:
            self.append_to_log("请先选择路径！", "red")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存处理Excel文件", "", "Excel文件 (*.xlsx)")
        if not save_path:
            return

        # 扫描目录获取所有文件
        data = []
        for root, dirs, files in os.walk(self.current_path):
            rel_path = os.path.relpath(root, self.current_path)
            if rel_path == ".":
                rel_path = ""

            for file_name in files:
                full_path = os.path.join(root, file_name)
                rel_full_path = os.path.join(rel_path, file_name) if rel_path else file_name
                name_without_ext = os.path.splitext(file_name)[0]
                ext = os.path.splitext(file_name)[1]

                data.append({
                    "源文件名": rel_full_path,
                    "新文件名": name_without_ext,
                    "新后缀": ext[1:] if ext else "",
                    "是否删除": "",
                    "备注": ""
                })

        df = pd.DataFrame(data)
        df.to_excel(save_path, index=False)

        self.append_to_log(f"已生成处理模板Excel: {save_path}", "green")
        self.append_to_log("请编辑Excel文件后，使用各个功能按钮分别处理", "blue")

        # 询问是否立即打开
        reply = QMessageBox.question(self, "打开文件", "是否立即打开Excel文件进行编辑？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            os.startfile(save_path)

    def create_template_excel(self):
        """创建模板Excel文件"""
        save_path, _ = QFileDialog.getSaveFileName(self, "保存模板Excel", "", "Excel文件 (*.xlsx)")
        if not save_path:
            return

        template_data = {
            "源文件名": ["示例文件1.txt", "示例文件夹/示例文件2.pdf", "示例文件夹/子文件夹"],
            "新文件名": ["新文件1", "新文件2", ""],
            "新后缀": ["", ".docx", ""],
            "是否删除": ["", "delete", ""],
            "说明": ["修改名称示例", "删除示例", "创建文件夹示例"]
        }

        df = pd.DataFrame(template_data)
        df.to_excel(save_path, index=False)
        self.append_to_log(f"模板已创建: {save_path}", "green")

        reply = QMessageBox.question(self, "打开文件", "是否立即打开模板文件？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            os.startfile(save_path)

    def select_directory(self, input_field):
        """选择目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择目录")
        if directory:
            input_field.setText(directory)

    def load_sync_groups(self):
        """加载备份组列表"""
        sync_groups = self.load_sync_groups_from_file()
        self.sync_group_list.clear()
        for name, data in sync_groups.items():
            item = QListWidgetItem(f"{name} | {data['source']} -> {data['target']} ({data['mode']})")
            item.setData(Qt.UserRole, name)
            self.sync_group_list.addItem(item)

    def load_selected_group(self):
        """加载选中的备份组"""
        current_item = self.sync_group_list.currentItem()
        if not current_item:
            self.append_to_log("请先选择一个备份组", "orange")
            return

        group_name = current_item.data(Qt.UserRole)
        sync_groups = self.load_sync_groups_from_file()

        if group_name in sync_groups:
            data = sync_groups[group_name]
            self.left_path_input.setText(data["source"])
            self.right_path_input.setText(data["target"])

            mode = data["mode"]
            if mode == "增量同步":
                self.incremental_backup.setChecked(True)
            elif mode == "单向同步":
                self.sync_left_to_right.setChecked(True)
            elif mode == "镜像同步":
                self.sync_mirror.setChecked(True)

            self.append_to_log(f"已加载备份组: {group_name}", "green")

    def delete_selected_group(self):
        """删除选中的备份组"""
        current_item = self.sync_group_list.currentItem()
        if not current_item:
            self.append_to_log("请先选择一个备份组", "orange")
            return

        group_name = current_item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除备份组 '{group_name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            sync_groups = self.load_sync_groups_from_file()
            if group_name in sync_groups:
                del sync_groups[group_name]
                self.save_sync_groups_to_file(sync_groups)
                self.load_sync_groups()
                self.append_to_log(f"已删除备份组: {group_name}", "green")

    def save_sync_group(self):
        """保存备份组"""
        source = self.left_path_input.text()
        target = self.right_path_input.text()

        if not source or not target:
            self.append_to_log("请填写源路径和目标路径", "red")
            return

        if self.incremental_backup.isChecked():
            mode = "增量同步"
        elif self.sync_left_to_right.isChecked():
            mode = "单向同步"
        else:
            mode = "镜像同步"

        group_name, ok = QInputDialog.getText(self, "保存备份组", "请输入备份组名称：")
        if not ok or not group_name.strip():
            return

        sync_groups = self.load_sync_groups_from_file()
        sync_groups[group_name] = {"source": source, "target": target, "mode": mode}
        self.save_sync_groups_to_file(sync_groups)
        self.load_sync_groups()
        self.append_to_log(f"备份组 '{group_name}' 已保存", "green")

    def load_sync_groups_from_file(self):
        """从文件加载备份组"""
        try:
            with open("sync_groups.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_sync_groups_to_file(self, sync_groups):
        """保存备份组到文件"""
        with open("sync_groups.json", "w", encoding="utf-8") as f:
            json.dump(sync_groups, f, indent=4, ensure_ascii=False)

    def start_backup(self):
        """开始备份"""
        source = self.left_path_input.text()
        target = self.right_path_input.text()

        if not source or not target:
            self.append_to_log("请填写源路径和目标路径", "red")
            return

        if not os.path.exists(source):
            self.append_to_log(f"源路径不存在: {source}", "red")
            return

        if self.incremental_backup.isChecked():
            mode = "增量同步"
        elif self.sync_left_to_right.isChecked():
            mode = "单向同步"
        else:
            mode = "镜像同步"

        self.append_to_log(f"开始{mode}...", "blue")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        self.backup_thread = BackupThread(source, target, mode)
        self.backup_thread.log_signal.connect(self.append_to_log)
        self.backup_thread.finished_signal.connect(self.on_backup_finished)
        self.backup_thread.start()

    def on_backup_finished(self, success, message):
        """备份完成回调"""
        self.progress_bar.setVisible(False)
        if success:
            self.append_to_log(message, "green")
        else:
            self.append_to_log(message, "red")

    def append_to_log(self, text, color="black"):
        """添加日志"""
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        timestamp = datetime.now().strftime("%H:%M:%S")
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(f"[{timestamp}] {text}\n")
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def save_log(self):
        """保存日志"""
        log_text = self.log_output.toPlainText()
        file_name, _ = QFileDialog.getSaveFileName(self, "保存日志", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(log_text)
            self.append_to_log(f"日志已保存: {file_name}", "green")

    def show_about_message(self):
        """显示关于信息"""
        QMessageBox.about(self, "关于",
                          f"<h2>文件处理器 Pro</h2>"
                          f"<p>版本: {self.current_version}</p>"
                          f"<p>一个功能强大的文件批量处理工具</p>"
                          f"<p>功能特性：</p>"
                          f"<ul>"
                          f"<li>批量获取文件信息并导出Excel</li>"
                          f"<li>批量重命名文件</li>"
                          f"<li>批量修改文件后缀</li>"
                          f"<li>批量创建文件/文件夹</li>"
                          f"<li>批量删除文件</li>"
                          f"<li>文件备份同步</li>"
                          f"</ul>"
                          f"<p>作者：海斯</p>")

    def show_update_dialog(self):
        """检查更新"""
        QMessageBox.information(self, "检查更新", f"当前版本 {self.current_version} 已是最新版本！")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileProcessorUI()
    window.show()
    sys.exit(app.exec_())