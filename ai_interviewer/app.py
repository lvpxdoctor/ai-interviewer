# 用fastapi实现以下的接口
# 携带了current_topic(希望得到的首次面试题的类型)
# 预期拿到该类型下的一道面试题
# 传入：
# {
#    "current_topic": "数据库知识",
#    "history_question_and_answer": [],
#    "is_deep_base_history": 0  # 是否希望基于同类型的历史数据，来生成新的面试题,0是不基于历史 1是基于历史
# } 
# 输出：
# {
#    "current_topic": "数据库知识",
#    “interview question”: "question1"
# } 
import time
import json
from flask import Flask, request, jsonify, Response, stream_with_context
from ali_dashscope.qwen import call_with_prompt, call_with_stream

app = Flask(__name__)

@app.route('/')
def health_check():
    return 'ok'


NOT_HISTTORY_PROMPT = '你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，基于「{question_type}」主题，给出1道面试题，请只给到面试题'
NOT_HISTTORY_STREAM_PROMPT = '你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，基于「{question_type}」主题，给出1道面试题，请只给到面试题, 不要有「面试题」的前缀'
HISTTORY_PROMPT = """
你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，
基于「{question_type}」主题，和面试题「{interview_question}」，对应回答「{interview_answer}」
请先对回答进行简短评估，如果回答特别短，生成的评价要多鼓励一下，
然后再给出面试题,评价要用语气柔和且简短，不要太长
请给出1道更深层次的面试题，一定和主题相关
返回json格式，key是「评价」「深层次面试题」
"""
HISTTORY_STREAM_PROMPT = """
你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，
基于「{question_type}」主题，和面试题「{interview_question}」，对应回答「{interview_answer}」
请生成一道更深层次的面试题，一定和主题相关，和上面的面试题有关，如果上面的回答很短，就只基于上面面试题生成，
只生成一道题，简短点，不要有多余的阐述
给到的面试题，不要有「面试题」的前缀
"""
EVALUATION_STREAM_PROMPT = """
你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，
基于「{question_type}」主题，和面试题「{interview_question}」，对应回答「{interview_answer}」
请对回答进行简短评估，如果回答特别短，生成的评价要多鼓励一下,
给到的评估，一定要简约，不超过50字，不要有多余的阐述,语气要人性化，
给到的评估，不要有「评估」的前缀
"""
FEEDBACK_PROMPT = """
你是一个软件工程师面试官，你精通python,java,go等各种语言, 以下是面试者回答的几个问题，请给出反馈
{feedback_qa}
反馈要求：
提供反馈时，先用简短话术总结面试者的表现，0-10分，无需给出理由
提供反馈时，它将始终提供0至10的评分，并对评分进行理由说明
提供反馈时，它总是使用清晰的结构
提供反馈时，将面试者称为您
总的不超过100字
"""
FEEDBACK_STREAM_PROMPT = """
你是一个软件工程师面试官，你精通python,java,go等各种语言, 以下是面试者回答的几个问题，请给出反馈
{feedback_qa}
反馈要求：
提供反馈时，先用简短话术总结面试者的表现，0-10分，无需给出理由
提供反馈时，它将始终提供0至10的评分，并对评分进行理由说明
提供反馈时，它总是使用清晰的结构
提供反馈时，将面试者称为您
总的不超过100字, 不要有「反馈」的前缀
"""
# 提供反馈时，要提供详细反馈
# 提供反馈是，要提供具体的例子
FEEDBACK_QA = """\n面试题{index}: {question} \n 对应回答：{answer} """

@app.route('/interview-question', methods=['POST'])
def get_interview_question():
    data = request.get_json()
    current_topic = data.get('current_topic', '数据库知识')
    is_deep_base_history = data.get('is_deep_base_history', 0)
    history_question_and_answer = data.get('history_question_and_answer', [])
    
    # 评价的默认值
    evaluation = ''

    # 这里应该是你的逻辑来生成面试题
    # 为了简单起见，我们只是返回一个固定的问题
    if not is_deep_base_history or not history_question_and_answer:
        not_history_prompt = NOT_HISTTORY_PROMPT.format(question_type=current_topic)
        question = call_with_prompt(not_history_prompt)
        question = question.split('面试题：')[-1]
    else:
        # for i in reversed(history_question_and_answer):
        #     if current_topic in i[-1]:
        #         history_question_and_answer = i[0]
        #         history_answer = i[1]
        #         break
        #     else:
        #         history_question_and_answer = ''
        #         history_answer = ''
        #         continue
        # 如果上一个主题是同一个，且is_deep_base_history=1, 则进行深度问题推荐
        i = history_question_and_answer[-1]
        if current_topic in i[-1]:
            history_question_and_answer = i[0]
            history_answer = i[1]
        else:
            history_question_and_answer = ''
            history_answer = ''

        # 异常情况处理
        if not history_question_and_answer:
            response = json.dumps({
                'current_topic': current_topic,
                'interview_question': '没有找到历史问答的相关主题，无法给到新的面试题',
                'evaluation': '' # 增加对上个题的评价

            }, ensure_ascii=False)
            return response     
        history_prompt = HISTTORY_PROMPT.format(
            question_type=current_topic, interview_question=history_question_and_answer, 
            interview_answer=history_answer)
        print(f'{time.time()},history_prompt:', history_prompt)
        question = call_with_prompt(history_prompt)
        print('完整的回答question:', question)
        question = question.replace('json', '').replace('```', '')
        question = eval(question)
        evaluation = question.get('评价', '')
        question = question.get('深层次面试题', '')

    # response = jsonify({
    #     'current_topic': current_topic,
    #     'interview question': question
    # })

    response = json.dumps({
        'current_topic': current_topic,
        'interview_question': question,
        'evaluation': evaluation # 增加对上个题的评价

    }, ensure_ascii=False)
    print(f'{time.time()},response:', response)
    return response


@app.route('/interview-question-stream', methods=['POST'])
def get_interview_question_stream():
    data = request.get_json()
    current_topic = data.get('current_topic', '数据库知识')
    is_deep_base_history = data.get('is_deep_base_history', 0)
    history_question_and_answer = data.get('history_question_and_answer', [])
    
    # 这里应该是你的逻辑来生成面试题
    # 为了简单起见，我们只是返回一个固定的问题
    if not is_deep_base_history or not history_question_and_answer:
        not_history_prompt = NOT_HISTTORY_STREAM_PROMPT.format(question_type=current_topic)
        print('独立面试题:', not_history_prompt)
        questions = call_with_stream(not_history_prompt)
        # question = question.split('面试题：')[-1]
        return Response(questions, mimetype='text/plain')

    else:
        # 如果上一个主题是同一个，且is_deep_base_history=1, 则进行深度问题推荐
        i = history_question_and_answer[-1]
        if current_topic in i[-1]:
            history_question_and_answer = i[0]
            history_answer = i[1]
        else:
            history_question_and_answer = ''
            history_answer = ''

        # 异常情况处理
        if not history_question_and_answer:
            questions = '没有找到历史问答的相关主题，无法给到新的面试题'
            return Response(questions, mimetype='text/plain')     
        history_prompt = HISTTORY_STREAM_PROMPT.format(
            question_type=current_topic, interview_question=history_question_and_answer, 
            interview_answer=history_answer)
        print(f'{time.time()},history_prompt:', history_prompt)
        questions = call_with_stream(history_prompt)
        print('questions类型：', type(questions))
        return Response(questions, mimetype='text/plain')
    

@app.route('/interview-evaluation-stream', methods=['POST'])
def get_interview_evaluation_stream():
    data = request.get_json()
    question_type = data.get('question_type', '')
    interview_question = data.get('interview_question', '')
    interview_answer = data.get('interview_answer', '')
    
    if not question_type:
        return Response('没有找到历史问答的相关主题，无法给到评估', mimetype='text/plain')
    elif not interview_question:
        return Response('没有找到历史问答的相关面试题，无法给到评估', mimetype='text/plain')
    elif not interview_answer:
        return Response('没有找到历史问答的相关回答，无法给到评估', mimetype='text/plain')
    else:
        not_history_prompt = EVALUATION_STREAM_PROMPT.format(
            question_type=question_type,
            interview_question=interview_question,
            interview_answer=interview_answer)
        print('评价:', not_history_prompt)
        questions = call_with_stream(not_history_prompt)
        return Response(questions, mimetype='text/plain')


@app.route('/interview-feedback', methods=['POST'])
def get_feedback():
    """
    通过面试的问答给到面试者反馈
    """
    data = request.get_json()
    history_question_and_answer = data.get('history_question_and_answer', [])
    if not history_question_and_answer:
        return Response('没有历史问答，无法给到反馈', mimetype='text/plain')
    feedback_qa = ''
    for index, item in enumerate(history_question_and_answer):
        question = item[0]
        answer = item[1]
        feedback_prompt = FEEDBACK_QA.format(index=index+1, question=question, answer=answer)
        feedback_qa += feedback_prompt
    feedback_prompt = FEEDBACK_PROMPT.format(feedback_qa=feedback_qa)
    feedback = call_with_prompt(feedback_prompt)
    feedback = feedback.split('反馈：')[-1].strip()

    response = json.dumps({
        'feedback_result': feedback
        }, ensure_ascii=False)

    return response

@app.route('/interview-feedback-stream', methods=['POST'])
def get_feedback_stream():
    """
    通过面试的问答给到面试者反馈
    流式处理
    """
    data = request.get_json()
    history_question_and_answer = data.get('history_question_and_answer', [])
    if not history_question_and_answer:
        return {'feedback_result': '没有历史问答，无法给到反馈'}
    feedback_qa = ''
    for index, item in enumerate(history_question_and_answer):
        question = item[0]
        answer = item[1]
        feedback_prompt = FEEDBACK_QA.format(index=index+1, question=question, answer=answer)
        feedback_qa += feedback_prompt
    feedback_prompt = FEEDBACK_STREAM_PROMPT.format(feedback_qa=feedback_qa)
    feedback = call_with_stream(feedback_prompt)
    return Response(feedback, mimetype='text/plain')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
