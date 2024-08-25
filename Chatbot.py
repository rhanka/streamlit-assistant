from openai import OpenAI
from openai import beta
import os
import uuid
import streamlit as st
import time
import urllib.request
import streamlit.components.v1 as components

assistant_id = os.environ.get("ASSISTANT_ID")

if os.environ["OPENAI_API_KEY"] is None or assistant_id is None:
    st.error("Environment variables for API keys are not set.")

with st.sidebar:
    st.sidebar.empty()
     # openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    "[Get an OpenAI API key](https://platform.openai.com/account/api-keys)"
    "[View the source code](https://github.com/rhanka/streamlit-assistant/blob/main/Chatbot.py)"

st.title("💬 Documentation Nethris")
nethris_base_url="https://clients.nethris.com/WebCommon/HelpFiles/CGI/FR/PAY/"
nethris_base_full_url="https://clients.nethris.com/WebCommon/HelpFiles/CGI/FR/PAY/index?"

client = OpenAI()
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0


if "assistant" not in st.session_state:
    # Load the previously created assistant
    st.caption("🚀 Poser une question à l'assistant de documentation !")
    st.session_state.assistant = beta.assistants.retrieve(assistant_id)

    # Create a new thread for this session
    st.session_state.thread = client.beta.threads.create(
        metadata={
            'session_id': st.session_state.session_id,
        }
    )
 
# If the run is completed, display the messages
elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    # Retrieve the list of messages
    st.session_state.messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )

    for thread_message in st.session_state.messages.data:
        for message_content in thread_message.content:
            # Access the actual text content
            message_content = message_content.text
            annotations = message_content.annotations
            citations = []

            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations):
                # Replace the text with a footnote

                cited_file=""
                # Gather citations based on annotation attributes
                if (file_citation := getattr(annotation, 'file_citation', None)):
                    cited_file = client.files.retrieve(file_citation.file_id)
                elif (file_path := getattr(annotation, 'file_path', None)):
                    cited_file = client.files.retrieve(file_path.file_id)
                cited_file = cited_file.filename.replace(".md", "")
                cited_url = f'{nethris_base_url}{cited_file}'
                cited_full_url = f'{nethris_base_full_url}{cited_file}'
                citation_url_short = f'[[{index}†]]({cited_url})'
                #citations.append(f'[[{index}†]{cited_file}]({cited_url})')
                citations.append({"file": cited_file, "url": cited_url, "full_url": cited_full_url})
                message_content.value = message_content.value.replace(annotation.text, f' {citation_url_short}')

            # Add footnotes to the end of the message before displaying to user
            # message_content.value += '\n\n' + '\n'.join(citations)
            message_content.citations = citations

    # Display messages
    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    st.markdown(content_part.text.value)
                    #st.markdown('\n---\n'.join(content_part.text.citations))
                    #str.write(content_part.text.citations)
                    index=0
                    for citation in content_part.text.citations:
                        with st.popover(f'[{index}†] {citation["file"]}'):
                            iframe_code = f"""
                                <iframe src="{citation["url"]}" width="100%" height="500px" frameborder="0" style="border:0;" allowfullscreen></iframe>
                            """
                            components.html(iframe_code, height=500)
                            # with urllib.request.urlopen(citation["url"]) as response:
                            #     st.write(response.read())
                            st.write(citation["full_url"])
                        index+=1

if prompt := st.chat_input("Poser une question relative à la documentation Nethris"):
    with st.chat_message('user'):
        st.write(prompt)

    # Add message to the thread
    st.session_state.messages = client.beta.threads.messages.create(
        thread_id=st.session_state.thread.id,
        role="user",
        content=prompt
    )

    # Do a run to process the messages in the thread
    st.session_state.run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id,
    )
    if st.session_state.retry_error < 3:
        time.sleep(1) # Wait 1 second before checking run status
        st.rerun()
                    
# Check if 'run' object has 'status' attribute
if hasattr(st.session_state.run, 'status'):
    # Handle the 'running' status
    if st.session_state.run.status == "running":
        with st.chat_message('assistant'):
            st.write("Thinking ......")
        if st.session_state.retry_error < 3:
            time.sleep(1)  # Short delay to prevent immediate rerun, adjust as needed
            st.rerun()

    # Handle the 'failed' status
    elif st.session_state.run.status == "failed":
        st.session_state.retry_error += 1
        with st.chat_message('assistant'):
            if st.session_state.retry_error < 3:
                st.write("Run failed, retrying ......")
                time.sleep(3)  # Longer delay before retrying
                st.rerun()
            else:
                st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

    # Handle any status that is not 'completed'
    elif st.session_state.run.status != "completed":
        # Attempt to retrieve the run again, possibly redundant if there's no other status but 'running' or 'failed'
        st.session_state.run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()
