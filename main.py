import sys
import json
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, QLabel, 
                             QFileDialog, QTextEdit, QMessageBox, QScrollArea,
                             QGridLayout, QFrame, QSplitter, QTabWidget,
                             QComboBox, QSpinBox, QCheckBox, QGroupBox, QListWidget,
                             QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize, QTimer
from PyQt6.QtGui import QFont, QPalette, QPixmap, QPainter, QPen, QColor, QBrush, QPolygon

# 全局常量：像素到毫米的转换比例
PER_PIXEL_MM = 127.0 / 9570


class ClassManager:
    """类别管理器，负责加载和管理缺陷类别"""
    def __init__(self, classes_file_path=None):
        self.classes = {}
        self.load_classes(classes_file_path)
    
    def load_classes(self, classes_file_path=None):
        """加载类别文件"""
        if not classes_file_path:
            # 尝试在当前目录或主应用目录找到classes.txt
            current_dir = os.path.dirname(os.path.abspath(__file__))
            classes_file_path = os.path.join(current_dir, 'classes.txt')
        
        try:
            with open(classes_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line:
                        parts = line.split(',', 1)
                        class_id = int(parts[0])
                        class_name = parts[1].strip('"')
                        self.classes[class_id] = class_name
        except FileNotFoundError:
            print(f"类别文件未找到: {classes_file_path}")
            # 使用默认类别
            self.classes = {
                0: "废丝", 1: "大糙", 2: "粘附糙", 3: "大长结", 4: "重螺旋",
                5: "小糙", 6: "长结", 7: "螺旋", 8: "环及裂丝", 9: "特大糙疵",
                10: "洁净度", 11: "非缺陷"
            }
        except Exception as e:
            print(f"加载类别文件时出错: {e}")
            self.classes = {11: "非缺陷", 1: "缺陷"}
    
    def get_class_name(self, class_id):
        """根据类别ID获取类别名称"""
        return self.classes.get(class_id, f"未知类别({class_id})")
    
    def get_all_classes(self):
        """获取所有类别"""
        return self.classes
    
    def get_class_color(self, class_id):
        """根据类别ID获取颜色"""
        if class_id == 10:  # 洁净度
            return QColor(0, 0, 255)  # 蓝色
        elif class_id == 11:  # 非缺陷
            return QColor(0, 255, 0)  # 绿色
        else:  # 其他所有缺陷类别
            return QColor(255, 0, 0)  # 红色


class ImageLabel(QLabel):
    """自定义图片标签，支持绘制缺陷区域"""
    region_clicked = pyqtSignal(int)  # 发送被点击区域的信号
    new_region_created = pyqtSignal(int, int, int, int)  # 发送新建区域的信号 (x, y, width, height)
    region_unselected = pyqtSignal()  # 发送取消选中区域的信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.regions = []
        self.class_manager = None
        self.scale_factor = 1.0
        self.zoom_factor = 1.0  # 用户缩放倍数
        self.selected_region_index = -1  # 当前选中的区域索引
        self.regions_visible = True  # 区域框是否可见，默认为True
        self.setMinimumSize(400, 300)
        self.setStyleSheet("border: 1px solid gray;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 接受键盘焦点
        self.setScaledContents(False)  # 不自动缩放内容
        
        # 添加缺陷模式相关变量
        self.add_defect_mode = False
        self.drawing = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.current_rect = QRect()
        
        # 图片拖动相关变量
        self.panning = False
        self.pan_start_point = QPoint()
        self.scroll_area = None  # 滚动区域的引用
        self.click_threshold = 5  # 点击和拖动的阈值（像素）
        
    def clear_image_cache(self):
        """清除图片缓存"""
        self.original_pixmap = None
        self.regions = []
        self.selected_region_index = -1
        self.zoom_factor = 1.0
        self.scale_factor = 1.0
        self.image_path = None
        self.clear()  # 清除QLabel显示的内容
        self.setText("无图片")
        print("图片缓存已清除")
        
    def set_image_and_regions(self, image_path, regions, class_manager):
        """设置图片和缺陷区域"""
        try:
            self.image_path = image_path
            self.regions = regions or []
            self.class_manager = class_manager
            
            if not image_path:
                self.setText("未指定图片路径")
                return
                
            if not os.path.exists(image_path):
                self.setText(f"图片文件不存在: {os.path.basename(image_path)}")
                return
            
            self.original_pixmap = QPixmap(image_path)
            if self.original_pixmap.isNull():
                print(f"无法加载图片: {image_path}")
                self.setText(f"无法加载图片: {os.path.basename(image_path)}")
                return
                
            self.update_display()
            
        except Exception as e:
            print(f"设置图片和区域时出错: {e}")
            import traceback
            traceback.print_exc()
            self.setText(f"加载图片出错: {str(e)}")
    
    def update_display(self):
        """更新显示"""
        if not self.original_pixmap:
            return
        
        try:
            # 获取原始图片尺寸
            pixmap_size = self.original_pixmap.size()
            
            # 计算缩放后的尺寸
            new_width = int(pixmap_size.width() * self.zoom_factor)
            new_height = int(pixmap_size.height() * self.zoom_factor)
            
            # 确保尺寸不为0
            if new_width <= 0 or new_height <= 0:
                return
            
            # 缩放图片
            scaled_pixmap = self.original_pixmap.scaled(
                new_width, 
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # 更新scale_factor用于区域绘制
            self.scale_factor = self.zoom_factor
            
            # 绘制缺陷区域
            pixmap_with_regions = self.draw_regions(scaled_pixmap)
            
            # 设置图片
            self.setPixmap(pixmap_with_regions)
            
            # 调整控件大小以匹配图片
            self.resize(new_width, new_height)
            
        except Exception as e:
            print(f"更新显示时出错: {e}")
            import traceback
            traceback.print_exc()
            # 回退到显示原始图片
            self.setPixmap(self.original_pixmap)
    
    def get_region_class_id(self, region):
        """从区域数据中获取正确的类别ID"""
        try:
            final_label_index = region.get('final_label_index', 0)
            label_confidence = region.get('label_confidence', [])
            
            # 检查索引是否有效
            if 0 <= final_label_index < len(label_confidence):
                return label_confidence[final_label_index].get('label', 11)
            else:
                # 如果索引无效，返回默认值或第一个标签
                if label_confidence:
                    return label_confidence[0].get('label', 11)
                return 11  # 默认为"非缺陷"
        except (IndexError, TypeError):
            return 11  # 出错时返回默认值
    
    def draw_regions(self, pixmap):
        """在图片上绘制缺陷区域"""
        # 如果区域不可见，直接返回原图
        if not self.regions_visible or not self.regions or not self.class_manager:
            return pixmap
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for i, region in enumerate(self.regions):
            # 获取区域信息
            x = int(region.get('x', 0) * self.scale_factor)
            y = int(region.get('y', 0) * self.scale_factor)
            width = int(region.get('width', 0) * self.scale_factor)
            height = int(region.get('height', 0) * self.scale_factor)
            
            # 使用新的方法获取正确的类别ID
            class_id = self.get_region_class_id(region)
            
            # 获取修改状态
            modified_status = region.get('modified_status', 0)
            
            # 获取类别颜色
            color = self.class_manager.get_class_color(class_id)
            
            # 根据是否选中和修改状态调整边框样式
            is_selected = (i == self.selected_region_index)
            pen_width = 8 if is_selected else 3  # 选中区域边框显著加粗
            
            # 根据修改状态设置边框样式
            if modified_status == 1:
                # 已修改：使用虚线边框
                pen_style = Qt.PenStyle.DashLine
            elif modified_status == 2:
                # 已添加：使用点线边框
                pen_style = Qt.PenStyle.DotLine
            else:
                # 未修改：使用实线边框
                pen_style = Qt.PenStyle.SolidLine
            
            # 为选中的区域绘制双重边框效果
            if is_selected:
                # 外层边框：白色粗边框作为高亮
                outer_pen = QPen(QColor(255, 255, 255), pen_width + 2, pen_style)
                painter.setPen(outer_pen)
                painter.drawRect(x - 1, y - 1, width + 2, height + 2)
                
                # 内层边框：原色边框
                inner_pen = QPen(color, pen_width, pen_style)
                painter.setPen(inner_pen)
                painter.drawRect(x, y, width, height)
                
                # 添加选中标识：在左上角绘制一个小三角形
                triangle_size = 20
                triangle_points = [
                    QPoint(x, y),
                    QPoint(x + triangle_size, y),
                    QPoint(x, y + triangle_size)
                ]
                triangle_polygon = QPolygon(triangle_points)
                painter.setBrush(QBrush(QColor(255, 255, 0)))  # 黄色三角形
                painter.setPen(QPen(QColor(255, 255, 0), 2))
                painter.drawPolygon(triangle_polygon)
                painter.setBrush(QBrush())  # 清除画刷
            else:
                # 非选中区域：正常边框
                pen = QPen(color, pen_width, pen_style)
                painter.setPen(pen)
                painter.drawRect(x, y, width, height)
            
            # 绘制标签文本 - 只对非洁净度和非缺陷类别显示名称
            # 洁净度(10)和非缺陷(11)已经通过颜色区分，不需要显示名称
            if class_id not in [10, 11]:  # 不是洁净度和非缺陷
                painter.setPen(QPen(color, 2))  # 文本颜色与边框一致
                font = QFont()
                font.setPointSize(12)  # 固定字体大小
                font.setBold(True)
                painter.setFont(font)
                
                # 在标签文本中包含修改状态和选中状态
                status_suffix = ""
                if modified_status == 1:
                    status_suffix = " [修改]"
                elif modified_status == 2:
                    status_suffix = " [已添加]"
                
                # 为选中的区域添加特殊标识
                selection_prefix = "★ " if is_selected else ""
                
                text = f"{selection_prefix}{i+1}: {self.class_manager.get_class_name(class_id)}{status_suffix}"
                
                # 计算文本背景框大小
                text_metrics = painter.fontMetrics()
                text_rect = text_metrics.boundingRect(text)
                text_bg_rect = QRect(x, y-25, text_rect.width() + 10, text_rect.height() + 5)
                
                # 根据选中状态和修改状态设置背景色
                if is_selected:
                    bg_color = QColor(255, 255, 0, 230)  # 选中区域：亮黄色背景
                elif modified_status == 1:
                    bg_color = QColor(255, 255, 0, 200)  # 黄色背景表示已修改
                elif modified_status == 2:
                    bg_color = QColor(255, 165, 0, 200)  # 橙色背景表示已添加
                else:
                    bg_color = QColor(255, 255, 255, 200)  # 白色背景表示未修改
                
                # 绘制背景
                painter.fillRect(text_bg_rect, bg_color)
                
                # 为选中区域的文本添加边框
                if is_selected:
                    painter.setPen(QPen(QColor(0, 0, 0), 2))  # 黑色边框
                    painter.drawRect(text_bg_rect)
                
                # 绘制文本
                painter.setPen(QPen(color, 1))
                painter.drawText(text_bg_rect, Qt.AlignmentFlag.AlignCenter, text)
        
        # 绘制正在拖拽的临时矩形（如果在添加缺陷模式中）
        if self.add_defect_mode and self.drawing and not self.current_rect.isEmpty():
            # 使用虚线红色边框绘制临时矩形
            temp_pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(temp_pen)
            painter.drawRect(self.current_rect)
            
            # 在矩形中心显示大小信息
            center_x = self.current_rect.center().x()
            center_y = self.current_rect.center().y()
            size_text = f"{self.current_rect.width()}×{self.current_rect.height()}"
            
            # 设置文字样式
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            # 计算文字背景
            text_metrics = painter.fontMetrics()
            text_rect = text_metrics.boundingRect(size_text)
            text_bg_rect = QRect(
                center_x - text_rect.width()//2 - 5,
                center_y - text_rect.height()//2 - 2,
                text_rect.width() + 10,
                text_rect.height() + 4
            )
            
            # 绘制半透明背景
            painter.fillRect(text_bg_rect, QColor(255, 255, 255, 180))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawRect(text_bg_rect)
            
            # 绘制文字
            painter.setPen(QPen(QColor(255, 0, 0), 1))
            painter.drawText(text_bg_rect, Qt.AlignmentFlag.AlignCenter, size_text)
        
        painter.end()
        return pixmap
    
    def set_selected_region(self, region_index):
        """设置选中的区域"""
        self.selected_region_index = region_index
        self.update_display()
    
    def focus_on_region(self, region_index):
        """聚焦到指定区域：重置缩放到100%并移动到区域位置"""
        print(f"聚焦到区域 {region_index}")
        
        if 0 <= region_index < len(self.regions):
            # 1. 重置缩放到100%
            self.zoom_factor = 1.0
            self.selected_region_index = region_index
            self.update_display()
            
            # 更新缩放标签
            if hasattr(self, 'parent_dialog') and hasattr(self.parent_dialog, 'update_zoom_label'):
                self.parent_dialog.update_zoom_label()
            
            # 2. 使用QTimer延迟执行滚动，确保图片已经重新绘制
            QTimer.singleShot(100, lambda: self._scroll_to_region_center(region_index))
    
    def _scroll_to_region_center(self, region_index):
        """滚动到区域中心位置"""
        if 0 <= region_index < len(self.regions):
            # 获取区域的原始坐标（100%缩放下）
            region = self.regions[region_index]
            x = int(region.get('x', 0) * self.scale_factor)
            y = int(region.get('y', 0) * self.scale_factor)
            width = int(region.get('width', 0) * self.scale_factor)
            height = int(region.get('height', 0) * self.scale_factor)
            
            # 计算区域中心点
            center_x = x + width // 2
            center_y = y + height // 2
            
            print(f"区域中心坐标: ({center_x}, {center_y})")
            
            # 寻找滚动区域并滚动到中心
            widget = self
            while widget:
                parent = widget.parent()
                if parent and isinstance(parent, QScrollArea):
                    print("找到滚动区域，移动到区域中心")
                    
                    # 获取视窗大小
                    viewport = parent.viewport()
                    viewport_width = viewport.width()
                    viewport_height = viewport.height()
                    
                    # 计算滚动位置，使区域中心位于视窗中心
                    target_x = max(0, center_x - viewport_width // 2)
                    target_y = max(0, center_y - viewport_height // 2)
                    
                    # 获取滚动条
                    h_scrollbar = parent.horizontalScrollBar()
                    v_scrollbar = parent.verticalScrollBar()
                    
                    # 设置滚动位置
                    if h_scrollbar:
                        max_h = h_scrollbar.maximum()
                        target_x = min(target_x, max_h)
                        h_scrollbar.setValue(target_x)
                        print(f"水平滚动到: {target_x}")
                    
                    if v_scrollbar:
                        max_v = v_scrollbar.maximum()
                        target_y = min(target_y, max_v)
                        v_scrollbar.setValue(target_y)
                        print(f"垂直滚动到: {target_y}")
                    
                    break
                widget = parent
            else:
                print("未找到滚动区域")
    
    def set_scroll_area(self, scroll_area):
        """设置滚动区域的引用，用于拖动移动"""
        self.scroll_area = scroll_area
    
    def set_add_defect_mode(self, enabled):
        """设置添加缺陷模式"""
        self.add_defect_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)  # 设置十字光标
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)  # 恢复正常光标
            self.drawing = False
            self.update_display()  # 刷新显示以清除临时绘制的矩形
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        click_pos = event.position().toPoint()
        
        if event.button() == Qt.MouseButton.RightButton and self.add_defect_mode:
            # 右键拖拽添加缺陷模式
            self.drawing = True
            self.start_point = click_pos
            self.end_point = click_pos
            self.current_rect = QRect()
        elif event.button() == Qt.MouseButton.LeftButton:
            # 左键处理：记录起始点，等待判断是点击还是拖动
            self.pan_start_point = click_pos
            self.panning = False  # 初始化为false，等待移动判断
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        current_pos = event.position().toPoint()
        
        if self.drawing and self.add_defect_mode:
            # 添加缺陷模式下的拖拽
            self.end_point = current_pos
            # 计算当前矩形
            self.current_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()  # 重绘界面
        elif event.buttons() & Qt.MouseButton.LeftButton:
            # 左键拖动处理
            if not self.panning:
                # 检查是否超过点击阈值，如果是则开始拖动
                distance = (current_pos - self.pan_start_point).manhattanLength()
                if distance > self.click_threshold:
                    self.panning = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
            
            if self.panning and self.scroll_area:
                # 计算移动偏移量
                delta = current_pos - self.pan_start_point
                
                # 获取当前滚动条位置
                h_scroll = self.scroll_area.horizontalScrollBar()
                v_scroll = self.scroll_area.verticalScrollBar()
                
                # 移动滚动条（注意方向相反）
                h_scroll.setValue(h_scroll.value() - delta.x())
                v_scroll.setValue(v_scroll.value() - delta.y())
                
                # 更新起始点
                self.pan_start_point = current_pos
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.MouseButton.RightButton and self.drawing and self.add_defect_mode:
            self.drawing = False
            self.end_point = event.position().toPoint()
            
            # 计算最终矩形
            final_rect = QRect(self.start_point, self.end_point).normalized()
            
            # 检查矩形大小是否合理（至少10x10像素）
            if final_rect.width() >= 10 and final_rect.height() >= 10:
                # 发送新区域创建信号
                self.new_region_created.emit(
                    final_rect.x(), 
                    final_rect.y(), 
                    final_rect.width(), 
                    final_rect.height()
                )
            
            # 清除临时矩形
            self.current_rect = QRect()
            self.update()
        elif event.button() == Qt.MouseButton.LeftButton:
            # 左键释放处理
            if self.panning:
                # 结束拖动
                self.panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                # 这是一个点击操作，处理区域选择
                if self.regions:
                    click_pos = event.position().toPoint()
                    region_found = False
                    # 查找被点击的区域
                    for i, region in enumerate(self.regions):
                        x = int(region.get('x', 0) * self.scale_factor)
                        y = int(region.get('y', 0) * self.scale_factor)
                        width = int(region.get('width', 0) * self.scale_factor)
                        height = int(region.get('height', 0) * self.scale_factor)
                        
                        if (x <= click_pos.x() <= x + width and 
                            y <= click_pos.y() <= y + height):
                            self.region_clicked.emit(i)
                            region_found = True
                            break
                    
                    # 如果没有点击到任何区域，取消选中
                    if not region_found:
                        self.region_unselected.emit()
                else:
                    # 没有区域时，直接取消选中
                    self.region_unselected.emit()
        
        super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event):
        """处理窗口大小改变事件"""
        super().resizeEvent(event)
        # 移除自动更新显示，避免不必要的重复缩放
    
    def wheelEvent(self, event):
        """处理鼠标滚轮事件进行缩放，以鼠标位置为中心"""
        if self.original_pixmap and self.scroll_area:
            # 获取鼠标在ImageLabel上的位置
            mouse_pos = event.position().toPoint()
            
            # 获取滚动条当前值
            h_scrollbar = self.scroll_area.horizontalScrollBar()
            v_scrollbar = self.scroll_area.verticalScrollBar()
            old_h_value = h_scrollbar.value()
            old_v_value = v_scrollbar.value()
            
            # 计算鼠标在完整图片中的绝对坐标
            old_size = self.size()
            mouse_x_in_image = mouse_pos.x()
            mouse_y_in_image = mouse_pos.y()
            
            # 计算鼠标在图片中的相对位置（0-1之间）
            if old_size.width() > 0 and old_size.height() > 0:
                rel_x = mouse_x_in_image / old_size.width()
                rel_y = mouse_y_in_image / old_size.height()
            else:
                rel_x = 0.5
                rel_y = 0.5
            
            # 保存旧的缩放因子
            old_zoom_factor = self.zoom_factor
            
            # 获取滚轮滚动方向并调整缩放
            delta = event.angleDelta().y()
            zoom_step = 0.1
            
            if delta > 0:
                # 向上滚动，放大
                self.zoom_factor *= (1 + zoom_step)
            else:
                # 向下滚动，缩小
                self.zoom_factor *= (1 - zoom_step)
            
            # 限制缩放范围
            self.zoom_factor = max(0.1, min(5.0, self.zoom_factor))
            
            # 如果缩放因子没有实际改变，直接返回
            if abs(self.zoom_factor - old_zoom_factor) < 0.001:
                return
            
            # 更新显示
            self.update_display()
            
            # 计算缩放后鼠标应该在图片中的新位置
            new_size = self.size()
            new_mouse_x_in_image = rel_x * new_size.width()
            new_mouse_y_in_image = rel_y * new_size.height()
            
            # 计算需要调整的滚动量，使鼠标位置保持在视窗中的相同位置
            scroll_adjust_x = new_mouse_x_in_image - mouse_x_in_image
            scroll_adjust_y = new_mouse_y_in_image - mouse_y_in_image
            
            # 设置新的滚动位置
            new_h_value = old_h_value + scroll_adjust_x
            new_v_value = old_v_value + scroll_adjust_y
            
            h_scrollbar.setValue(int(new_h_value))
            v_scrollbar.setValue(int(new_v_value))
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if self.original_pixmap:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                # + 键放大 - 如果有父窗口且支持缩放方法，使用父窗口的方法
                if hasattr(self, 'parent_dialog') and hasattr(self.parent_dialog, 'zoom_in'):
                    self.parent_dialog.zoom_in()
                else:
                    # 回退到简单缩放
                    self.zoom_factor *= 1.1
                    self.zoom_factor = min(5.0, self.zoom_factor)
                    self.update_display()
            elif event.key() == Qt.Key.Key_Minus:
                # - 键缩小
                if hasattr(self, 'parent_dialog') and hasattr(self.parent_dialog, 'zoom_out'):
                    self.parent_dialog.zoom_out()
                else:
                    # 回退到简单缩放
                    self.zoom_factor *= 0.9
                    self.zoom_factor = max(0.1, self.zoom_factor)
                    self.update_display()
            elif event.key() == Qt.Key.Key_0:
                # 0 键重置缩放
                if hasattr(self, 'parent_dialog') and hasattr(self.parent_dialog, 'zoom_reset'):
                    self.parent_dialog.zoom_reset()
                else:
                    # 回退到简单缩放
                    self.zoom_factor = 1.0
                    self.update_display()
        
        super().keyPressEvent(event)
    
    def paintEvent(self, event):
        """重写绘制事件，显示正在拖拽的矩形"""
        super().paintEvent(event)
        
        # 如果在添加缺陷模式中且正在拖拽，绘制临时矩形
        if self.add_defect_mode and self.drawing and not self.current_rect.isEmpty():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 设置虚线红色边框
            pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            # 绘制矩形
            painter.drawRect(self.current_rect)
            
            # 在矩形中心显示大小信息
            if self.current_rect.width() > 20 and self.current_rect.height() > 20:
                center_x = self.current_rect.center().x()
                center_y = self.current_rect.center().y()
                size_text = f"{self.current_rect.width()}×{self.current_rect.height()}"
                
                # 设置文字样式
                font = QFont()
                font.setPointSize(10)
                font.setBold(True)
                painter.setFont(font)
                
                # 计算文字背景
                text_metrics = painter.fontMetrics()
                text_rect = text_metrics.boundingRect(size_text)
                text_bg_rect = QRect(
                    center_x - text_rect.width()//2 - 5,
                    center_y - text_rect.height()//2 - 2,
                    text_rect.width() + 10,
                    text_rect.height() + 4
                )
                
                # 绘制半透明白色背景
                painter.fillRect(text_bg_rect, QColor(255, 255, 255, 180))
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.drawRect(text_bg_rect)
                
                # 绘制文字
                painter.setPen(QPen(QColor(255, 0, 0), 1))
                painter.drawText(text_bg_rect, Qt.AlignmentFlag.AlignCenter, size_text)
            
            painter.end()

class DetailDialog(QWidget):
    """详细标注界面"""
    def __init__(self, button, actual_img_path, parent=None):
        super().__init__(parent)  # 设置正确的父窗口
        self.button = button
        self.actual_img_path = actual_img_path
        self.current_region_index = -1
        self.regions_modified = False
        self.parent_app = parent  # 保存父应用的引用
        self.regions_visible = True  # 区域框是否可见，默认为True
        self.add_defect_mode = False  # 添加缺陷模式标志
        
        # 初始化类别管理器，使用相对路径
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            classes_file = os.path.join(script_dir, 'classes.txt')
            self.class_manager = ClassManager(classes_file)
            print(f"成功加载类别管理器，文件路径: {classes_file}")
        except Exception as e:
            print(f"警告：加载类别文件失败: {e}")
            self.class_manager = ClassManager()  # 使用默认类别
        
        self.init_ui()
        
        # 如果有区域，自动选择第一个
        if self.button.regions:
            self.on_region_clicked(0)
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.focus_on_region(0)
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"标注界面 - {self.button.button_name}")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置窗口属性，确保窗口正确显示
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # 主布局
        main_layout = QHBoxLayout(self)
        
        # 左侧图片显示区域
        self.create_image_area(main_layout)
        
        # 右侧控制面板
        self.create_control_panel(main_layout)
        
        # 设置布局比例
        main_layout.setStretch(0, 3)  # 图片区域占3/4
        main_layout.setStretch(1, 1)  # 控制面板占1/4
        
        # 初始化导航按钮状态
        self.update_navigation_buttons()
    
    def create_image_area(self, main_layout):
        """创建图片显示区域"""
        try:
            image_frame = QFrame()
            image_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            image_layout = QVBoxLayout(image_frame)
            
            # 缩放控制按钮
            zoom_layout = QHBoxLayout()
            zoom_in_btn = QPushButton("放大 (+)")
            zoom_in_btn.clicked.connect(self.zoom_in)
            zoom_out_btn = QPushButton("缩小 (-)")
            zoom_out_btn.clicked.connect(self.zoom_out)
            zoom_reset_btn = QPushButton("重置 (0)")
            zoom_reset_btn.clicked.connect(self.zoom_reset)
            
            # 添加切换区域框显示的按钮
            self.toggle_regions_btn = QPushButton("隐藏区域框")
            self.toggle_regions_btn.clicked.connect(self.toggle_regions_visibility)
            self.toggle_regions_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
            
            self.zoom_label = QLabel("缩放: 100%")
            
            # 添加使用说明
            help_label = QLabel("提示: 鼠标滚轮缩放，+/- 键缩放，0 键重置，左键拖动移动图片")
            help_label.setStyleSheet("color: gray; font-size: 10px;")
            
            zoom_layout.addWidget(zoom_in_btn)
            zoom_layout.addWidget(zoom_out_btn)
            zoom_layout.addWidget(zoom_reset_btn)
            zoom_layout.addWidget(self.toggle_regions_btn)  # 添加切换按钮
            zoom_layout.addWidget(self.zoom_label)
            zoom_layout.addStretch()
            zoom_layout.addWidget(help_label)
            
            image_layout.addLayout(zoom_layout)
            
            # 检查图片路径是否存在
            if not self.actual_img_path or not os.path.exists(self.actual_img_path):
                # 显示占位符
                placeholder_label = QLabel(f"图片不存在: {self.actual_img_path}")
                placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                image_layout.addWidget(placeholder_label)
                main_layout.addWidget(image_frame)
                return
            
            # 图片标签
            self.image_label = ImageLabel()
            self.image_label.region_clicked.connect(self.on_region_clicked)
            self.image_label.new_region_created.connect(self.add_new_defect_region)
            self.image_label.region_unselected.connect(self.on_region_unselected)
            
            # 设置DetailDialog的引用，方便更新缩放标签
            self.image_label.parent_dialog = self
            
            # 设置区域框的初始可见性
            self.image_label.regions_visible = self.regions_visible
            
            # 设置图片和区域
            self.image_label.set_image_and_regions(
                self.actual_img_path, 
                self.button.regions, 
                self.class_manager
            )
            
            # 滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidget(self.image_label)
            scroll_area.setWidgetResizable(False)  # 改为False，让图片保持真实大小
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setMinimumSize(600, 400)
            
            # 设置滚动区域引用，用于拖动移动
            self.image_label.set_scroll_area(scroll_area)
            
            image_layout.addWidget(scroll_area)
            main_layout.addWidget(image_frame)
            
        except Exception as e:
            print(f"创建图片区域时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 显示错误信息
            error_label = QLabel(f"创建图片区域时出错: {str(e)}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            main_layout.addWidget(error_label)
    
    def create_control_panel(self, main_layout):
        """创建控制面板"""
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 基本信息组
        self.create_basic_info_group(control_layout)
        
        # 区域列表组
        self.create_region_list_group(control_layout)
        
        # 区域导航组
        self.create_region_navigation_group(control_layout)
        
        # 当前选中区域编辑组
        self.create_region_edit_group(control_layout)
        
        # 操作按钮组
        self.create_action_buttons(control_layout)
        
        control_layout.addStretch()
        main_layout.addWidget(control_widget)
    
    def create_basic_info_group(self, parent_layout):
        """创建基本信息组"""
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout(info_group)
        
        # 基本信息
        info_text = f"按钮: {self.button.button_name}\n"
        info_text += f"列号: {self.button.column}\n"
        info_text += f"索引: {self.button.index}\n"
        info_text += f"缺陷区域: {len(self.button.regions)} 个"
        
        self.basic_info_label = QLabel(info_text)
        info_layout.addWidget(self.basic_info_label)
        
        # 类别统计信息
        self.class_stats_label = QLabel()
        self.class_stats_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 5px; border: 1px solid #ddd; }")
        self.update_class_statistics()
        info_layout.addWidget(self.class_stats_label)
        
        parent_layout.addWidget(info_group)
    
    def create_region_list_group(self, parent_layout):
        """创建区域列表组"""
        list_group = QGroupBox("缺陷区域列表")
        list_layout = QVBoxLayout(list_group)
        
        # 添加说明标签
        instruction_label = QLabel("点击列表项或图片中的区域来选择")
        instruction_label.setStyleSheet("color: gray; font-size: 10px;")
        list_layout.addWidget(instruction_label)
        
        # 添加修改状态的视觉说明
        status_legend = QLabel("颜色说明：白色=未修改，黄色=已修改，橙色=已添加")
        status_legend.setStyleSheet("color: gray; font-size: 9px; font-style: italic;")
        list_layout.addWidget(status_legend)
        
        # 区域列表 - 使用QListWidget而不是QTextEdit
        self.region_list_widget = QListWidget()
        self.region_list_widget.setMaximumHeight(150)
        self.region_list_widget.itemClicked.connect(self.on_region_list_item_clicked)
        self.update_region_list()
        
        list_layout.addWidget(self.region_list_widget)
        parent_layout.addWidget(list_group)
    
    def create_region_navigation_group(self, parent_layout):
        """创建区域导航组"""
        nav_group = QGroupBox("区域导航")
        nav_layout = QVBoxLayout(nav_group)
        
        # 导航按钮布局
        nav_button_layout = QHBoxLayout()
        
        # 上一个区域按钮
        self.prev_region_btn = QPushButton("上一个 (←)")
        self.prev_region_btn.clicked.connect(self.go_to_previous_region)
        self.prev_region_btn.setEnabled(False)
        nav_button_layout.addWidget(self.prev_region_btn)
        
        # 下一个区域按钮  
        self.next_region_btn = QPushButton("下一个 (→)")
        self.next_region_btn.clicked.connect(self.go_to_next_region)
        self.next_region_btn.setEnabled(False)
        nav_button_layout.addWidget(self.next_region_btn)
        
        # 添加快速确认按钮
        self.quick_confirm_btn = QPushButton("确认当前区域 (空格)")
        self.quick_confirm_btn.clicked.connect(self.quick_confirm_current_region)
        self.quick_confirm_btn.setEnabled(False)
        self.quick_confirm_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        nav_button_layout.addWidget(self.quick_confirm_btn)

        nav_layout.addLayout(nav_button_layout)
        
        # 添加快捷键提示
        shortcut_label = QLabel("快捷键: ←/→ 方向键导航, 空格键快速确认, Delete键删除, H键隐藏/显示区域框, 右键拖拽添加缺陷, 左键拖动移动图片")
        shortcut_label.setStyleSheet("color: gray; font-size: 9px;")
        nav_layout.addWidget(shortcut_label)
        
        parent_layout.addWidget(nav_group)
    
    def create_region_edit_group(self, parent_layout):
        """创建区域编辑组"""
        edit_group = QGroupBox("编辑选中区域")
        edit_layout = QVBoxLayout(edit_group)
        
        # 当前选中区域信息
        self.current_region_label = QLabel("请点击图片中的区域进行选择")
        edit_layout.addWidget(self.current_region_label)
        
        # 类别选择
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("类别:"))
        
        self.class_combo = QComboBox()
        for class_id, class_name in self.class_manager.get_all_classes().items():
            self.class_combo.addItem(f"{class_id}: {class_name}", class_id)
        self.class_combo.currentTextChanged.connect(self.on_class_changed)
        class_layout.addWidget(self.class_combo)
        
        edit_layout.addLayout(class_layout)
        
        # 修改状态
        modify_layout = QHBoxLayout()
        modify_layout.addWidget(QLabel("修改状态:"))
        self.modify_spin = QSpinBox()
        self.modify_spin.setRange(0, 2)
        self.modify_spin.valueChanged.connect(self.on_modify_changed)
        modify_layout.addWidget(self.modify_spin)
        
        # 添加修改状态说明
        status_help = QLabel("(0:未修改, 1:已修改, 2:已添加)")
        status_help.setStyleSheet("color: gray; font-size: 10px;")
        modify_layout.addWidget(status_help)
        
        edit_layout.addLayout(modify_layout)
        
        # 大小信息（只读）
        pos_group = QGroupBox("大小信息")
        pos_layout = QGridLayout(pos_group)
        
        pos_layout.addWidget(QLabel("宽度(mm):"), 0, 0)
        self.width_label = QLabel("0")
        pos_layout.addWidget(self.width_label, 0, 1)
        
        pos_layout.addWidget(QLabel("高度(mm):"), 0, 2)
        self.height_label = QLabel("0")
        pos_layout.addWidget(self.height_label, 0, 3)
        
        edit_layout.addWidget(pos_group)
        
        # 置信度信息
        conf_group = QGroupBox("置信度信息")
        conf_layout = QVBoxLayout(conf_group)
        self.confidence_text = QTextEdit()
        self.confidence_text.setMaximumHeight(100)
        self.confidence_text.setReadOnly(True)
        conf_layout.addWidget(self.confidence_text)
        edit_layout.addWidget(conf_group)
        
        parent_layout.addWidget(edit_group)
    
    def create_action_buttons(self, parent_layout):
        """创建操作按钮"""
        button_layout = QVBoxLayout()
        
        # 第一行按钮
        first_row_layout = QHBoxLayout()
        
        # 添加缺陷按钮
        self.add_defect_btn = QPushButton("添加缺陷")
        self.add_defect_btn.clicked.connect(self.toggle_add_defect_mode)
        self.add_defect_btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; }")
        first_row_layout.addWidget(self.add_defect_btn)
        
        # 删除区域按钮
        self.delete_region_btn = QPushButton("删除选中区域")
        self.delete_region_btn.clicked.connect(self.delete_current_region)
        self.delete_region_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_region_btn.setEnabled(False)  # 初始禁用
        first_row_layout.addWidget(self.delete_region_btn)
        
        button_layout.addLayout(first_row_layout)
        
        # 第二行按钮
        second_row_layout = QHBoxLayout()
        
        # 保存按钮
        save_btn = QPushButton("保存修改")
        save_btn.clicked.connect(self.save_changes)
        save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        second_row_layout.addWidget(save_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        second_row_layout.addWidget(cancel_btn)
        
        button_layout.addLayout(second_row_layout)
        
        # 添加提示标签
        self.add_defect_hint = QLabel("提示: 点击'添加缺陷'后，在图片上右键拖拽框选区域")
        self.add_defect_hint.setStyleSheet("color: gray; font-size: 10px; font-style: italic;")
        self.add_defect_hint.setVisible(False)
        button_layout.addWidget(self.add_defect_hint)
        
        parent_layout.addLayout(button_layout)
    
    def get_region_class_id(self, region):
        """从区域数据中获取正确的类别ID"""
        try:
            final_label_index = region.get('final_label_index', 0)
            label_confidence = region.get('label_confidence', [])
            
            # 检查索引是否有效
            if 0 <= final_label_index < len(label_confidence):
                return label_confidence[final_label_index].get('label', 11)
            else:
                # 如果索引无效，返回默认值或第一个标签
                if label_confidence:
                    return label_confidence[0].get('label', 11)
                return 11  # 默认为"非缺陷"
        except (IndexError, TypeError):
            return 11  # 出错时返回默认值
    
    def update_class_statistics(self):
        """更新类别统计信息"""
        if not self.button.regions:
            self.class_stats_label.setText("无区域数据")
            return
        
        # 统计各个类别的数量
        class_counts = {}
        modified_counts = {"未修改": 0, "已修改": 0, "已添加": 0}
        
        for region in self.button.regions:
            # 统计类别
            class_id = self.get_region_class_id(region)
            class_name = self.class_manager.get_class_name(class_id)
            
            if class_name in class_counts:
                class_counts[class_name] += 1
            else:
                class_counts[class_name] = 1
            
            # 统计修改状态
            modified_status = region.get('modified_status', 0)
            if modified_status == 0:
                modified_counts["未修改"] += 1
            elif modified_status == 1:
                modified_counts["已修改"] += 1
            elif modified_status == 2:
                modified_counts["已添加"] += 1
        
        # 构建显示文本
        stats_text = "类别统计:\n"
        for class_name, count in sorted(class_counts.items()):
            stats_text += f"  {class_name}: {count} 个\n"
        
        stats_text += "\n修改状态统计:\n"
        for status, count in modified_counts.items():
            stats_text += f"  {status}: {count} 个\n"
        
        self.class_stats_label.setText(stats_text.strip())
    
    def update_region_list(self):
        """更新区域列表显示"""
        self.region_list_widget.clear()
        
        for i, region in enumerate(self.button.regions):
            class_id = self.get_region_class_id(region)
            class_name = self.class_manager.get_class_name(class_id)
            
            # 获取修改状态
            modified_status = region.get('modified_status', 0)
            status_text = ""
            if modified_status == 1:
                status_text = " [已修改]"
            elif modified_status == 2:
                status_text = " [已添加]"
            
            # 创建列表项，包含修改状态
            item_text = f"区域 {i+1}: {class_name}{status_text}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # 存储区域索引
            
            # 根据类别和修改状态设置颜色
            color = self.class_manager.get_class_color(class_id)
            
            # 如果有修改状态，调整背景色
            if modified_status == 1:
                # 已修改：使用黄色调
                item.setBackground(QColor(255, 255, 0, 100))  # 浅黄色背景
            elif modified_status == 2:
                # 已添加：使用橙色调
                item.setBackground(QColor(255, 165, 0, 100))  # 浅橙色背景
            else:
                # 未修改：使用原来的类别颜色
                item.setBackground(QColor(color.red(), color.green(), color.blue(), 50))  # 浅色背景
            
            self.region_list_widget.addItem(item)
        
        # 更新导航按钮状态
        self.update_navigation_buttons()
    
    def on_region_list_item_clicked(self, item):
        """处理区域列表项点击事件"""
        region_index = item.data(Qt.ItemDataRole.UserRole)
        if region_index is not None:
            self.on_region_clicked(region_index)
            # 聚焦到对应区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.focus_on_region(region_index)
    
    def on_region_clicked(self, region_index):
        """处理区域点击事件"""
        self.current_region_index = region_index
        if 0 <= region_index < len(self.button.regions):
            region = self.button.regions[region_index]
            self.load_region_data(region)
            self.current_region_label.setText(f"当前选中: 区域 {region_index + 1}")
            
            # 启用删除按钮
            if hasattr(self, 'delete_region_btn'):
                self.delete_region_btn.setEnabled(True)
            
            # 高亮显示选中的区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.set_selected_region(region_index)
            
            # 高亮显示列表中的项
            if hasattr(self, 'region_list_widget'):
                self.region_list_widget.setCurrentRow(region_index)
            
            # 更新导航按钮状态
            self.update_navigation_buttons()
    
    def on_region_unselected(self):
        """处理取消选中区域事件"""
        self.current_region_index = -1
        self.current_region_label.setText("请点击图片中的区域进行选择")
        
        # 禁用删除按钮
        if hasattr(self, 'delete_region_btn'):
            self.delete_region_btn.setEnabled(False)
        
        # 取消高亮显示选中的区域
        if hasattr(self, 'image_label') and self.image_label:
            self.image_label.set_selected_region(-1)
        
        # 取消列表中的选中项
        if hasattr(self, 'region_list_widget'):
            self.region_list_widget.clearSelection()
        
        # 清空编辑控件
        self.clear_edit_controls()
        
        # 更新导航按钮状态
        self.update_navigation_buttons()
    
    def clear_edit_controls(self):
        """清空编辑控件"""
        # 重置类别选择
        if hasattr(self, 'class_combo'):
            self.class_combo.setCurrentIndex(0)
        
        # 重置修改状态
        if hasattr(self, 'modify_spin'):
            self.modify_spin.setValue(0)
        
        # 清空大小信息
        if hasattr(self, 'width_label') and hasattr(self, 'height_label'):
            self.width_label.setText("0")
            self.height_label.setText("0")
        
        # 清空置信度信息
        if hasattr(self, 'confidence_text'):
            self.confidence_text.setPlainText("")
    
    def update_navigation_buttons(self):
        """更新导航按钮的状态"""
        if hasattr(self, 'prev_region_btn') and hasattr(self, 'next_region_btn'):
            total_regions = len(self.button.regions)
            current_index = self.current_region_index
            
            # 上一个按钮：当前不是第一个区域时启用
            self.prev_region_btn.setEnabled(current_index > 0)
            
            # 下一个按钮：当前不是最后一个区域时启用
            self.next_region_btn.setEnabled(current_index < total_regions - 1 and total_regions > 0)
            
            # 快速确认按钮：有选中区域时启用
            self.quick_confirm_btn.setEnabled(current_index >= 0)
            
            # 删除按钮：有选中区域时启用
            if hasattr(self, 'delete_region_btn'):
                self.delete_region_btn.setEnabled(current_index >= 0)

            # 更新按钮文本显示当前位置
            if total_regions > 0 and current_index >= 0:
                self.prev_region_btn.setText(f"上一个 (←) {current_index}/{total_regions}")
                self.next_region_btn.setText(f"下一个 (→) {current_index + 2}/{total_regions}")
            else:
                self.prev_region_btn.setText("上一个 (←)")
                self.next_region_btn.setText("下一个 (→)")
    
    def go_to_previous_region(self):
        """跳转到上一个区域"""
        if self.current_region_index > 0:
            new_index = self.current_region_index - 1
            self.on_region_clicked(new_index)
            # 聚焦到对应区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.focus_on_region(new_index)
    
    def go_to_next_region(self):
        """跳转到下一个区域"""
        if self.current_region_index < len(self.button.regions) - 1:
            new_index = self.current_region_index + 1
            self.on_region_clicked(new_index)
            # 聚焦到对应区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.focus_on_region(new_index)
    
    def delete_current_region(self):
        """删除当前选中的区域"""
        if self.current_region_index < 0 or self.current_region_index >= len(self.button.regions):
            QMessageBox.warning(self, "删除失败", "请先选择要删除的区域")
            return
        
        # 确认删除
        region = self.button.regions[self.current_region_index]
        class_id = self.get_region_class_id(region)
        class_name = self.class_manager.get_class_name(class_id)
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除区域 {self.current_region_index + 1}: {class_name} 吗？\n\n"
            "注意：删除后需要保存才能永久生效。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # 删除区域
            deleted_region = self.button.regions.pop(self.current_region_index)
            self.regions_modified = True
            
            # 更新界面
            self.update_region_list()
            self.update_class_statistics()
            self.update_basic_info()
            
            # 重新设置图片和区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.set_image_and_regions(
                    self.actual_img_path, 
                    self.button.regions, 
                    self.class_manager
                )
            
            # 选择新的区域（如果还有区域的话）
            if self.button.regions:
                if self.current_region_index >= len(self.button.regions):
                    # 如果删除的是最后一个区域，选择新的最后一个
                    new_index = len(self.button.regions) - 1
                else:
                    # 保持当前索引，选择下一个区域
                    new_index = self.current_region_index
                
                self.on_region_clicked(new_index)
                if hasattr(self, 'image_label') and self.image_label:
                    self.image_label.focus_on_region(new_index)
            else:
                # 如果没有区域了，清空选择
                self.current_region_index = -1
                self.current_region_label.setText("所有区域已删除")
                self.delete_region_btn.setEnabled(False)
                self.quick_confirm_btn.setEnabled(False)
                
                # 清空编辑控件
                self.class_combo.setCurrentIndex(0)
                self.modify_spin.setValue(0)
                self.width_label.setText("0")
                self.height_label.setText("0")
                self.confidence_text.clear()
            
            # 更新导航按钮状态
            self.update_navigation_buttons()
            
            QMessageBox.information(self, "删除成功", f"区域 {class_name} 已删除")
            
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除区域时发生错误：\n{str(e)}")
            print(f"删除区域错误: {e}")
            import traceback
            traceback.print_exc()

    def toggle_add_defect_mode(self):
        """切换添加缺陷模式"""
        self.add_defect_mode = not self.add_defect_mode
        
        if self.add_defect_mode:
            self.add_defect_btn.setText("退出添加模式")
            self.add_defect_btn.setStyleSheet("QPushButton { background-color: #795548; color: white; }")
            self.add_defect_hint.setVisible(True)
            # 设置图片标签为添加模式
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.set_add_defect_mode(True)
        else:
            self.add_defect_btn.setText("添加缺陷")
            self.add_defect_btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; }")
            self.add_defect_hint.setVisible(False)
            # 退出添加模式
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.set_add_defect_mode(False)

    def add_new_defect_region(self, x, y, width, height):
        """添加新的缺陷区域"""
        try:
            # 将屏幕坐标转换为原始图片坐标
            if hasattr(self, 'image_label') and self.image_label:
                original_x = int(x / self.image_label.scale_factor)
                original_y = int(y / self.image_label.scale_factor)
                original_width = int(width / self.image_label.scale_factor)
                original_height = int(height / self.image_label.scale_factor)
            else:
                original_x, original_y = x, y
                original_width, original_height = width, height
            
            # 创建新的区域字典
            new_region = {
                "final_label_index": 1,  # 设为1
                "height": original_height,
                "imgPath": "",  # 设为空字符串
                "isSure": True,  # 设为True
                "label_confidence": [
                    {
                        "confidence": 1.0,
                        "label": 11  # 非缺陷
                    },
                    {
                        "confidence": 1.0,
                        "label": 1  # 用户可以设置的标签，默认为1（大糙）
                    },
                    {
                        "confidence": 1.0,
                        "label": 11  # 保持一致性
                    },
                    {
                        "confidence": 1.0,
                        "label": 11  # 保持一致性
                    }
                ],
                "modified_status": 2,  # 设为2，表示人工添加
                "width": original_width,
                "x": original_x,
                "y": original_y,
                "yolo_confidence": 0.0  # 设为0.0
            }
            
            # 添加到区域列表
            self.button.regions.append(new_region)
            self.regions_modified = True
            
            # 更新界面
            self.update_region_list()
            self.update_class_statistics()
            self.update_basic_info()
            
            # 重新设置图片和区域
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.set_image_and_regions(
                    self.actual_img_path, 
                    self.button.regions, 
                    self.class_manager
                )
            
            # 选择新添加的区域
            new_index = len(self.button.regions) - 1
            self.on_region_clicked(new_index)
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.focus_on_region(new_index)
            
            # 退出添加模式
            self.toggle_add_defect_mode()
            
            QMessageBox.information(self, "添加成功", "新的缺陷区域已添加！\n请在右侧面板设置正确的类别。")
            
        except Exception as e:
            QMessageBox.critical(self, "添加失败", f"添加缺陷区域时发生错误：\n{str(e)}")
            print(f"添加缺陷区域错误: {e}")
            import traceback
            traceback.print_exc()

    def update_basic_info(self):
        """更新基本信息显示"""
        info_text = f"按钮: {self.button.button_name}\n"
        info_text += f"列号: {self.button.column}\n"
        info_text += f"索引: {self.button.index}\n"
        info_text += f"缺陷区域: {len(self.button.regions)} 个"
        
        self.basic_info_label.setText(info_text)

    def quick_confirm_current_region(self):
        """快速确认当前区域（设置为已修改状态）"""
        if self.current_region_index >= 0 and self.current_region_index < len(self.button.regions):
            region = self.button.regions[self.current_region_index]
            
            # 只有在不是人工添加的区域时才设置为已修改状态
            if region.get('modified_status', 0) != 2:
                region['modified_status'] = 1
                self.regions_modified = True
                
                # 更新界面显示
                self.modify_spin.setValue(1)
                self.update_region_list()
                if hasattr(self, 'image_label') and self.image_label:
                    self.image_label.update_display()
            
            # 自动跳转到下一个区域（如果有的话）
            if self.current_region_index < len(self.button.regions) - 1:
                self.go_to_next_region()
            else:
                # 如果是最后一个区域，显示完成提示
                QMessageBox.information(self, "完成", "已确认所有区域！")
    
    def load_region_data(self, region):
        """加载区域数据到编辑控件"""
        # 获取正确的类别ID
        class_id = self.get_region_class_id(region)
        
        # 设置类别（使用标志防止触发on_class_changed）
        self._updating_class_selection = True
        for i in range(self.class_combo.count()):
            if self.class_combo.itemData(i) == class_id:
                self.class_combo.setCurrentIndex(i)
                break
        delattr(self, '_updating_class_selection')
        
        
        # 设置修改状态（使用标志防止触发on_modify_changed）
        self._updating_modify_status = True
        self.modify_spin.setValue(region.get('modified_status', 0))
        delattr(self, '_updating_modify_status')
        
        # 设置大小信息（转换为毫米）
        width_pixels = region.get('width', 0)
        height_pixels = region.get('height', 0)
        width_mm = width_pixels * PER_PIXEL_MM
        height_mm = height_pixels * PER_PIXEL_MM
        
        self.width_label.setText(f"{width_mm:.2f}")
        self.height_label.setText(f"{height_mm:.2f}")
        
        # 设置置信度信息
        conf_text = f"YOLO置信度: {region.get('yolo_confidence', 0.0):.4f}\n\n"
        label_confidence = region.get('label_confidence', [])
        final_label_index = region.get('final_label_index', 0)
        
        if label_confidence:
            conf_text += "标签置信度:\n"
            for i, conf in enumerate(label_confidence):
                label = conf.get('label', 'N/A')
                confidence = conf.get('confidence', 0.0)
                class_name = self.class_manager.get_class_name(label)
                
                # 标记当前选中的标签
                marker = " ← 当前选中" if i == final_label_index else ""
                conf_text += f"  [{i}] {class_name} ({label}): {confidence:.4f}{marker}\n"
        
        self.confidence_text.setPlainText(conf_text)
    
    def on_class_changed(self):
        """处理类别改变事件"""
        if self.current_region_index >= 0:
            # 只有在用户手动更改时才允许修改（防止自动设置被覆盖）
            if hasattr(self, '_updating_class_selection'):
                return
                
            new_class_id = self.class_combo.currentData()
            region = self.button.regions[self.current_region_index]
            
            # 获取当前的final_label_index
            final_label_index = region.get('final_label_index', 0)
            label_confidence = region.get('label_confidence', [])
            
            # 检查索引是否有效
            if 0 <= final_label_index < len(label_confidence):
                # 修改对应项的label值
                label_confidence[final_label_index]['label'] = new_class_id
                
                # 只有在不是人工添加的区域时才自动设置modified_status为1
                if region.get('modified_status', 0) != 2:
                    region['modified_status'] = 1
                    
                    # 更新修改状态显示（使用标志防止触发on_modify_changed）
                    self._updating_modify_status = True
                    self.modify_spin.setValue(1)
                    delattr(self, '_updating_modify_status')
                
                self.regions_modified = True
                self.update_region_list()
                self.update_class_statistics()  # 更新统计信息
                self.image_label.update_display()  # 重新绘制图片
                
                # 重新加载区域数据以显示更新后的信息
                self.load_region_data(region)
            else:
                QMessageBox.warning(
                    self, "索引错误", 
                    f"final_label_index ({final_label_index}) 超出了label_confidence数组范围。"
                )
    
    
    def on_modify_changed(self, value):
        """处理修改状态改变事件"""
        if self.current_region_index >= 0:
            # 只有在用户手动更改时才允许修改（防止自动设置被覆盖）
            if not hasattr(self, '_updating_modify_status'):
                self.button.regions[self.current_region_index]['modified_status'] = value
                self.regions_modified = True
                self.update_region_list()
                self.update_class_statistics()  # 更新统计信息
    
    def save_changes(self):
        """保存修改"""
        if self.regions_modified:
            reply = QMessageBox.question(
                self, "保存修改", 
                "是否保存对缺陷区域的修改？\n注意：这将修改原始JSON数据。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # 保存到JSON文件
                    if hasattr(self.parent_app, 'save_json_data'):
                        self.parent_app.save_json_data()
                        
                        # 及时刷新按钮上的洁净度数量
                        if hasattr(self.parent_app, 'refresh_button_display'):
                            self.parent_app.refresh_button_display(self.button)
                        
                        QMessageBox.information(self, "保存成功", "修改已保存到JSON文件！")
                        self.regions_modified = False
                    else:
                        QMessageBox.warning(self, "保存失败", "无法找到保存方法，请检查程序配置。")
                except Exception as e:
                    QMessageBox.critical(self, "保存错误", f"保存文件时发生错误:\n{str(e)}")
        
        self.close()
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_Left:
            # 左箭头键：上一个区域
            self.go_to_previous_region()
        elif event.key() == Qt.Key.Key_Right:
            # 右箭头键：下一个区域
            self.go_to_next_region()
        elif event.key() == Qt.Key.Key_Space:
            # 空格键：快速确认当前区域（将修改状态设为1）
            if self.current_region_index >= 0:
                region = self.button.regions[self.current_region_index]
                # 只有在不是人工添加的区域时才设置为已修改状态
                if region.get('modified_status', 0) != 2:
                    region['modified_status'] = 1
                    self.regions_modified = True
                    self.load_region_data(region)
                    self.update_region_list()
                    self.update_class_statistics()
                    self.image_label.update_display()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        if self.regions_modified:
            reply = QMessageBox.question(
                self, "未保存的修改", 
                "有未保存的修改，是否要保存？",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_changes()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                # 即使不保存，也需要刷新按钮显示以确保状态正确
                if hasattr(self.parent_app, 'refresh_button_display'):
                    self.parent_app.refresh_button_display(self.button)
                event.accept()
            else:
                event.ignore()
                return
        else:
            # 即使没有修改，也刷新按钮显示以确保状态正确
            if hasattr(self.parent_app, 'refresh_button_display'):
                self.parent_app.refresh_button_display(self.button)
            event.accept()
        
        # 清理父应用的引用
        if hasattr(self, 'parent_app') and self.parent_app:
            if hasattr(self.parent_app, 'detail_dialog'):
                self.parent_app.detail_dialog = None
    
    def keyPressEvent(self, event):
        """处理键盘快捷键"""
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Up:
            # 左键或上键：上一个区域
            self.go_to_previous_region()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_Down:
            # 右键或下键：下一个区域
            self.go_to_next_region()
        elif event.key() == Qt.Key.Key_Space:
            # 空格键：快速确认当前区域
            self.quick_confirm_current_region()
        elif event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            # Delete键或Backspace键：删除当前区域
            if self.current_region_index >= 0:
                self.delete_current_region()
        elif event.key() == Qt.Key.Key_H:
            # H键：切换区域框显示/隐藏
            self.toggle_regions_visibility()
        elif event.key() == Qt.Key.Key_Escape:
            # ESC键：关闭窗口
            self.close()
        else:
            super().keyPressEvent(event)
    
    def zoom_in(self):
        """放大图片，以视窗中心为中心"""
        if hasattr(self, 'image_label') and self.image_label:
            self._zoom_with_center(1.2)
    
    def zoom_out(self):
        """缩小图片，以视窗中心为中心"""
        if hasattr(self, 'image_label') and self.image_label:
            self._zoom_with_center(0.8)
    
    def _zoom_with_center(self, zoom_multiplier):
        """以视窗中心为中心进行缩放"""
        if not hasattr(self, 'image_label') or not self.image_label or not self.image_label.scroll_area:
            return
        
        # 获取滚动区域
        scroll_area = self.image_label.scroll_area
        
        # 获取视窗中心点
        viewport = scroll_area.viewport()
        center_x = viewport.width() / 2
        center_y = viewport.height() / 2
        
        # 获取滚动条位置
        h_scrollbar = scroll_area.horizontalScrollBar()
        v_scrollbar = scroll_area.verticalScrollBar()
        old_h_value = h_scrollbar.value()
        old_v_value = v_scrollbar.value()
        
        # 计算视窗中心在图片中的相对位置
        old_size = self.image_label.size()
        if old_size.width() > 0 and old_size.height() > 0:
            rel_x = (center_x + old_h_value) / old_size.width()
            rel_y = (center_y + old_v_value) / old_size.height()
        else:
            rel_x = 0.5
            rel_y = 0.5
        
        # 执行缩放
        old_zoom = self.image_label.zoom_factor
        self.image_label.zoom_factor *= zoom_multiplier
        self.image_label.zoom_factor = max(0.1, min(5.0, self.image_label.zoom_factor))
        
        # 更新显示
        self.image_label.update_display()
        self.update_zoom_label()
        
        # 计算新的滚动位置以保持视窗中心为缩放中心
        new_size = self.image_label.size()
        new_h_value = rel_x * new_size.width() - center_x
        new_v_value = rel_y * new_size.height() - center_y
        
        # 设置新的滚动位置
        h_scrollbar.setValue(int(new_h_value))
        v_scrollbar.setValue(int(new_v_value))
    
    def zoom_reset(self):
        """重置缩放，以视窗中心为中心"""
        if hasattr(self, 'image_label') and self.image_label:
            # 如果当前已经是100%，直接返回
            if abs(self.image_label.zoom_factor - 1.0) < 0.01:
                return
            
            # 计算缩放倍数
            reset_multiplier = 1.0 / self.image_label.zoom_factor
            self._zoom_with_center(reset_multiplier)
    
    def update_zoom_label(self):
        """更新缩放标签"""
        if hasattr(self, 'image_label') and self.image_label and hasattr(self, 'zoom_label'):
            zoom_percent = int(self.image_label.zoom_factor * 100)
            self.zoom_label.setText(f"缩放: {zoom_percent}%")
    
    def toggle_regions_visibility(self):
        """切换区域框的显示/隐藏"""
        self.regions_visible = not self.regions_visible
        
        # 更新按钮文本
        if self.regions_visible:
            self.toggle_regions_btn.setText("隐藏区域框")
            self.toggle_regions_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        else:
            self.toggle_regions_btn.setText("显示区域框")
            self.toggle_regions_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        
        # 更新图片显示
        if hasattr(self, 'image_label') and self.image_label:
            self.image_label.regions_visible = self.regions_visible
            self.image_label.update_display()


class ImageButton(QPushButton):
    """自定义图片按钮类"""
    def __init__(self, button_name, pic_info, parent=None):
        super().__init__(parent)
        self.button_name = button_name
        self.pic_info = pic_info
        self.img_path = pic_info.get('imgPath', '')
        self.regions = pic_info.get('regions', [])
        self.column = pic_info.get('column', 0)
        self.index = pic_info.get('index', 0)
        
        # 计算洁净度区域数量
        cleanliness_count = self.count_cleanliness_regions()
        
        # 检查确认状态
        confirmation_status = self.check_confirmation_status()
        
        # 设置按钮文本和样式，包含确认状态
        confirmation_text = ""
        if confirmation_status["total"] > 0:
            confirmation_text = f"\n确认: {confirmation_status['confirmed']}/{confirmation_status['total']}"
        
        self.setText(f"{button_name}\n区域: {len(self.regions)}\n洁净度: {cleanliness_count}{confirmation_text}")
        self.setMinimumSize(80, 100)  # 增加高度以容纳更多文本
        self.setMaximumSize(120, 120)
        
        # 根据确认状态设置不同颜色
        if confirmation_status["total"] > 0 and confirmation_status["unconfirmed"] > 0:
            # 有未确认的区域 - 使用橙色警告色
            self.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc99;
                    border: 2px solid #ff9933;
                    border-radius: 5px;
                    font-size: 9px;
                    color: #cc3300;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ffaa66;
                }
                QPushButton:pressed {
                    background-color: #ff7700;
                }
            """)
        elif self.regions:
            # 有缺陷区域且已全部确认 - 使用红色
            self.setStyleSheet("""
                QPushButton {
                    background-color: #ffcccc;
                    border: 2px solid #ff6666;
                    border-radius: 5px;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #ff9999;
                }
                QPushButton:pressed {
                    background-color: #ff3333;
                }
            """)
        else:
            # 无缺陷区域 - 使用绿色
            self.setStyleSheet("""
                QPushButton {
                    background-color: #ccffcc;
                    border: 2px solid #66cc66;
                    border-radius: 5px;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #99ff99;
                }
                QPushButton:pressed {
                    background-color: #33ff33;
                }
            """)
    
    def get_region_class_id(self, region):
        """从区域数据中获取正确的类别ID"""
        try:
            final_label_index = region.get('final_label_index', 0)
            label_confidence = region.get('label_confidence', [])
            
            # 检查索引是否有效
            if 0 <= final_label_index < len(label_confidence):
                return label_confidence[final_label_index].get('label', 11)
            else:
                # 如果索引无效，返回默认值或第一个标签
                if label_confidence:
                    return label_confidence[0].get('label', 11)
                return 11  # 默认为"非缺陷"
        except (IndexError, TypeError):
            return 11  # 出错时返回默认值
    
    def count_cleanliness_regions(self):
        """计算洁净度（label为10）的区域数量"""
        if not self.regions:
            return 0
        
        cleanliness_count = 0
        for region in self.regions:
            class_id = self.get_region_class_id(region)
            if class_id == 10:  # 洁净度的label为10
                cleanliness_count += 1
        
        return cleanliness_count
    
    def check_confirmation_status(self):
        """检查所有区域的确认状态"""
        if not self.regions:
            return {"total": 0, "confirmed": 0, "unconfirmed": 0}
        
        total = len(self.regions)
        confirmed = 0
        unconfirmed = 0
        
        for region in self.regions:
            modified_status = region.get('modified_status', 0)
            if modified_status > 0:  # 已修改或已添加表示已确认
                confirmed += 1
            else:
                unconfirmed += 1
        
        return {"total": total, "confirmed": confirmed, "unconfirmed": unconfirmed}


class BoardView(QWidget):
    """黑板视图组件"""
    button_clicked = pyqtSignal(object)  # 发送被点击按钮的信号
    
    def __init__(self, side_name, parent=None):
        super().__init__(parent)
        self.side_name = side_name
        self.buttons = []
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(f"黑板{self.side_name}")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.grid_layout = QGridLayout(scroll_widget)
        self.grid_layout.setSpacing(5)
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(400)
        
        layout.addWidget(scroll_area)
    
    def add_buttons(self, pic_info_list):
        """添加按钮到网格布局"""
        # 清除现有按钮
        self.clear_buttons()
        
        if not pic_info_list:
            return
        
        # 首先添加列号标签（第0行）
        for col in range(10):  # 10列
            column_label = QLabel(f"列 {col + 1}")
            column_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column_label.setStyleSheet("""
                QLabel {
                    background-color: #e0e0e0;
                    border: 1px solid #999;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px;
                    margin: 2px;
                }
            """)
            column_label.setMinimumHeight(30)
            column_label.setMaximumHeight(30)
            self.grid_layout.addWidget(column_label, 0, col)  # 第0行放列号
        
        # 按照拍摄顺序排序（根据connectButtonName中的数字）
        def extract_number(pic_info):
            try:
                button_name = pic_info.get('connectButtonName', '')
                parts = button_name.split('_')
                if len(parts) >= 2:
                    return int(parts[1])
                return 0
            except (ValueError, IndexError):
                return 0
        
        # 判断是正面还是反面
        is_front = True
        if pic_info_list:
            first_number = extract_number(pic_info_list[0])
            is_front = first_number <= 25
        
        # 为每个按钮创建widget并放置到正确位置
        for pic_info in pic_info_list:
            button_name = pic_info.get('connectButtonName', f'img_{len(self.buttons)+1}')
            button = ImageButton(button_name, pic_info)
            button.clicked.connect(lambda checked, btn=button: self.button_clicked.emit(btn))
            
            # 获取列号 (1-10) - 直接使用JSON中的column值
            column = pic_info.get('column', 1)
            
            # 从按钮名称提取位置编号
            position = extract_number(pic_info)
            
            if is_front:
                # 正面：从左下角开始，自下向上拍摄每列
                # 根据position计算在列内的位置
                if button_name.startswith('p1_'):
                    # 第一个相机：p1_1到p1_25
                    pics_in_column = [p for p in pic_info_list if p.get('column') == column and p.get('connectButtonName', '').startswith('p1_')]
                    pics_in_column.sort(key=extract_number)
                    if pic_info in pics_in_column:
                        index_in_column = pics_in_column.index(pic_info)
                        # 检查是否是需要颠倒的列（3,4,7,8）
                        if column in [3, 4, 7, 8]:
                            row = index_in_column + 1  # 从上到下：1,2,3,4,5 (+1因为第0行是列号)
                        else:
                            row = 5 - index_in_column  # 从下到上：5,4,3,2,1 (+1因为第0行是列号)
                    else:
                        row = 1
                elif button_name.startswith('p2_'):
                    # 第二个相机：p2_1到p2_25
                    pics_in_column = [p for p in pic_info_list if p.get('column') == column and p.get('connectButtonName', '').startswith('p2_')]
                    pics_in_column.sort(key=extract_number)
                    if pic_info in pics_in_column:
                        index_in_column = pics_in_column.index(pic_info)
                        # 检查是否是需要颠倒的列（3,4,7,8）
                        if column in [3, 4, 7, 8]:
                            row = index_in_column + 1  # 从上到下：1,2,3,4,5 (+1因为第0行是列号)
                        else:
                            row = 5 - index_in_column  # 从下到上：5,4,3,2,1 (+1因为第0行是列号)
                    else:
                        row = 1
                
                col = column - 1  # 列位置（0-9）
                
            else:
                # 反面：从右上角开始，自上向下拍摄每列
                if button_name.startswith('p1_'):
                    # 第一个相机：p1_26到p1_50
                    pics_in_column = [p for p in pic_info_list if p.get('column') == column and p.get('connectButtonName', '').startswith('p1_')]
                    pics_in_column.sort(key=extract_number)
                    if pic_info in pics_in_column:
                        index_in_column = pics_in_column.index(pic_info)
                        # 检查是否是需要颠倒的列（3,4,7,8）
                        if column in [3, 4, 7, 8]:
                            row = 5 - index_in_column  # 从下到上：5,4,3,2,1 (+1因为第0行是列号)
                        else:
                            row = index_in_column + 1  # 从上到下：1,2,3,4,5 (+1因为第0行是列号)
                    else:
                        row = 1
                elif button_name.startswith('p2_'):
                    # 第二个相机：p2_26到p2_50
                    pics_in_column = [p for p in pic_info_list if p.get('column') == column and p.get('connectButtonName', '').startswith('p2_')]
                    pics_in_column.sort(key=extract_number)
                    if pic_info in pics_in_column:
                        index_in_column = pics_in_column.index(pic_info)
                        # 检查是否是需要颠倒的列（3,4,7,8）
                        if column in [3, 4, 7, 8]:
                            row = 5 - index_in_column  # 从下到上：5,4,3,2,1 (+1因为第0行是列号)
                        else:
                            row = index_in_column + 1  # 从上到下：1,2,3,4,5 (+1因为第0行是列号)
                    else:
                        row = 1
                
                col = column - 1  # 列位置（0-9）
            
            self.grid_layout.addWidget(button, row, col)
            self.buttons.append(button)
    
    def clear_buttons(self):
        """清除所有按钮和标签"""
        # 清除按钮
        for button in self.buttons:
            button.deleteLater()
        self.buttons.clear()
        
        # 清除网格布局中的所有组件（包括列号标签）
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


class SilkLabelApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_file_path = None
        self.json_data = None
        self.current_board_data = None
        self.json_dir = None  # JSON文件所在目录
        self.detail_dialog = None  # 保存当前打开的详细标注窗口
        self.init_ui()
    
    def get_actual_image_path(self, original_img_path):
        """根据JSON文件所在目录计算实际的图片路径"""
        if not original_img_path:
            return original_img_path
        
        # 如果json_dir为空，尝试从selected_file_path获取
        json_dir = self.json_dir
        if not json_dir and self.selected_file_path:
            json_dir = os.path.dirname(self.selected_file_path)
        
        if not json_dir:
            return original_img_path
        
        try:
            # 从原始路径中提取相机文件夹和图片文件名
            # 例如："E:/img/20250805/2/camera2/img1.bmp" -> "camera2/img1.bmp"
            path_parts = original_img_path.replace('\\', '/').split('/')
            
            # 找到camera1或camera2的位置
            camera_index = -1
            for i, part in enumerate(path_parts):
                if part.startswith('camera'):
                    camera_index = i
                    break
            
            if camera_index >= 0:
                # 提取从camera开始的相对路径
                relative_path = '/'.join(path_parts[camera_index:])
                # 组合成完整路径
                actual_path = os.path.join(json_dir, relative_path)
                # 将反斜杠转换为正斜杠以保持一致性
                actual_path = actual_path.replace('\\', '/')
                return actual_path
            else:
                return original_img_path
                
        except Exception as e:
            print(f"转换图片路径时出错: {e}")
            return original_img_path
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("SilkLabel - 生丝缺陷标注工具")
        self.setGeometry(100, 100, 1000, 700)
        
        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建顶部控制区域
        self.create_control_panel(main_layout)
        
        # 创建黑板视图区域
        self.create_board_view_panel(main_layout)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setStyleSheet("padding: 5px; border-top: 1px solid gray;")
        main_layout.addWidget(self.status_label)
    
    def create_control_panel(self, main_layout):
        """创建顶部控制面板"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 选择文件按钮
        self.select_file_btn = QPushButton("选择JSON文件")
        self.select_file_btn.clicked.connect(self.select_json_file)
        self.select_file_btn.setMinimumHeight(40)
        button_layout.addWidget(self.select_file_btn)
        
        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_content)
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        control_layout.addLayout(button_layout)
        
        # 文件路径显示标签
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        control_layout.addWidget(self.file_path_label)
        
        # 批次信息标签
        self.batch_info_label = QLabel("")
        self.batch_info_label.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        control_layout.addWidget(self.batch_info_label)
        
        main_layout.addWidget(control_frame)
    
    def create_board_view_panel(self, main_layout):
        """创建黑板视图面板"""
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 正面视图 (1-25)
        self.front_view = BoardView("正面")
        self.front_view.button_clicked.connect(self.on_image_button_clicked)
        self.tab_widget.addTab(self.front_view, "正面 (1-25)")
        
        # 反面视图 (26-50)
        self.back_view = BoardView("反面")
        self.back_view.button_clicked.connect(self.on_image_button_clicked)
        self.tab_widget.addTab(self.back_view, "反面 (26-50)")
        
        main_layout.addWidget(self.tab_widget)
    
    def save_json_data(self):
        """保存JSON数据到文件"""
        if not self.selected_file_path or not self.json_data:
            raise Exception("没有可保存的数据或文件路径")
        
        try:
            with open(self.selected_file_path, 'w', encoding='utf-8') as file:
                json.dump(self.json_data, file, ensure_ascii=False, indent=2)
            print(f"JSON数据已保存到: {self.selected_file_path}")
        except Exception as e:
            raise Exception(f"保存JSON文件失败: {str(e)}")
    
    def refresh_button_display(self, updated_button):
        """刷新指定按钮的显示（洁净度数量等）"""
        try:
            # 重新计算洁净度区域数量
            cleanliness_count = updated_button.count_cleanliness_regions()
            
            # 检查确认状态
            confirmation_status = updated_button.check_confirmation_status()
            
            # 更新按钮文本，包含确认状态
            confirmation_text = ""
            if confirmation_status["total"] > 0:
                confirmation_text = f"\n确认: {confirmation_status['confirmed']}/{confirmation_status['total']}"
            
            updated_button.setText(f"{updated_button.button_name}\n区域: {len(updated_button.regions)}\n洁净度: {cleanliness_count}{confirmation_text}")
            
            # 根据确认状态重新设置按钮样式
            if confirmation_status["total"] > 0 and confirmation_status["unconfirmed"] > 0:
                # 有未确认的区域 - 使用橙色警告色
                updated_button.setStyleSheet("""
                    QPushButton {
                        background-color: #ffcc99;
                        border: 2px solid #ff9933;
                        border-radius: 5px;
                        font-size: 9px;
                        color: #cc3300;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #ffaa66;
                    }
                    QPushButton:pressed {
                        background-color: #ff7700;
                    }
                """)
            elif updated_button.regions:
                # 有缺陷区域且已全部确认 - 使用红色
                updated_button.setStyleSheet("""
                    QPushButton {
                        background-color: #ffcccc;
                        border: 2px solid #ff6666;
                        border-radius: 5px;
                        font-size: 9px;
                    }
                    QPushButton:hover {
                        background-color: #ff9999;
                    }
                    QPushButton:pressed {
                        background-color: #ff3333;
                    }
                """)
            else:
                # 无缺陷区域 - 使用绿色
                updated_button.setStyleSheet("""
                    QPushButton {
                        background-color: #ccffcc;
                        border: 2px solid #66cc66;
                        border-radius: 5px;
                        font-size: 9px;
                    }
                    QPushButton:hover {
                        background-color: #99ff99;
                    }
                    QPushButton:pressed {
                        background-color: #33ff33;
                    }
                """)
            
            print(f"已刷新按钮 {updated_button.button_name} 的显示")
            
        except Exception as e:
            print(f"刷新按钮显示时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def select_json_file(self):
        """选择JSON文件"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "选择JSON文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            self.selected_file_path = file_path
            self.load_json_file(file_path)
    
    def select_json_file(self):
        """选择JSON文件"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "选择JSON文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            self.selected_file_path = file_path
            self.load_json_file(file_path)
    
    def load_json_file(self, file_path):
        """加载并显示JSON文件内容"""
        try:
            # 先清理旧数据
            if hasattr(self, 'detail_dialog') and self.detail_dialog:
                try:
                    self.detail_dialog.close()
                except RuntimeError:
                    # 对象已经被删除，忽略错误
                    pass
                self.detail_dialog = None
            
            # 清空旧的按钮视图
            self.front_view.clear_buttons()
            self.back_view.clear_buttons()
            
            with open(file_path, 'r', encoding='utf-8') as file:
                self.json_data = json.load(file)
            
            # 设置JSON文件所在目录
            self.json_dir = os.path.dirname(file_path)
            
            # 更新界面状态
            self.file_path_label.setText(f"文件路径: {file_path}")
            self.file_path_label.setStyleSheet("QLabel { color: black; }")
            self.clear_btn.setEnabled(True)
            
            # 处理黑板数据
            self.process_board_data()
            
            self.status_label.setText(f"成功加载文件: {file_path}")
            
        except json.JSONDecodeError as e:
            QMessageBox.warning(
                self,
                "JSON解析错误",
                f"文件不是有效的JSON格式:\n{str(e)}"
            )
            self.status_label.setText("JSON解析失败")
            
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "文件错误",
                "找不到指定的文件!"
            )
            self.status_label.setText("文件未找到")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"加载文件时发生错误:\n{str(e)}"
            )
            self.status_label.setText("加载文件失败")
    
    def process_board_data(self):
        """处理黑板数据并生成按钮"""
        if not self.json_data:
            return
        
        try:
            # 获取批次名称
            batch_name = self.json_data.get('batchName', '未知批次')
            self.batch_info_label.setText(f"批次: {batch_name}")
            
            # 获取当前黑板数据
            self.current_board_data = self.json_data.get('currentBlackboard')
            if not self.current_board_data:
                QMessageBox.warning(self, "数据错误", "JSON文件中没有找到currentBlackboard数据")
                return
            
            all_pic_info = self.current_board_data.get('all_pic_info', [])
            if not all_pic_info:
                QMessageBox.warning(self, "数据错误", "JSON文件中没有找到图片信息")
                return
            
            # 分离正面和反面图片
            front_pics = []  # 正面：1_1到1_25 + 2_1到2_25
            back_pics = []   # 反面：1_26到1_50 + 2_26到2_50
            
            for pic_info in all_pic_info:
                button_name = pic_info.get('connectButtonName', '')
                
                # 解析按钮名称，如 "p1_1" 或 "p2_26"
                if button_name.startswith('p1_'):
                    # 第1个相机
                    try:
                        number = int(button_name.split('_')[1])
                        if 1 <= number <= 25:
                            front_pics.append(pic_info)
                        elif 26 <= number <= 50:
                            back_pics.append(pic_info)
                    except (ValueError, IndexError):
                        pass
                elif button_name.startswith('p2_'):
                    # 第2个相机
                    try:
                        number = int(button_name.split('_')[1])
                        if 1 <= number <= 25:
                            front_pics.append(pic_info)
                        elif 26 <= number <= 50:
                            back_pics.append(pic_info)
                    except (ValueError, IndexError):
                        pass
            
            # 按照相机和编号排序
            def sort_key(pic_info):
                try:
                    button_name = pic_info.get('connectButtonName', '')
                    parts = button_name.split('_')
                    if len(parts) >= 2:
                        camera = int(parts[0][1:])  # p1 -> 1, p2 -> 2
                        number = int(parts[1])
                        return (camera, number)
                    return (0, 0)
                except (ValueError, IndexError):
                    return (0, 0)
            
            front_pics.sort(key=sort_key)
            back_pics.sort(key=sort_key)
            
            # 生成按钮
            self.front_view.add_buttons(front_pics)
            self.back_view.add_buttons(back_pics)
            
            self.status_label.setText(f"已加载 {len(front_pics)} 张正面图片和 {len(back_pics)} 张反面图片")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "处理数据错误",
                f"处理黑板数据时发生错误:\n{str(e)}"
            )
    
    def on_image_button_clicked(self, button):
        """处理图片按钮点击事件"""
        try:
            # 设置JSON文件所在目录
            if self.selected_file_path and not self.json_dir:
                self.json_dir = os.path.dirname(self.selected_file_path)
            
            # 获取实际的图片路径
            actual_img_path = self.get_actual_image_path(button.img_path)
            
            if not actual_img_path or not os.path.exists(actual_img_path):
                QMessageBox.warning(
                    self, "图片不存在", 
                    f"无法找到图片文件：{button.img_path}\n计算的路径：{actual_img_path}"
                )
                return
            
            # 创建并显示详细标注界面
            self.detail_dialog = DetailDialog(button, actual_img_path, self)
            self.detail_dialog.showMaximized()  # 最大化显示
            
            # 更新状态标签
            self.status_label.setText(f"打开标注界面: {button.button_name}")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"打开标注界面时发生错误:\n{str(e)}"
            )
            print(f"Error in on_image_button_clicked: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_content(self):
        """清空显示内容"""
        self.file_path_label.setText("未选择文件")
        self.file_path_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        self.batch_info_label.setText("")
        self.clear_btn.setEnabled(False)
        self.selected_file_path = None
        self.json_data = None
        self.current_board_data = None
        self.json_dir = None  # 清除JSON目录
        
        # 关闭当前打开的详细标注窗口
        if hasattr(self, 'detail_dialog') and self.detail_dialog:
            try:
                self.detail_dialog.close()
            except RuntimeError:
                # 对象已经被删除，忽略错误
                pass
            self.detail_dialog = None
        
        # 清空按钮视图
        self.front_view.clear_buttons()
        self.back_view.clear_buttons()
        
        self.status_label.setText("内容已清空，图片缓存已清理")


def main():
    app = QApplication(sys.argv)
    window = SilkLabelApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
