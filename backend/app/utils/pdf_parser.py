"""
PDF 解析工具
支持文本提取、图像识别、表格解析等功能
使用 PyMuPDF 作为主要解析引擎，性能更好
"""
import os
import logging
import fitz  # PyMuPDF - 更好的PDF处理库
import pdfplumber  # 用于表格解析
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import pytesseract
import io
import re
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PDFContent(BaseModel):
    """PDF 内容数据结构"""
    text: str = ""
    page_count: int = 0
    metadata: Dict[str, Any] = {}
    images: List[Dict[str, Any]] = []
    has_forms: bool = False
    tables: List[Dict[str, Any]] = []


class PDFParser:
    """PDF 解析器 - 基于 PyMuPDF"""
    
    def __init__(self, enable_ocr: bool = True):
        """
        初始化 PDF 解析器
        
        Args:
            enable_ocr: 是否启用 OCR，只对扫描版PDF使用
        """
        self.enable_ocr = enable_ocr
        
        # 检查 tesseract 是否可用
        if enable_ocr:
            try:
                pytesseract.get_tesseract_version()
                logger.info("✅ Tesseract OCR 可用")
            except Exception as e:
                logger.warning(f"⚠️ Tesseract OCR 不可用: {str(e)}")
                self.enable_ocr = False
    
    def parse_pdf(self, pdf_path: str) -> PDFContent:
        """
        解析 PDF 文件
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            PDFContent: 解析结果
        """
        start_time = datetime.now()
        logger.info(f"🔍 开始解析PDF: {pdf_path}")
        
        try:
            # 使用 PyMuPDF 打开PDF
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            logger.info(f"📄 PDF页数: {page_count}")
            
            # 获取文档元数据
            metadata = self._extract_metadata(doc)
            
            # 提取文本内容
            text_content = self._extract_text_content(doc)
            
            # 判断是否需要OCR
            needs_ocr = self._should_use_ocr(text_content, page_count)
            
            # 处理图像和OCR
            images = []
            if needs_ocr and self.enable_ocr:
                logger.info("🔤 检测到扫描版PDF，启用OCR...")
                images = self._extract_images_with_ocr(doc)
                # 将OCR文本添加到主文本中
                ocr_texts = [img.get("ocr_text", "") for img in images if img.get("ocr_text")]
                if ocr_texts:
                    text_content += "\n\n=== OCR识别内容 ===\n" + "\n".join(ocr_texts)
            elif not needs_ocr:
                logger.info("📝 检测到标准PDF，跳过OCR")
                images = self._extract_images_metadata(doc)
            
            # 提取表格（使用pdfplumber）
            tables = self._extract_tables_with_pdfplumber(pdf_path)
            
            # 检查是否有表单
            has_forms = self._check_forms(doc)
            
            doc.close()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ PDF解析完成，耗时: {processing_time:.2f}秒")
            
            return PDFContent(
                text=text_content,
                page_count=page_count,
                metadata=metadata,
                images=images,
                has_forms=has_forms,
                tables=tables
            )
            
        except Exception as e:
            logger.error(f"❌ PDF解析失败: {str(e)}")
            raise
    
    def _extract_metadata(self, doc: fitz.Document) -> Dict[str, Any]:
        """提取PDF元数据"""
        try:
            metadata = doc.metadata
            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": metadata.get("creationDate", ""),
                "modification_date": metadata.get("modDate", "")
            }
        except Exception as e:
            logger.warning(f"元数据提取失败: {str(e)}")
            return {}
    
    def _extract_text_content(self, doc: fitz.Document) -> str:
        """提取文本内容，处理编码问题"""
        text_content = []
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                
                # 使用PyMuPDF提取文本，保持布局
                text = page.get_text()
                
                # 处理字符编码问题
                if text.strip():
                    # 清理可能的编码问题
                    try:
                        # 确保文本是有效的UTF-8
                        cleaned_text = text.encode('utf-8', errors='ignore').decode('utf-8')
                        # 移除控制字符，但保留换行符和制表符
                        cleaned_text = ''.join(char for char in cleaned_text 
                                             if ord(char) >= 32 or char in '\n\r\t')
                        
                        if cleaned_text.strip():
                            text_content.append(f"\n--- 第 {page_num + 1} 页 ---\n")
                            text_content.append(cleaned_text)
                            
                    except UnicodeError as ue:
                        logger.warning(f"第{page_num + 1}页字符编码处理失败: {str(ue)}")
                        # 尝试其他编码方式
                        try:
                            fallback_text = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                            if fallback_text.strip():
                                text_content.append(f"\n--- 第 {page_num + 1} 页 (编码修复) ---\n")
                                text_content.append(fallback_text)
                        except Exception:
                            logger.warning(f"第{page_num + 1}页编码修复也失败，跳过该页")
                            
            except Exception as e:
                logger.warning(f"第{page_num + 1}页文本提取失败: {str(e)}")
                continue
        
        final_text = "\n".join(text_content)
        logger.info(f"📝 文本提取完成，总字符数: {len(final_text)}")
        return final_text
    
    def _should_use_ocr(self, text_content: str, page_count: int) -> bool:
        """
        智能判断是否需要使用OCR
        
        Args:
            text_content: 已提取的文本内容
            page_count: 页数
            
        Returns:
            bool: 是否需要OCR
        """
        if not self.enable_ocr:
            return False
        
        # 计算文本密度
        clean_text = re.sub(r'\s+', ' ', text_content).strip()
        text_length = len(clean_text)
        
        # 平均每页文本字符数
        avg_chars_per_page = text_length / page_count if page_count > 0 else 0
        
        # 判断逻辑：
        # 1. 如果平均每页字符数少于50，可能是扫描版
        # 2. 如果文本主要是特殊字符或乱码，可能是扫描版  
        # 3. 如果文本中有效字符比例过低，可能是扫描版
        
        logger.info(f"📊 文本分析 - 总字符数: {text_length}, 平均每页: {avg_chars_per_page:.1f}")
        
        if avg_chars_per_page < 50:
            logger.info("🔍 检测理由: 平均每页字符数过少，可能是扫描版")
            return True
        
        # 检查有效字符比例
        if text_length > 0:
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_text))
            english_chars = len(re.findall(r'[a-zA-Z]', clean_text))
            numbers = len(re.findall(r'[0-9]', clean_text))
            valid_chars = chinese_chars + english_chars + numbers
            
            valid_ratio = valid_chars / text_length
            logger.info(f"📊 有效字符比例: {valid_ratio:.2f}")
            
            if valid_ratio < 0.3:  # 有效字符少于30%
                logger.info("🔍 检测理由: 有效字符比例过低，可能是扫描版")
                return True
        
        logger.info("📝 检测结果: 标准PDF，包含可提取文本")
        return False
    
    def _extract_images_with_ocr(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """提取图像并进行OCR识别"""
        images = []
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # 获取图像数据
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # 只处理RGB/GRAY图像
                            img_data = pix.tobytes("png")
                            image = Image.open(io.BytesIO(img_data))
                            
                            # OCR识别
                            ocr_text = ""
                            if self.enable_ocr:
                                try:
                                    ocr_text = pytesseract.image_to_string(
                                        image, 
                                        lang='chi_sim+eng',  # 中英文识别
                                        config='--psm 6'  # 假设单列文本
                                    ).strip()
                                except Exception as ocr_e:
                                    logger.warning(f"OCR识别失败: {str(ocr_e)}")
                            
                            images.append({
                                "page": page_num + 1,
                                "name": f"img_p{page_num + 1}_{img_index + 1}",
                                "size": len(img_data),
                                "ocr_text": ocr_text
                            })
                        
                        pix = None  # 释放内存
                        
                    except Exception as e:
                        logger.warning(f"第{page_num + 1}页图像{img_index + 1}处理失败: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"第{page_num + 1}页图像提取失败: {str(e)}")
                continue
        
        return images
    
    def _extract_images_metadata(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """提取图像元数据（不进行OCR）"""
        images = []
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    images.append({
                        "page": page_num + 1,
                        "name": f"img_p{page_num + 1}_{img_index + 1}",
                        "xref": img[0],
                        "size": "unknown",
                        "ocr_text": ""  # 标准PDF不进行OCR
                    })
                        
            except Exception as e:
                logger.warning(f"第{page_num + 1}页图像元数据提取失败: {str(e)}")
                continue
        
        return images
    
    def _extract_tables_with_pdfplumber(self, pdf_path: str) -> List[Dict[str, Any]]:
        """使用pdfplumber提取表格"""
        tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_tables = page.extract_tables()
                        for table_index, table in enumerate(page_tables):
                            if table and len(table) > 0:
                                tables.append({
                                    "page": page_num + 1,
                                    "table_index": table_index + 1,
                                    "rows": len(table),
                                    "columns": len(table[0]) if table[0] else 0,
                                    "data": table
                                })
                    except Exception as e:
                        logger.warning(f"第{page_num + 1}页表格提取失败: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.warning(f"表格提取失败: {str(e)}")
        
        return tables
    
    def _check_forms(self, doc: fitz.Document) -> bool:
        """检查是否包含表单字段"""
        try:
            # PyMuPDF检查表单字段
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                if widgets:
                    return True
            return False
        except Exception as e:
            logger.warning(f"表单检查失败: {str(e)}")
            return False


def parse_pdf_file(file_path: str, enable_ocr: bool = False) -> PDFContent:
    """
    解析PDF文件，使用PyMuPDF引擎
    
    Args:
        file_path: PDF文件路径
        enable_ocr: 是否启用OCR
        
    Returns:
        PDFContent: 解析结果
    """
    parser = PDFParser(enable_ocr=enable_ocr)
    return parser.parse_pdf(file_path) 