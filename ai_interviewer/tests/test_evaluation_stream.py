import requests

url = 'http://127.0.0.1:5000/interview-evaluation-stream'

data = {
    'question_type': '数据库知识',
    'interview_question': '请问您在设计数据库时，如何避免数据冗余和更新异常？请详细说明。',
    'interview_answer': '1、ddl要符合规范 2、冷热字段分离 3、使用外键来约束'
}

results = requests.post(url, json=data, stream=True)
for res in results:
    print(res.decode('utf-8', errors='ignore'))
