# For prerequisites running the following sample, visit https://help.aliyun.com/document_detail/611472.html
import time
import json
from http import HTTPStatus
import dashscope


def call_with_messages():
    messages = [{'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': '如何做炒西红柿鸡蛋？'}]

    response = dashscope.Generation.call(
        dashscope.Generation.Models.qwen_turbo,
        messages=messages,
        result_format='message',  # set the result to be "message" format.
    )
    if response.status_code == HTTPStatus.OK:
        print(response)
    else:
        print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
            response.request_id, response.status_code,
            response.code, response.message
        ))


def call_with_prompt(prompt='如何做炒西红柿鸡蛋？'):
    start_time = time.time()
    response = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_max,
        prompt=prompt,
        temperature=1.2,
        # top_p=0.9,
    )
    end_time = time.time()
    print('调用模型时间消耗:', end_time - start_time)
    # 目前可用的model有：qwen-max,qwen-turbo,qwen-max-1201,qwen-max-longcontext
    # The response status_code is HTTPStatus.OK indicate success,
    # otherwise indicate request is failed, you can get error code
    # and message from code and message.
    if response.status_code == HTTPStatus.OK:
        print(response.output)  # The output text
        print(response.usage)  # The usage information
    else:
        print(response.code)  # The error code.
        print(response.message)  # The error message.
    return response.output.text


# 流式输出
def call_with_stream(prompt='如何做炒西红柿鸡蛋？'):
    messages = [
        {'role': 'user', 'content': prompt}]
    responses = dashscope.Generation.call(
        dashscope.Generation.Models.qwen_max,
        messages=messages,
        result_format='message',  # set the result to be "message" format.
        stream=True,
        incremental_output=True  # get streaming output incrementally
    )
    full_content = ''  # with incrementally we need to merge output.
    for response in responses:
        sin_response = response.output.choices[0]['message']['content']
        print('逐步输出结果：', sin_response)

        if response.status_code == HTTPStatus.OK:
            full_content += sin_response
            # print(response)
        else:
            print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                response.request_id, response.status_code,
                response.code, response.message
            ))
        yield sin_response
    # print('Full response:\n' + full_content)


if __name__ == '__main__':
    # call_with_messages()
    prompt = '你是一个软件工程师面试官，你精通python,java,go等各种语言，现在我需要你做一个面试官，基于数据库知识主题，随机给出1道面试题，请只给到面试题'
    """
    res = call_with_prompt(prompt)
    res = res.split('面试题：')[-1]
    print('res', res)
    """
    results = call_with_stream(prompt)
    for res in results:
        print(res)
