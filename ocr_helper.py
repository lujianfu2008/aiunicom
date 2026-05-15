# -*- coding: utf-8 -*-
"""
OCR辅助模块 - 提供图片文字识别功能
"""

import os
import sys
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class OCREngine:
    """OCR引擎封装"""
    
    def __init__(self):
        self._engine = None
        self._engine_type = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """初始化OCR引擎"""
        if self._initialized:
            return True
        
        # 尝试不同的OCR引擎
        engines = [
            ('rapidocr', self._init_rapidocr),
            ('easyocr', self._init_easyocr),
            ('tesseract', self._init_tesseract),
        ]
        
        for name, init_func in engines:
            try:
                logger.info(f"尝试初始化{name}...")
                if init_func():
                    self._engine_type = name
                    self._initialized = True
                    logger.info(f"{name}初始化成功")
                    return True
            except Exception as e:
                logger.debug(f"{name}初始化失败: {e}")
        
        logger.warning("没有可用的OCR引擎")
        return False
    
    def _init_rapidocr(self) -> bool:
        """初始化RapidOCR"""
        from rapidocr_onnxruntime import RapidOCR
        self._engine = RapidOCR()
        return True
    
    def _init_easyocr(self) -> bool:
        """初始化EasyOCR"""
        import easyocr
        self._engine = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        return True
    
    def _init_tesseract(self) -> bool:
        """初始化Tesseract"""
        import pytesseract
        # 测试是否可用
        pytesseract.get_tesseract_version()
        self._engine = pytesseract
        return True
    
    def recognize(self, image_path: str) -> Optional[str]:
        """识别图片中的文字"""
        if not self._initialized:
            if not self.initialize():
                return None
        
        try:
            if self._engine_type == 'rapidocr':
                return self._recognize_rapidocr(image_path)
            elif self._engine_type == 'easyocr':
                return self._recognize_easyocr(image_path)
            elif self._engine_type == 'tesseract':
                return self._recognize_tesseract(image_path)
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
        
        return None
    
    def _recognize_rapidocr(self, image_path: str) -> Optional[str]:
        """使用RapidOCR识别"""
        result, _ = self._engine(image_path)
        if result:
            texts = []
            for item in result:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    texts.append(item[1])
            return '\n'.join(texts) if texts else None
        return None
    
    def _recognize_easyocr(self, image_path: str) -> Optional[str]:
        """使用EasyOCR识别"""
        result = self._engine.readtext(image_path, detail=0, paragraph=True)
        if result:
            return '\n'.join(result)
        return None
    
    def _recognize_tesseract(self, image_path: str) -> Optional[str]:
        """使用Tesseract识别"""
        from PIL import Image
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        text = self._engine.image_to_string(img, lang='chi_sim+eng')
        return text if text.strip() else None


# 全局OCR引擎实例
_ocr_engine = None


def get_ocr_engine() -> OCREngine:
    """获取全局OCR引擎实例"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine()
    return _ocr_engine


def recognize_image(image_path: str) -> Optional[str]:
    """
    识别图片中的文字
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        识别出的文字，失败返回None
    """
    engine = get_ocr_engine()
    return engine.recognize(image_path)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    test_path = r"D:\工作文档\cbss2.0体验版\沃工单问题定位\2109\1861090-操作来源.png"
    
    if os.path.exists(test_path):
        print(f"测试文件: {os.path.basename(test_path)}")
        result = recognize_image(test_path)
        if result:
            print(f"\n识别结果:\n{result[:500]}...")
        else:
            print("识别失败")
    else:
        print(f"文件不存在: {test_path}")
