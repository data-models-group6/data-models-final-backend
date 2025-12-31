後端啟動步驟 (Python / FastAPI)

# 1. Clone repository URL
https://github.com/data-models-group6/data-models-final-backend.git

# 2.建立名為 venv 的虛擬環境
python -m venv venv

# 3. 啟動虛擬環境 (Windows PowerShell)
.\venv\Scripts\activate

# 4.安裝依賴套件
pip install -r requirements.txt

# 5.啟動後端伺服器
uvicorn app.main:app --reload
