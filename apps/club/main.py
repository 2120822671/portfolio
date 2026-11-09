import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
import pymysql
from typing import List

app = FastAPI()


# ---------------- 根路径跳转（作品集整合） ----------------
@app.get("/")
async def index_redirect():
    return RedirectResponse(url="/club/static/index.html")

# ---------------- 自动生成 static/index.html ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
HTML_FILE = os.path.join(STATIC_DIR, "index.html")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

if not os.path.exists(HTML_FILE):
    # 【修改点5：前端修复XSS隐患】将 innerHTML 拼接改为安全的 textContent 赋值
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>学生社团活动登记系统</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f4f7f6; }
        h1 { color: #333; text-align: center; }
        .container { max-width: 800px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        .form-group input { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        .form-group input:focus { border-color: #007bff; outline: none; }
        button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        table { width: 100%; border-collapse: collapse; margin-top: 30px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
        th { background-color: #007bff; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .msg { padding: 10px; margin-bottom: 15px; border-radius: 4px; display: none; }
        .msg.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; display: block; }
        .msg.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>学生社团活动登记</h1>
        <form id="activityForm">
            <div id="formMsg" class="msg"></div>
            <div class="form-group">
                <label>活动名称</label>
                <input type="text" id="activity_name" required placeholder="请输入活动名称">
            </div>
            <div class="form-group">
                <label>活动类型</label>
                <input type="text" id="activity_type" required placeholder="例如：体育竞技、学术讲座">
            </div>
            <div class="form-group">
                <label>参与人数</label>
                <!-- 【修改点6：前端增加人数上限限制】 -->
                <input type="number" id="join_num" required min="1" max="9999" placeholder="1-9999整数">
            </div>
            <button type="submit">提交登记</button>
        </form>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>活动名称</th>
                    <th>活动类型</th>
                    <th>参与人数</th>
                </tr>
            </thead>
            <tbody id="activityList"></tbody>
        </table>
    </div>
    <script>
        window.onload = fetchActivities;
        document.getElementById('activityForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const msgDiv = document.getElementById('formMsg');
            msgDiv.className = 'msg';
            const name = document.getElementById('activity_name').value.trim();
            const type = document.getElementById('activity_type').value.trim();
            const num = parseInt(document.getElementById('join_num').value);
            
            // 【修改点3：前端加强空输入拦截】纯空格输入直接拦截
            if (!name || !type) {
                msgDiv.textContent = '活动名称和活动类型不能为空或纯空格！';
                msgDiv.className = 'msg error';
                return;
            }
            // 【修改点4：前端增加人数上限校验】
            if (isNaN(num) || num <= 0 || num > 9999) {
                msgDiv.textContent = '参与人数必须是1-9999的整数！';
                msgDiv.className = 'msg error';
                return;
            }
            try {
                const response = await fetch('/api/activity/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ activity_name: name, activity_type: type, join_num: num })
                });
                const data = await response.json();
                if (response.ok) {
                    msgDiv.textContent = '登记成功！';
                    msgDiv.className = 'msg success';
                    document.getElementById('activityForm').reset();
                    fetchActivities();
                } else {
                    const errMsg = data.detail ? (Array.isArray(data.detail) ? data.detail.map(e => e.msg).join('; ') : data.detail) : '提交失败';
                    msgDiv.textContent = '错误：' + errMsg;
                    msgDiv.className = 'msg error';
                }
            } catch (error) {
                msgDiv.textContent = '网络请求异常！';
                msgDiv.className = 'msg error';
            }
        });
        async function fetchActivities() {
            try {
                const response = await fetch('/api/activity/list');
                const data = await response.json();
                const tbody = document.getElementById('activityList');
                tbody.innerHTML = '';
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4">暂无活动记录</td></tr>';
                    return;
                }
                data.forEach(item => {
                    const tr = document.createElement('tr');
                    // 【修改点5：修复XSS隐患】不使用 innerHTML 拼接，改用安全的 textContent 赋值
                    const tdId = document.createElement('td');
                    tdId.textContent = item.id; 
                    const tdName = document.createElement('td');
                    tdName.textContent = item.activity_name;
                    const tdType = document.createElement('td');
                    tdType.textContent = item.activity_type;
                    const tdNum = document.createElement('td');
                    tdNum.textContent = item.join_num;
                    
                    tr.appendChild(tdId);
                    tr.appendChild(tdName);
                    tr.appendChild(tdType);
                    tr.appendChild(tdNum);
                    tbody.appendChild(tr);
                });
            } catch (error) {
                console.error('获取列表失败:', error);
            }
        }
    </script>
</body>
</html>
    """
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content.strip())

app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# ---------------- 数据库配置 ----------------
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",       
    "password": "123456", 
    "database": "test_db",
    "charset": "utf8mb4"
}

def get_db_connection():
    # 【修改点1：增加性能警告注释】生产环境必须替换为连接池(如DBUtils或SQLAlchemy)，避免连接数打满
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")

# ---------------- Pydantic 模型 (参数校验) ----------------
class ActivityCreate(BaseModel):
    # 【修改点2：补齐业务参数校验逻辑】增加最大长度限制和参与人数上限(le=9999)
    activity_name: str = Field(..., min_length=1, max_length=100, description="活动名称不能为空且最长100字符")
    activity_type: str = Field(..., min_length=1, max_length=50, description="活动类型不能为空且最长50字符")
    join_num: int = Field(..., gt=0, le=9999, description="参与人数必须大于0且上限9999")

    # 【修改点3：后端加强空输入拦截】使用 field_validator 拦截纯空格输入
    @field_validator('activity_name', 'activity_type')
    @classmethod
    def strip_and_validate_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('不能输入纯空格')
        return v

class ActivityResponse(BaseModel):
    id: int
    activity_name: str
    activity_type: str
    join_num: int

# ---------------- 接口路由 ----------------
@app.post("/api/activity/add", response_model=ActivityResponse)
def add_activity(activity: ActivityCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 【修改点1：防SQL注入规范标注】严格使用参数化查询元组，严禁字符串拼接format或f-string
            sql = "INSERT INTO activity (activity_name, activity_type, join_num) VALUES (%s, %s, %s)"
            cursor.execute(sql, (activity.activity_name, activity.activity_type, activity.join_num))
            conn.commit()
            insert_id = cursor.lastrowid
            return {
                "id": insert_id,
                "activity_name": activity.activity_name,
                "activity_type": activity.activity_type,
                "join_num": activity.join_num
            }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"数据插入失败: {str(e)}")
    finally:
        conn.close()

@app.get("/api/activity/list", response_model=List[ActivityResponse])
def list_activities():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, activity_name, activity_type, join_num FROM activity ORDER BY id DESC"
            cursor.execute(sql)
            results = cursor.fetchall()
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据查询失败: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
