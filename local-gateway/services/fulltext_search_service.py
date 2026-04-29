"""
全文检索服务 — 支持 PDF、DOCX、TXT、MD 等格式
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# 索引存储
INDEX_FILE = DOWNLOADS_DIR.parent / "data" / "search_index.json"


class FullTextIndex:
    """简单的内存全文索引"""

    def __init__(self):
        self.documents = {}
        self.index = {}  # word -> {doc_id: [positions]}
        self._load()

    def _load(self):
        """加载索引"""
        try:
            if INDEX_FILE.exists():
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.documents = data.get("documents", {})
                self.index = data.get("index", {})
        except Exception as e:
            logger.warning(f"加载搜索索引失败: {e}")

    def save(self):
        """保存索引"""
        try:
            INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "documents": self.documents,
                    "index": self.index,
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存搜索索引失败: {e}")
            return False

    def add_document(self, doc_id: str, content: str, metadata: dict = None):
        """添加文档到索引"""
        # 分词（简单空格分词 + 中文单字）
        words = self._tokenize(content)

        # 存储文档
        self.documents[doc_id] = {
            "content_preview": content[:500],
            "word_count": len(words),
            "metadata": metadata or {},
        }

        # 建立倒排索引
        for i, word in enumerate(words):
            word = word.lower()
            if word not in self.index:
                self.index[word] = {}
            if doc_id not in self.index[word]:
                self.index[word][doc_id] = []
            self.index[word][doc_id].append(i)

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """搜索文档"""
        query_words = self._tokenize(query)
        if not query_words:
            return []

        # 计算每个文档的得分
        doc_scores = {}
        for word in query_words:
            word = word.lower()
            if word in self.index:
                for doc_id, positions in self.index[word].items():
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = {
                            "score": 0,
                            "matched_words": set(),
                            "positions": [],
                        }
                    # TF 加权
                    doc_scores[doc_id]["score"] += len(positions)
                    doc_scores[doc_id]["matched_words"].add(word)
                    doc_scores[doc_id]["positions"].extend(positions)

        # 排序并返回结果
        results = []
        for doc_id, data in doc_scores.items():
            # 计算匹配度 (匹配的词数 / 查询词数)
            match_ratio = len(data["matched_words"]) / len(query_words)
            # 最终得分
            final_score = data["score"] * match_ratio

            doc_info = self.documents.get(doc_id, {})
            results.append({
                "doc_id": doc_id,
                "score": final_score,
                "matched_words": list(data["matched_words"]),
                "preview": doc_info.get("content_preview", ""),
                "metadata": doc_info.get("metadata", {}),
            })

        # 按得分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """分词"""
        # 英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        # 中文单字
        chinese_chars = re.findall(r'[一-鿿]', text)
        # 数字
        numbers = re.findall(r'\d+', text)

        return english_words + chinese_chars + numbers

    def remove_document(self, doc_id: str):
        """从索引中移除文档"""
        if doc_id not in self.documents:
            return

        del self.documents[doc_id]

        # 清理索引
        for word in list(self.index.keys()):
            if doc_id in self.index[word]:
                del self.index[word][doc_id]
            if not self.index[word]:
                del self.index[word]


# 全局索引实例
fulltext_index = FullTextIndex()


# ============================================================
# 文档解析
# ============================================================

def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """从 PDF 提取文本"""
    try:
        import PyPDF2

        text = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")

        return "\n".join(text)
    except Exception as e:
        logger.error(f"PDF 解析失败 {file_path}: {e}")
        return None


def extract_text_from_docx(file_path: str) -> Optional[str]:
    """从 DOCX 提取文本"""
    try:
        import docx2txt

        return docx2txt.process(file_path)
    except Exception as e:
        logger.error(f"DOCX 解析失败 {file_path}: {e}")
        return None


def extract_text_from_txt(file_path: str) -> Optional[str]:
    """从 TXT 提取文本"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        logger.error(f"TXT 读取失败 {file_path}: {e}")
        return None


def extract_text(file_path: str) -> Optional[str]:
    """根据文件类型提取文本"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif suffix in (".txt", ".md", ".py", ".js", ".json", ".yaml", ".yml"):
        return extract_text_from_txt(file_path)
    else:
        return None


# ============================================================
# 索引管理
# ============================================================

async def index_all_files(category: str = None) -> dict:
    """
    索引所有下载的文件

    Args:
        category: 指定分类索引，None 表示全部
    """
    from config import CATEGORY_DIRS

    indexed = 0
    failed = 0

    if category and category in CATEGORY_DIRS:
        dirs = [CATEGORY_DIRS[category]]
    else:
        dirs = list(CATEGORY_DIRS.values())

    for dir_path in dirs:
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue

            # 提取文本
            content = extract_text(str(file_path))
            if content:
                doc_id = str(file_path.relative_to(DOWNLOADS_DIR))
                fulltext_index.add_document(
                    doc_id,
                    content,
                    metadata={
                        "filename": file_path.name,
                        "category": file_path.parent.name,
                        "size": file_path.stat().st_size,
                    },
                )
                indexed += 1
            else:
                failed += 1

    fulltext_index.save()

    return {
        "status": "success",
        "indexed": indexed,
        "failed": failed,
        "total_documents": len(fulltext_index.documents),
    }


async def search_fulltext(query: str, category: str = None, top_k: int = 20) -> dict:
    """全文搜索"""
    if not fulltext_index.documents:
        return {
            "status": "success",
            "query": query,
            "results": [],
            "message": "索引为空，请先运行索引构建",
        }

    results = fulltext_index.search(query, top_k)

    # 按分类过滤
    if category:
        results = [r for r in results if r.get("metadata", {}).get("category") == category]

    return {
        "status": "success",
        "query": query,
        "total_results": len(results),
        "results": results,
    }


async def get_index_stats() -> dict:
    """获取索引统计"""
    return {
        "status": "success",
        "documents": len(fulltext_index.documents),
        "unique_words": len(fulltext_index.index),
        "index_file": str(INDEX_FILE),
    }


async def rebuild_index() -> dict:
    """重建索引"""
    global fulltext_index
    fulltext_index = FullTextIndex()
    result = await index_all_files()
    return result
