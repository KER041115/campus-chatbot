# build_db.py
import os
import glob
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb

print("=" * 50)
print("📚 构建向量数据库...")
print("=" * 50)

# 1. 创建 chroma 客户端
client = chromadb.PersistentClient(path="./chroma_db")

# 删除旧集合（如果存在）
try:
    client.delete_collection("campus_docs")
except:
    pass

# 创建新集合
collection = client.create_collection(
    name="campus_docs",
    metadata={"hnsw:space": "cosine"}
)

# 2. 加载嵌入模型（免费且离线）
print("⏳ 加载嵌入模型...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ 模型加载完成")

# 3. 从 docs 文件夹读取 PDF
docs_dir = "./docs"
if not os.path.exists(docs_dir):
    os.makedirs(docs_dir)
    print(f"⚠️ 已创建 {docs_dir} 文件夹，请将 PDF 文件放入后重新运行此脚本。")
    exit()

pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
if not pdf_files:
    print("⚠️ 未找到 PDF 文件，请将学校资料放入 docs/ 文件夹。")
    exit()

print(f"📄 找到 {len(pdf_files)} 个 PDF 文件")

all_texts = []
all_ids = []
all_metadatas = []

for i, pdf_file in enumerate(pdf_files):
    print(f"📄 正在处理: {os.path.basename(pdf_file)}")
    try:
        reader = PdfReader(pdf_file)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                chunk_id = f"doc_{i}_page_{page_num}"
                all_texts.append(text)
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "source": os.path.basename(pdf_file),
                    "page": page_num + 1
                })
    except Exception as e:
        print(f"   ⚠️ 读取 {pdf_file} 出错: {e}")

if not all_texts:
    print("❌ 未提取到任何文本，请检查 PDF 文件是否可读。")
    exit()

# 4. 生成向量并存入数据库
print(f"✅ 共提取 {len(all_texts)} 页文本，正在生成向量...")

batch_size = 50
for i in range(0, len(all_texts), batch_size):
    batch_texts = all_texts[i:i+batch_size]
    batch_ids = all_ids[i:i+batch_size]
    batch_metadatas = all_metadatas[i:i+batch_size]
    
    # 生成嵌入向量
    embeddings = model.encode(batch_texts).tolist()
    
    # 存入 chromadb
    collection.add(
        documents=batch_texts,
        embeddings=embeddings,
        ids=batch_ids,
        metadatas=batch_metadatas
    )
    print(f"   已存入 {min(i+len(batch_texts), len(all_texts))}/{len(all_texts)} 页")

print("=" * 50)
print(f"✅ 向量数据库构建完成！共 {len(all_texts)} 页")
print(f"📁 保存在 ./chroma_db 文件夹")
print("=" * 50)