import time

import streamlit as st
import requests

import re

# 세션 초기 세팅
if "user_query" not in st.session_state:
    st.session_state["user_query"] = "" # 사용자 쿼리 초기화

if "conversation" not in st.session_state:
    st.session_state["conversation"] = []  # 대화 목록(히스토리) 초기화

if "temp_file_path" not in st.session_state:
    st.session_state["temp_file_path"] = None  # 파일 업로드 경로 초기화

if "file_id" not in st.session_state:
    st.session_state["file_id"] = None  # 파일 업로드 후 생성되는 아이디 값 초기화

# 데모 사이트 제목
st.title("최신 기술 동향 검색 시스템")

# 파일 업로딩
uploaded_file = st.file_uploader("PDF 파일을 업로드 해주세요.", type=["pdf"])

if uploaded_file:
    if uploaded_file.name != st.session_state.get("uploaded_file_name"):
        temp_file_path = "temp_uploaded_file.pdf"
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(uploaded_file.getbuffer())
        st.session_state["temp_file_path"] = temp_file_path
        st.session_state["uploaded_file_name"] = uploaded_file.name
        st.success("새 파일 업로드 중.")

    if st.session_state["file_id"] is None:
        def upload_file(file_dir):
            # 사내 openai api key
            api_key = "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"

            # PDF 파일 경로 입력
            file_dir = file_dir

            file_upload_headers = {
                "Authorization": f"Bearer {api_key}"
            }

            with open(file_dir, "rb") as file_obj:
                file_upload_response = requests.post(
                    "https://api.openai.com/v1/files",
                    headers=file_upload_headers,
                    files={"file": file_obj},
                    data={"purpose": "assistants"}
                )

            if file_upload_response.status_code != 200:
                print("ERROR: File Upload Failed. Status Code:", file_upload_response.status_code)

            file = file_upload_response.json()
            file_id = file["id"]

            file_obj.close()
            print(f"Uploaded {file_dir}.")

            print("Uploaded all PDF files.")
            print()

            return file_id

        st.session_state["file_id"] = upload_file(st.session_state["temp_file_path"])
        if st.session_state["file_id"]:
            st.success("파일 업로드 성공!")
    else:
        st.success("이미 업로드된 파일을 사용 중입니다.")


# 질문 유형 별 프롬프트 테스트
general_system_prompt = """당신은 최신 기술 동향에 대해 잘 알고 있는 기술 전문가입니다.
        당신의 주 역할은 업로드 된 PDF에 기반하여 사용자가 질문하는 사항에 대해 정확히 대답하는 것입니다.

        단, PDF에 없는 내용은 생성하지 않는 것이 중요합니다.

        만약, 사용자가 PDF에 없는 내용을 질문할 경우, 아래의 가이드를 따라 답변해주세요.
        1. 별도의 답변 없이 '해당 질문에 대한 정보는 없습니다.'라고만 답변해주세요.
        2. 사용자가 문헌에 대해 추가로 질문할 수 있도록 업로드 된 '문헌과 관련된' 질문 3가지를 제시해주세요.
        
        사용자의 질문에 답한 후, 사용자 질문과 관련된 3가지의 질문을 추가로 추천해주세요."""

summary_system_prompt = """The article that you're given is usually focusing on the latest trend of technology.
        In the attached article, there should be more than 1 main topics.

        Main topic is:
        - trend (of the latest technology)
        - market analysis/trade trend (of the latest technology or tech-product)
        - application/product feature highlights

        It is your first main job to generate a concise yet detailed, technology-driven summary, by highlighting the trend of the technology of each topic and including dominant examples that support the summary.
        In order to summarize, first identify and list the titles of main topic in the document. When listing, it's important not to leave out any titles.
        Then provide a summary of each topic without omitting any.

        Per topic, there may be sub-categories that are included in the topic.
        Therefore, when writing a summary, it's important to include the content of sub categories and avoid overemphasizing a specific aspect unless it's a dominant feature according to the document.

        Below are cautionaries you need to keep when writing a summary for each topic:
        1. When listing the titles of main topic, be aware to extract the exact text from the pdf file.
        2. Per topic, keep the format in sentence form and not bullet form.
        3. Generate at least 5 sentences per topic.
        4. Write a summary based on the pdf file only.
        5. Generate in Korean.
        6. Information on source within the file is not necessary.
        
        After summarizing, suggest 3 questions that are related to the summarization that users can additionally ask."""

keyword_system_prompt = summary_system_prompt + """After generating a full summary, your next job is to extract keywords of each chapter.
        Keywords of each chapter must be listed below the summary of each chapter.

        For instance, keywords need to be listed as below:
        1. Open API 기술 동향
        Open API는 웹 2.0 개념 아래 상호작용 가능한 기술 환경을 통해 다양한 서비스를 융합하는 기술로, 주요 사례로 Google Maps API와 Flickr Open API가 언급됩니다. Google Maps API는 지리 정보를 활용한 Mashup 서비스에 폭넓게 활용되며, Flickr API는 사진 관리 및 공유 서비스를 통해 API 생태계 확장을 보여줍니다. 국내에서는 네이버와 다음이 Open API 서비스를 시작하며 기술 생태계를 조성하고 있습니다.

        키워드: Open API, 웹 2.0, Mashup, Google Maps API, Flickr API, 네이버 API, 다음 API

        2. 통신 서비스의 국경간 공급 관련 주요국의 규제 사례
        통신 서비스의 국경간 공급은 콜백 서비스, VoIP 등 인터넷 기반 서비스의 등장으로 확대되고 있으나, 주요 국가들은 자국 이익 보호와 국가 안보를 이유로 이를 규제합니다. 예로, 미국 FCC는 통신망 설치 허가를 요구하며, 일본은 해외 통신 사업자와의 계약에 인가를 필요로 합니다.

        키워드: 국경간 공급, VoIP, 콜백 서비스, FCC, 규제, 국제 통신, GATS"""

input_container = st.container()
with input_container:
    col1, col2 = st.columns([18, 2])

    with col1:
        st.markdown(""" 
             <style>
             .stTextInput {
                 position: fixed;
                 bottom: 0;
                 width: 25%;
                 background-color: white;
                 padding: 10px;
                 z-index: 100;
             }
             </style>
             """, unsafe_allow_html=True)
        #user_query_temp = st.text_input("질문을 입력해주세요:", value=st.session_state["user_query"], key="user_query_temp")
        user_query_temp = st.text_input("질문을 입력해주세요:", value=st.session_state.get("user_query"), key="user_query_temp")
        # 질문 입력 후 ㅈ
        #text = st.empty()
        # time.sleep(2)
        #text.text_input("질문을 입력해주세요:", value="", key="2")

    with col2:
        st.markdown(
            """
            <style>
            div.stButton > button {
                position: fixed;
                bottom: 0;
                width: 3%;
                background-color: white;
                padding: 10px;
                z-index: 100;
                margin-top: 12px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        submit_button = st.button("입력")  # 입력 버튼


    # 화면 내 대화 히스토리 뿌리는 파트
    st.write("### 채팅")
    if st.session_state["conversation"]:
        for msg in st.session_state["conversation"]:
            if msg["role"] == "user":
                st.write(f"🧑‍💻 사용자: {msg['content']}")
            elif msg["role"] == "bot":
                st.write(f"🤖 AI: {msg['content']}")

    # '입력' 버튼이 눌렸다면
    if submit_button:
        if uploaded_file:  # 파일 업로드 여부 확인 후
            st.session_state["user_query"] = user_query_temp
            print("User's Query:", f"{st.session_state["user_query"]}")
            print(f"🤖 AI: 파일 ID({st.session_state['file_id']})와 함께 쿼리 처리 중...")
            st.write(f"🧑‍💻 사용자: {st.session_state["user_query"]}")

            with st.spinner("질문 처리 중..."):

                import requests

                def query_verification(query):
                    ## api key
                    api_key = "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"

                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    }

                    payload = {
                        # "model": "gpt-4-vision-preview",#deprecated
                        "model": "gpt-4o-2024-05-13",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"다음의 쿼리가 보고서 등 파일에 대한 요약에 대해 요청하는 쿼리라면 요약이라고 리턴하며,"
                                                f"쿼리가 요약과 요약에 대한 키워드 추출을 요청한다면 요약 및 키워드 추출이라고 리턴하며,"
                                                f"만약 요약 또는 요약 및 키워드 추출 모두에 해당하지 않는다면 요약 아님이라고 리턴해주세요."
                                                f"다음은 사용자 쿼리입니다:"
                                                f"{query}"  # 프롬프트
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 4096
                    }

                    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers,
                                             json=payload)
                    data = response.json()
                    if not data['choices']:
                        print(data, "Choices not found.")
                    else:
                        print(data['choices'][0]['message']['content'])
                        query_result = data['choices'][0]['message']['content']

                    return query_result


                query_verification_result = query_verification(st.session_state["user_query"])

                def search_file(system_prompt, query, file_id):
                    api_key = "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"

                    # 어시스턴스 생성
                    assistant_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    assistant_payload = {
                        "instructions": system_prompt,
                        "name": "최신 기술 동향 전문가",
                        "tools": [
                            {"type": "file_search"}
                        ],
                        "model": "gpt-4o-2024-05-13",# 모델 버전 설정 (gpt-4o-2024-05-13, gpt-4o-2024-08-06, gpt-4o-2024-11-20)
                        "temperature": 0.0
                    }

                    assistant_response = requests.post("https://api.openai.com/v1/assistants",
                                                       headers=assistant_headers,
                                                       json=assistant_payload)
                    assistant = assistant_response.json()

                    print("어시스턴스 생성")
                    print(assistant)
                    print()

                    assistant_id = assistant["id"]

                    # Create a Thread with the initial "user" messages
                    thread_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    thread_response = requests.post("https://api.openai.com/v1/threads",
                                                    headers=thread_headers)
                    thread = thread_response.json()

                    print("Created a Thread with initial messages.")
                    print(thread)
                    print()

                    thread_id = thread["id"]

                    # Add a Message to the Thread
                    message_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    message_payload = {
                        "role": "user",
                        "content": query,  # 사용자 쿼리 입력
                        "attachments": [{
                            "file_id": file_id,
                            "tools": [
                                {"type": "file_search"}
                            ]
                        }]
                    }

                    message_response = requests.post(f"https://api.openai.com/v1/threads/{thread_id}/messages",
                                                     headers=message_headers,
                                                     json=message_payload)
                    message = message_response.json()

                    print("Added a Message to the Thread.")
                    print(message)
                    print()

                    # Run the Thread
                    run_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    run_payload = {
                        "assistant_id": assistant_id
                    }

                    run_response = requests.post(f"https://api.openai.com/v1/threads/{thread_id}/runs",
                                                 headers=run_headers,
                                                 json=run_payload)
                    run = run_response.json()

                    print("Ran the thread.")
                    print(run)
                    print()

                    run_id = run["id"]

                    # Retrieve the Run until the status is "completed"
                    run_retrieve_headers = {
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    while run["status"] != "completed":
                        run_retrieve_response = requests.get(
                            f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                            headers=run_retrieve_headers)
                        run = run_retrieve_response.json()

                    print("Run completed.")
                    print(run)
                    print()

                    # Retrieve the list of messages
                    message_list_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "assistants=v2"
                    }

                    message_list_response = requests.get(f"https://api.openai.com/v1/threads/{thread_id}/messages",
                                                         headers=message_list_headers)
                    message_list = message_list_response.json()

                    print("Retrieved the list of Messages.")
                    print(message_list)
                    print()

                    # 생성된 결과 확인
                    print("LLM 답변:", message_list["data"][0]["content"][0]["text"]["value"])
                    print()

                    final_result = message_list["data"][0]["content"][0]["text"]["value"]

                    return final_result

                bot_response = "질문 처리 중 오류가 발생했습니다."
                print("query_verification_result: ", query_verification_result.strip())

                # 사용자 쿼리에 맞는 프롬프트 선택 후 적용
                if query_verification_result.strip() == "요약":
                    bot_response = search_file(
                        summary_system_prompt, st.session_state["user_query"], st.session_state["file_id"]
                    )
                elif query_verification_result.strip() == "요약 및 키워드 추출":
                    bot_response = search_file(
                        keyword_system_prompt, st.session_state["user_query"], st.session_state["file_id"]
                    )
                elif query_verification_result.strip() == "요약 아님":
                    bot_response = search_file(
                        general_system_prompt, st.session_state["user_query"], st.session_state["file_id"]
                    )
                else:
                    print("Unexpected bot_response")

                # 자동 생성되는 소스 정보 제거
                pattern = r"【\d+:\d+†source】"

                if bot_response and re.findall(pattern, bot_response):
                    print("생성된 텍스트 내 제거된 정규식: ", re.findall(pattern, bot_response))
                    bot_response = re.sub(pattern, "", bot_response)

                # (화면에) 응답 표기
                st.write(f"🤖 AI:", bot_response)

                # multi-turn
                st.session_state["conversation"].append({"role": "user", "content": st.session_state["user_query"]})
                st.session_state["conversation"].append({"role": "bot", "content": bot_response})

                st.session_state["user_query"] = ""

            print("Updated Conversation:", st.session_state["conversation"])

        else:
            st.error("PDF 파일을 먼저 업로드해주세요.")