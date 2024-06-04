from fastapi import Request, FastAPI
from openai import OpenAI
import asyncio
import queue as q
import os

client = OpenAI(api_key='')
assistant_id = ''
id_dict = {}
app = FastAPI()

##########서버생성##########################
@app.get("/")
async def root():
    return {"message": "kakaoTest"}

@app.post("/chat/")
async def chat(request: Request):
    kakaorequest = await request.json()    
    # print('\n\n kakaorequest:', kakaorequest)
    # utterance = kakaorequest["userRequest"]["utterance"]
    # print('utterance:', utterance)
    return await main_chat(kakaorequest)
############################################


async def text_response_format(bot_response):
    print("\n text_response_format start")
    # 챗봇 응답을 카카오톡 플러스친구 API에 맞는 형식으로 변환
    response = {'version': '2.0', 'template': {'outputs': [{"simpleText": {"text": bot_response}}], 'quickReplies': []}}
    return response

async def timeover():
    print("\n timeover start")
    response = {"version":"2.0","template":{
      "outputs":[
         {
            "simpleText":{
               "text":"대화중에 미안해.\n아래 말풍선을 눌러줘👆"
            }
         }
      ],
      "quickReplies":[
         {
            "action":"message",
            "label":"말풍선🎈",
            "messageText":":)"
         }]}}
    return response


lock = asyncio.Lock()

test = {}

async def get_text_from_gpt(user_id, prompt):
    print("\n get_text_from_gpt start")
    print("\n get_text_from_gpt user_id : ",user_id)
    print(" get_text_from_gpt prompt : ",prompt)
    
    async with lock:
    # 사용자마다의 스레드 ID를 가져오거나 생성
        thread_id = id_dict.get(user_id)

        # 새로운 사용자인 경우에 대한 처리
        if thread_id is None:
            thread = client.beta.threads.create()
            thread_id = thread.id
            id_dict[user_id] = thread_id

        # 사용자의 질문을 OpenAI에 전달하고 답변을 받음
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == "completed":
                break
            else:
                await asyncio.sleep(1)

        # 답변을 가져오기
        thread_messages = client.beta.threads.messages.list(thread_id)
        # print(" \n\n thread_messages : ", thread_messages)
        # print(" \n\n result thread_id :", thread_id)
        result = thread_messages.data[0].content[0].text.value 

        print(" gpt result : ", result)
        test[user_id] = result
        print(" gpt test : " , test)
        return result



async def main_chat(kakaorequest):
    # 대화 시작 시간 기록
    start_time = asyncio.get_event_loop().time()
    run_flag = False
    # 로그 파일 경로 설정    
    cwd = os.getcwd()
    
    # 응답 결과를 저장하기 위한 텍스트 파일 생성
    user_id = kakaorequest["userRequest"]["user"]["id"]

    # 응답을 저장하는 큐 생성
    response_queue = q.Queue()
    
    # OpenAI 답변을 처리하는 비동기 작업 생성
    request_respond = asyncio.create_task(response_openai(kakaorequest, response_queue)) # , filename

    # 3.5초 동안 대기
    while (asyncio.get_event_loop().time() - start_time < 4):
        if not response_queue.empty():
            # 3.5초 안에 답변이 완성되면 바로 값 리턴
            response = response_queue.get()
            text = response['template']['outputs'][0]['simpleText']['text']

            
            # 3.5초 안에 대답이 왔을 때, test에 저장된 값 비워주기            
            key_to_pop = None
            for key, value in test.items():
                if value == text:
                    key_to_pop = key
                    break            
            if key_to_pop:
                test.pop(key_to_pop)                
            print("\n main_chat after pop test : ", test)
            
            run_flag= True
            break        
            
        await asyncio.sleep(0.1)

    # 3.5초 내 답변이 생성되지 않을 경우
    if run_flag== False:     
        response = await timeover()

    return response

async def response_openai(request, response_queue):  #, filename
    print("\n response_openai start")
    # 사용자가 답변 확인 버튼을 클릭한 경우
    if ':)' in request["userRequest"]["utterance"]:
        user_id = request["userRequest"]["user"]["id"]
        print("\n response user_id = ", user_id)        
        print("\n response test = ", test)
        a = test.pop(user_id, None)
        print("\n response a = ", a)
        
        
        # 텍스트 파일 내 저장된 정보가 있을 경우
        if a == None:
            pass    
        else:
            bot_res = a[0:]
            response_queue.put(await text_response_format(bot_res))
            # dbReset(filename)
    # OpenAI에 질문을 전달하고 응답을 큐에 추가
    else:       
        prompt = request["userRequest"]["utterance"]
        print("\n response prompt : ", prompt)
        user_id = request["userRequest"]["user"]["id"]
        bot_res = await get_text_from_gpt(user_id, prompt)
        response_queue.put(await text_response_format(bot_res))

    return response_queue