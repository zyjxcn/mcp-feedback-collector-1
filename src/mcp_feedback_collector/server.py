"""
交互式反馈收集器 MCP 服务器
AI调用时会汇报工作内容，用户可以提供文本反馈和/或图片反馈
"""

import io
import base64
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
import queue
from pathlib import Path
from datetime import datetime
import os
import markdown
import re

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image as MCPImage

# 创建MCP服务器
mcp = FastMCP(
    "交互式反馈收集器",
    dependencies=["pillow", "tkinter"]
)

# 配置超时时间（秒）
DEFAULT_DIALOG_TIMEOUT = 300  # 5分钟
DIALOG_TIMEOUT = int(os.getenv("MCP_DIALOG_TIMEOUT", DEFAULT_DIALOG_TIMEOUT))

class FeedbackDialog:
    def __init__(self, work_summary: str = "", timeout_seconds: int = DIALOG_TIMEOUT):
        self.result_queue = queue.Queue()
        self.root = None
        self.work_summary = work_summary
        self.timeout_seconds = timeout_seconds
        self.selected_images = []  # 改为支持多张图片
        self.image_preview_frame = None
        self.text_widget = None
        
    def show_dialog(self):
        """在新线程中显示反馈收集对话框"""
        def run_dialog():
            self.root = tk.Tk()
            self.root.title("🎯 工作完成汇报与反馈收集")
            self.root.geometry("700x800")
            self.root.resizable(True, True)
            self.root.configure(bg="#f5f5f5")
            
            # 设置窗口图标和样式
            try:
                self.root.iconbitmap(default="")
            except:
                pass
            
            # 居中显示窗口
            self.center_window()
            
            # 创建界面
            self.create_widgets()
            
            # 运行主循环
            self.root.mainloop()
            
        # 在新线程中运行对话框
        dialog_thread = threading.Thread(target=run_dialog)
        dialog_thread.daemon = True
        dialog_thread.start()
        
        # 等待结果
        try:
            result = self.result_queue.get(timeout=self.timeout_seconds)
            return result
        except queue.Empty:
            return None
    
    def center_window(self):
        """将窗口居中显示在屏幕中央"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
            
    def create_widgets(self):
        """创建美化的界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 删除标题标签以节省空间
        
        # 1. 工作汇报区域（增加高度）
        report_frame = tk.LabelFrame(
            main_frame, 
            text="📋 AI 完成汇报", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#2c3e50",
            relief=tk.RAISED,
            bd=2
        )
        report_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 在标题右侧添加深色主题切换按钮（缩小并移到框架最顶部）
        self.is_dark_theme = False  # 主题状态
        self.theme_btn = tk.Button(
            report_frame,
            text="🌙",
            command=self.toggle_theme,
            font=("Microsoft YaHei", 10, "bold"),
            bg="#ecf0f1",
            fg="#34495e",
            width=2,
            height=1,
            relief=tk.RAISED,
            bd=1,
            cursor="hand2",
            activebackground="#d5dbdb",
            activeforeground="#2c3e50"
        )
        self.theme_btn.place(relx=1.0, rely=0, anchor="ne", x=-5, y=-28)
        
        # 保存主要组件引用以便主题切换
        self.main_frame = main_frame
        self.report_frame = report_frame
        
        # 创建可调整大小的容器
        report_paned = tk.PanedWindow(
            report_frame,
            orient=tk.VERTICAL,
            bg="#ffffff",
            sashwidth=8,
            sashrelief=tk.RAISED,
            sashpad=2
        )
        report_paned.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 创建文本容器框架
        text_container = tk.Frame(report_paned, bg="#ffffff")
        
        # 创建可调整大小的文本组件（支持Markdown）
        self.report_text = tk.Text(
            text_container, 
            height=5,  # 初始高度
            wrap=tk.WORD, 
            bg="#ecf0f1", 
            fg="#2c3e50",
            font=("Microsoft YaHei", 10),
            relief=tk.FLAT,
            bd=5,
            state=tk.DISABLED
        )
        self.report_text.pack(fill=tk.BOTH, expand=True)
        
        # 添加到PanedWindow（增加初始高度）
        report_paned.add(text_container, minsize=100, height=200)
        
        # 配置Markdown样式标签
        self.setup_markdown_tags()
        
        # 显示工作汇报内容（支持Markdown）
        self.set_markdown_content(self.work_summary or "本次对话中完成的工作内容...")
        
        # 2. 用户反馈文本区域（减小高度）
        self.feedback_frame = tk.LabelFrame(
            main_frame, 
            text="✍️ 您的反馈", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2
        )
        self.feedback_frame.pack(fill=tk.X, expand=False, pady=(0, 15))
        
        # 文本输入框（减小高度）
        self.text_widget = scrolledtext.ScrolledText(
            self.feedback_frame, 
            height=4, 
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg="#ffffff",
            fg="#2c3e50",
            relief=tk.FLAT,
            bd=5,
            insertbackground="#3498db"
        )
        self.text_widget.pack(fill=tk.X, expand=False, padx=15, pady=15)
        self.text_widget.insert(tk.END, "请在此输入您的反馈、建议或问题...")
        self.text_widget.bind("<FocusIn>", self.clear_placeholder)
        
        # 3. 图片选择区域（默认隐藏，点击标题切换显示）
        self.image_frame_visible = False  # 图片区域显示状态
        
        # 创建可点击的标题框架
        self.image_title_frame = tk.Frame(main_frame, bg="#f5f5f5")
        self.image_title_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 可点击的图片反馈标题
        self.image_title_label = tk.Label(
            self.image_title_frame,
            text="🖼️ 图片反馈（点击展开/收起）",
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ecf0f1",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=10,
            pady=5
        )
        self.image_title_label.pack(fill=tk.X)
        self.image_title_label.bind("<Button-1>", self.toggle_image_frame)
        
        # 图片选择区域（初始隐藏）
        self.image_frame = tk.LabelFrame(
            main_frame, 
            text="🖼️ 图片反馈（可选，支持多张）", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2
        )
        # 初始不显示
        
        # 图片操作按钮
        self.btn_frame = tk.Frame(self.image_frame, bg="#ffffff")
        self.btn_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # 缩小的按钮样式（与提交取消按钮一致）
        btn_style = {
            "font": ("Microsoft YaHei", 8, "bold"),
            "relief": tk.FLAT,
            "bd": 0,
            "cursor": "hand2",
            "height": 1
        }
        
        self.select_file_btn = tk.Button(
            self.btn_frame,
            text="📁 选择图片文件",
            command=self.select_image_file,
            bg="#3498db",
            fg="white",
            width=12,
            **btn_style
        )
        self.select_file_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.paste_btn = tk.Button(
            self.btn_frame,
            text="📋 从剪贴板粘贴",
            command=self.paste_from_clipboard,
            bg="#2ecc71",
            fg="white",
            width=12,
            **btn_style
        )
        self.paste_btn.pack(side=tk.LEFT, padx=4)
        
        self.clear_btn = tk.Button(
            self.btn_frame,
            text="❌ 清除所有图片",
            command=self.clear_all_images,
            bg="#e74c3c",
            fg="white",
            width=12,
            **btn_style
        )
        self.clear_btn.pack(side=tk.LEFT, padx=8)
        
        # 图片预览区域（支持滚动）
        self.preview_container = tk.Frame(self.image_frame, bg="#ffffff")
        self.preview_container.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # 创建滚动画布
        self.canvas = tk.Canvas(self.preview_container, height=120, bg="#f8f9fa", relief=tk.SUNKEN, bd=1)
        self.scrollbar = tk.Scrollbar(self.preview_container, orient="horizontal", command=self.canvas.xview)
        self.image_preview_frame = tk.Frame(self.canvas, bg="#f8f9fa")
        
        self.image_preview_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.image_preview_frame, anchor="nw")
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="top", fill="x")
        self.scrollbar.pack(side="bottom", fill="x")
        
        # 初始提示
        self.update_image_preview()
        
        # 4. 底部区域（左下角提示文字 + 右下角按钮）
        self.bottom_frame = tk.Frame(main_frame, bg="#f5f5f5")
        self.bottom_frame.pack(fill=tk.X, pady=(15, 0))
        
        # 左下角提示信息
        self.info_label = tk.Label(
            self.bottom_frame,
            text="💡 提示：您可以只提供文字反馈、只提供图片，或者两者都提供（支持多张图片）",
            font=("Microsoft YaHei", 9),
            fg="#7f8c8d",
            bg="#f5f5f5"
        )
        self.info_label.pack(side=tk.LEFT, anchor="w")
        
        # 右下角按钮区域
        self.button_frame = tk.Frame(self.bottom_frame, bg="#f5f5f5")
        self.button_frame.pack(side=tk.RIGHT, anchor="e")
        
        # 主要操作按钮
        self.submit_btn = tk.Button(
            self.button_frame,
            text="✅ 提交反馈",
            command=self.submit_feedback,
            font=("Microsoft YaHei", 10, "bold"),
            bg="#27ae60",
            fg="white",
            width=9,
            height=1,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2"
        )
        self.submit_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_btn = tk.Button(
            self.button_frame,
            text="❌ 取消",
            command=self.cancel,
            font=("Microsoft YaHei", 10),
            bg="#95a5a6",
            fg="white",
            width=9,
            height=1,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.LEFT)
        
    def toggle_theme(self):
        """切换深色/浅色主题"""
        self.is_dark_theme = not self.is_dark_theme
        
        if self.is_dark_theme:
            # 深色主题配色
            self.apply_dark_theme()
        else:
            # 浅色主题配色
            self.apply_light_theme()
    
    def apply_dark_theme(self):
        """应用深色主题配色"""
        # 主窗口和主框架
        self.root.config(bg="#2c3e50")
        self.main_frame.config(bg="#2c3e50")
        
        # 标题栏（Windows系统）
        try:
            import ctypes
            from ctypes import wintypes
            # 获取窗口句柄
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            # 设置深色标题栏（Windows 10/11）
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)  # 1为深色模式
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                ctypes.byref(value), ctypes.sizeof(value)
            )
        except:
            pass
        
        # 工作汇报区域
        self.report_frame.config(bg="#34495e", fg="#ecf0f1")
        self.report_text.config(bg="#2c3e50", fg="#ecf0f1", selectbackground="#3498db")
        
        # 文字反馈区域
        self.feedback_frame.config(bg="#34495e", fg="#ecf0f1")
        self.text_widget.config(bg="#2c3e50", fg="#ecf0f1", insertbackground="#ecf0f1")
        
        # 图片反馈区域
        if hasattr(self, 'image_title_frame'):
            self.image_title_frame.config(bg="#2c3e50")
        if hasattr(self, 'image_title_label'):
            self.image_title_label.config(bg="#34495e", fg="#ecf0f1")
        if hasattr(self, 'image_frame'):
            self.image_frame.config(bg="#34495e", fg="#ecf0f1")
        if hasattr(self, 'btn_frame'):
            self.btn_frame.config(bg="#34495e")
        if hasattr(self, 'select_file_btn'):
            self.select_file_btn.config(bg="#2980b9", fg="#ffffff")
        if hasattr(self, 'paste_btn'):
            self.paste_btn.config(bg="#27ae60", fg="#ffffff")
        if hasattr(self, 'clear_btn'):
            self.clear_btn.config(bg="#c0392b", fg="#ffffff")
        if hasattr(self, 'preview_container'):
            self.preview_container.config(bg="#34495e")
        if hasattr(self, 'canvas'):
            self.canvas.config(bg="#2c3e50")
        if hasattr(self, 'image_preview_frame'):
            self.image_preview_frame.config(bg="#2c3e50")
        
        # 底部区域
        self.bottom_frame.config(bg="#2c3e50")
        self.info_label.config(bg="#2c3e50", fg="#bdc3c7")
        self.button_frame.config(bg="#2c3e50")
        
        # 主题按钮（增强视觉效果）
        self.theme_btn.config(
            text="☀️", 
            bg="#34495e", 
            fg="#f39c12",
            activebackground="#2c3e50",
            activeforeground="#f1c40f"
        )
        
        # 提交取消按钮
        self.submit_btn.config(bg="#27ae60", fg="#ffffff")
        self.cancel_btn.config(bg="#e74c3c", fg="#ffffff")
    
    def apply_light_theme(self):
        """应用浅色主题配色"""
        # 主窗口和主框架
        self.root.config(bg="#ffffff")
        self.main_frame.config(bg="#ffffff")
        
        # 标题栏（Windows系统）
        try:
            import ctypes
            from ctypes import wintypes
            # 获取窗口句柄
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            # 设置浅色标题栏（Windows 10/11）
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(0)  # 0为浅色模式
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                ctypes.byref(value), ctypes.sizeof(value)
            )
        except:
            pass
        
        # 工作汇报区域
        self.report_frame.config(bg="#ffffff", fg="#2c3e50")
        self.report_text.config(bg="#f8f9fa", fg="#2c3e50", selectbackground="#3498db")
        
        # 文字反馈区域
        self.feedback_frame.config(bg="#ffffff", fg="#34495e")
        self.text_widget.config(bg="#ffffff", fg="#2c3e50", insertbackground="#2c3e50")
        
        # 图片反馈区域
        if hasattr(self, 'image_title_frame'):
            self.image_title_frame.config(bg="#f5f5f5")
        if hasattr(self, 'image_title_label'):
            self.image_title_label.config(bg="#ecf0f1", fg="#34495e")
        if hasattr(self, 'image_frame'):
            self.image_frame.config(bg="#ffffff", fg="#34495e")
        if hasattr(self, 'btn_frame'):
            self.btn_frame.config(bg="#ffffff")
        if hasattr(self, 'select_file_btn'):
            self.select_file_btn.config(bg="#3498db", fg="white")
        if hasattr(self, 'paste_btn'):
            self.paste_btn.config(bg="#2ecc71", fg="white")
        if hasattr(self, 'clear_btn'):
            self.clear_btn.config(bg="#e74c3c", fg="white")
        if hasattr(self, 'preview_container'):
            self.preview_container.config(bg="#ffffff")
        if hasattr(self, 'canvas'):
            self.canvas.config(bg="#f8f9fa")
        if hasattr(self, 'image_preview_frame'):
            self.image_preview_frame.config(bg="#f8f9fa")
        
        # 底部区域
        self.bottom_frame.config(bg="#ffffff")
        self.info_label.config(bg="#ffffff", fg="#7f8c8d")
        self.button_frame.config(bg="#ffffff")
        
        # 主题按钮（增强视觉效果）
        self.theme_btn.config(
            text="🌙", 
            bg="#ecf0f1", 
            fg="#34495e",
            activebackground="#d5dbdb",
            activeforeground="#2c3e50"
        )
        
        # 提交取消按钮
        self.submit_btn.config(bg="#27ae60", fg="white")
        self.cancel_btn.config(bg="#95a5a6", fg="white")
    
    def toggle_image_frame(self, event=None):
        """切换图片反馈区域的显示状态"""
        if self.image_frame_visible:
            # 隐藏图片区域
            self.image_frame.pack_forget()
            self.image_title_label.config(text="🖼️ 图片反馈（点击展开/收起）")
            self.image_frame_visible = False
        else:
            # 显示图片区域
            self.image_frame.pack(fill=tk.X, pady=(0, 15))
            self.image_title_label.config(text="🖼️ 图片反馈（点击收起）")
            self.image_frame_visible = True
    
    def setup_markdown_tags(self):
        """设置Markdown样式标签"""
        # 标题样式
        self.report_text.tag_configure("h1", font=("Microsoft YaHei", 16, "bold"), foreground="#2c3e50")
        self.report_text.tag_configure("h2", font=("Microsoft YaHei", 14, "bold"), foreground="#34495e")
        self.report_text.tag_configure("h3", font=("Microsoft YaHei", 12, "bold"), foreground="#34495e")
        
        # 代码样式
        self.report_text.tag_configure("code", font=("Consolas", 9), background="#f1f2f6", foreground="#e74c3c")
        self.report_text.tag_configure("code_block", font=("Consolas", 9), background="#f1f2f6", foreground="#2c3e50")
        
        # 强调样式
        self.report_text.tag_configure("bold", font=("Microsoft YaHei", 10, "bold"))
        self.report_text.tag_configure("italic", font=("Microsoft YaHei", 10, "italic"))
        
        # 列表样式
        self.report_text.tag_configure("list", lmargin1=20, lmargin2=20)
        
    def set_markdown_content(self, content):
        """设置Markdown内容并应用样式"""
        self.report_text.config(state=tk.NORMAL)
        self.report_text.delete(1.0, tk.END)
        
        if not content:
            self.report_text.insert(tk.END, "本次对话中完成的工作内容...")
            self.report_text.config(state=tk.DISABLED)
            return
            
        lines = content.split('\n')
        current_pos = 1.0
        
        for line in lines:
            line_start = self.report_text.index(tk.INSERT)
            
            # 处理标题
            if line.startswith('### '):
                self.report_text.insert(tk.END, line[4:] + '\n')
                line_end = self.report_text.index(tk.INSERT + ' -1c')
                self.report_text.tag_add("h3", line_start, line_end)
            elif line.startswith('## '):
                self.report_text.insert(tk.END, line[3:] + '\n')
                line_end = self.report_text.index(tk.INSERT + ' -1c')
                self.report_text.tag_add("h2", line_start, line_end)
            elif line.startswith('# '):
                self.report_text.insert(tk.END, line[2:] + '\n')
                line_end = self.report_text.index(tk.INSERT + ' -1c')
                self.report_text.tag_add("h1", line_start, line_end)
            # 处理代码块
            elif line.startswith('```'):
                self.report_text.insert(tk.END, line + '\n')
                line_end = self.report_text.index(tk.INSERT + ' -1c')
                self.report_text.tag_add("code_block", line_start, line_end)
            # 处理列表
            elif line.startswith('- ') or line.startswith('* ') or re.match(r'^\d+\. ', line):
                self.report_text.insert(tk.END, line + '\n')
                line_end = self.report_text.index(tk.INSERT + ' -1c')
                self.report_text.tag_add("list", line_start, line_end)
            else:
                # 处理行内样式
                processed_line = self.process_inline_markdown(line)
                self.report_text.insert(tk.END, processed_line + '\n')
                
        self.report_text.config(state=tk.DISABLED)
        
    def process_inline_markdown(self, line):
        """处理行内Markdown样式"""
        # 处理行内代码
        line = re.sub(r'`([^`]+)`', r'\1', line)
        
        # 处理粗体
        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        
        # 处理斜体
        line = re.sub(r'\*([^*]+)\*', r'\1', line)
        
        return line
        
    def clear_placeholder(self, event):
        """清除占位符文本"""
        if self.text_widget.get(1.0, tk.END).strip() == "请在此输入您的反馈、建议或问题...":
            self.text_widget.delete(1.0, tk.END)
            
    def select_image_file(self):
        """选择图片文件（支持多选）"""
        file_types = [
            ("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("PNG文件", "*.png"),
            ("JPEG文件", "*.jpg *.jpeg"),
            ("所有文件", "*.*")
        ]
        
        file_paths = filedialog.askopenfilenames(
            title="选择图片文件（可多选）",
            filetypes=file_types
        )
        
        for file_path in file_paths:
            try:
                # 读取并验证图片
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                img = Image.open(io.BytesIO(image_data))
                self.selected_images.append({
                    'data': image_data,
                    'source': f'文件: {Path(file_path).name}',
                    'size': img.size,
                    'image': img
                })
                
            except Exception as e:
                messagebox.showerror("错误", f"无法读取图片文件 {Path(file_path).name}: {str(e)}")
                
        self.update_image_preview()
                
    def paste_from_clipboard(self):
        """从剪贴板粘贴图片"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            
            if img:
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                image_data = buffer.getvalue()
                
                self.selected_images.append({
                    'data': image_data,
                    'source': '剪贴板',
                    'size': img.size,
                    'image': img
                })
                
                self.update_image_preview()
            else:
                messagebox.showwarning("警告", "剪贴板中没有图片数据")
                
        except Exception as e:
            messagebox.showerror("错误", f"无法从剪贴板获取图片: {str(e)}")
            
    def clear_all_images(self):
        """清除所有选择的图片"""
        self.selected_images = []
        self.update_image_preview()
        
    def update_image_preview(self):
        """更新图片预览显示"""
        # 清除现有预览
        for widget in self.image_preview_frame.winfo_children():
            widget.destroy()
            
        if not self.selected_images:
            # 显示未选择图片的提示
            no_image_label = tk.Label(
                self.image_preview_frame,
                text="未选择图片",
                bg="#f8f9fa",
                fg="#95a5a6",
                font=("Microsoft YaHei", 10)
            )
            no_image_label.pack(pady=20)
        else:
            # 显示所有图片预览
            for i, img_info in enumerate(self.selected_images):
                try:
                    # 创建单个图片预览容器
                    img_container = tk.Frame(self.image_preview_frame, bg="#ffffff", relief=tk.RAISED, bd=1)
                    img_container.pack(side=tk.LEFT, padx=5, pady=5)
                    
                    # 创建缩略图
                    img_copy = img_info['image'].copy()
                    img_copy.thumbnail((100, 80), Image.Resampling.LANCZOS)
                    
                    # 转换为tkinter可用的格式
                    photo = ImageTk.PhotoImage(img_copy)
                    
                    # 图片标签
                    img_label = tk.Label(img_container, image=photo, bg="#ffffff")
                    img_label.image = photo  # 保持引用
                    img_label.pack(padx=5, pady=5)
                    
                    # 图片信息
                    info_text = f"{img_info['source']}\n{img_info['size'][0]}x{img_info['size'][1]}"
                    info_label = tk.Label(
                        img_container,
                        text=info_text,
                        font=("Microsoft YaHei", 8),
                        bg="#ffffff",
                        fg="#7f8c8d"
                    )
                    info_label.pack(pady=(0, 5))
                    
                    # 删除按钮
                    del_btn = tk.Button(
                        img_container,
                        text="×",
                        command=lambda idx=i: self.remove_image(idx),
                        font=("Arial", 10, "bold"),
                        bg="#e74c3c",
                        fg="white",
                        width=3,
                        relief=tk.FLAT,
                        cursor="hand2"
                    )
                    del_btn.pack(pady=(0, 5))
                    
                except Exception as e:
                    print(f"预览更新失败: {e}")
                    
    def remove_image(self, index):
        """删除指定索引的图片"""
        if 0 <= index < len(self.selected_images):
            self.selected_images.pop(index)
            self.update_image_preview()
            
    def submit_feedback(self):
        """提交反馈"""
        # 获取文本内容
        text_content = self.text_widget.get(1.0, tk.END).strip()
        if text_content == "请在此输入您的反馈、建议或问题...":
            text_content = ""
            
        # 检查是否有内容
        has_text = bool(text_content)
        has_images = bool(self.selected_images)
        
        if not has_text and not has_images:
            messagebox.showwarning("警告", "请至少提供文字反馈或图片反馈")
            return
            
        # 准备结果数据
        result = {
            'success': True,
            'text_feedback': text_content if has_text else None,
            'images': [img['data'] for img in self.selected_images] if has_images else None,
            'image_sources': [img['source'] for img in self.selected_images] if has_images else None,
            'has_text': has_text,
            'has_images': has_images,
            'image_count': len(self.selected_images),
            'timestamp': datetime.now().isoformat()
        }
        
        self.result_queue.put(result)
        self.root.destroy()
        
    def cancel(self):
        """取消操作"""
        self.result_queue.put({
            'success': False,
            'message': '用户取消了反馈提交'
        })
        self.root.destroy()


@mcp.tool()
def collect_feedback(work_summary: str = "", timeout_seconds: int = DIALOG_TIMEOUT) -> list:
    """
    收集用户反馈的交互式工具。AI可以汇报完成的工作，用户可以提供文字和/或图片反馈。
    
    Args:
        work_summary: AI完成的工作内容汇报
        timeout_seconds: 对话框超时时间（秒），默认300秒（5分钟）
        
    Returns:
        包含用户反馈内容的列表，可能包含文本和图片
    """
    dialog = FeedbackDialog(work_summary, timeout_seconds)
    result = dialog.show_dialog()
    
    if result is None:
        raise Exception(f"操作超时（{timeout_seconds}秒），请重试")
        
    if not result['success']:
        raise Exception(result.get('message', '用户取消了反馈提交'))
    
    # 构建返回内容列表
    feedback_items = []
    
    # 添加文字反馈
    if result['has_text']:
        from mcp.types import TextContent
        feedback_items.append(TextContent(
            type="text", 
            text=f"用户文字反馈：{result['text_feedback']}\n提交时间：{result['timestamp']}"
        ))
        
    # 添加图片反馈
    if result['has_images']:
        for image_data, source in zip(result['images'], result['image_sources']):
            feedback_items.append(MCPImage(data=image_data, format='png'))
        
    return feedback_items


@mcp.tool()
def pick_image() -> MCPImage:
    """
    弹出图片选择对话框，让用户选择图片文件或从剪贴板粘贴图片。
    用户可以选择本地图片文件，或者先截图到剪贴板然后粘贴。
    """
    # 使用简化的对话框只选择图片
    dialog = FeedbackDialog()
    dialog.work_summary = "请选择一张图片"
    
    # 创建简化版本的图片选择对话框
    def simple_image_dialog():
        root = tk.Tk()
        root.title("选择图片")
        root.geometry("400x300")
        root.resizable(False, False)
        root.eval('tk::PlaceWindow . center')
        
        selected_image = {'data': None}
        
        def select_file():
            file_path = filedialog.askopenfilename(
                title="选择图片文件",
                filetypes=[("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
            )
            if file_path:
                try:
                    with open(file_path, 'rb') as f:
                        selected_image['data'] = f.read()
                    root.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"无法读取图片: {e}")
                    
        def paste_clipboard():
            try:
                from PIL import ImageGrab
                img = ImageGrab.grabclipboard()
                if img:
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    selected_image['data'] = buffer.getvalue()
                    root.destroy()
                else:
                    messagebox.showwarning("警告", "剪贴板中没有图片")
            except Exception as e:
                messagebox.showerror("错误", f"剪贴板操作失败: {e}")
                
        def cancel():
            root.destroy()
            
        # 界面
        tk.Label(root, text="请选择图片来源", font=("Arial", 14, "bold")).pack(pady=20)
        
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="📁 选择图片文件", font=("Arial", 12), 
                 width=20, height=2, command=select_file).pack(pady=10)
        tk.Button(btn_frame, text="📋 从剪贴板粘贴", font=("Arial", 12), 
                 width=20, height=2, command=paste_clipboard).pack(pady=10)
        tk.Button(btn_frame, text="❌ 取消", font=("Arial", 12), 
                 width=20, height=1, command=cancel).pack(pady=10)
        
        root.mainloop()
        return selected_image['data']
    
    image_data = simple_image_dialog()
    
    if image_data is None:
        raise Exception("未选择图片或操作被取消")
        
    return MCPImage(data=image_data, format='png')


@mcp.tool()
def get_image_info(image_path: str) -> str:
    """
    获取指定路径图片的信息（尺寸、格式等）
    
    Args:
        image_path: 图片文件路径
    """
    try:
        path = Path(image_path)
        if not path.exists():
            return f"文件不存在: {image_path}"
            
        with Image.open(path) as img:
            info = {
                "文件名": path.name,
                "格式": img.format,
                "尺寸": f"{img.width} x {img.height}",
                "模式": img.mode,
                "文件大小": f"{path.stat().st_size / 1024:.1f} KB"
            }
            
        return "\n".join([f"{k}: {v}" for k, v in info.items()])
        
    except Exception as e:
        return f"获取图片信息失败: {str(e)}"


if __name__ == "__main__":
    mcp.run()


def main():
    """Main entry point for the mcp-feedback-collector command."""
    mcp.run()