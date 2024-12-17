from groq import Groq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from deepgram import DeepgramClient, SpeakOptions
from dotenv import load_dotenv
import os
import speech_recognition as sr
from colorama import Fore, Style
import pygame
import time
import logging
import traceback
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger().setLevel(logging.INFO)

load_dotenv(dotenv_path='../.env')

# Load API keys
groq_api_key = os.getenv('GROQ_API_KEY')
deepgram_api_key = os.getenv('DEEPGRAM_API_KEY')

def record_audio(file_path):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        logging.info("Recording started")
        audio_data = recognizer.listen(source)
        logging.info("Recording complete")
        with open(file_path, "wb") as audio_file:
            audio_file.write(audio_data.get_wav_data())
            
def play_audio(file_path):
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)
    pygame.mixer.quit()
            
def transcribe_audio(client, file_path):
    # Feed Groq client
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file)
    return transcription.text

def text_to_speech(client, file_path, content):
    # Feed Deepgram Client
    options = SpeakOptions(
                model="aura-zeus-en",
                encoding="linear16",
                container="wav"
            )
    speak_option = {"text": content}
    response = client.speak.v("1").save(file_path, speak_option, options)
    
def initialize_clients(groq_api_key, deepgram_api_key):
    client = Groq(api_key=groq_api_key)
    llm = ChatGroq(model="Gemma2-9b-It", groq_api_key=groq_api_key)
    deepgram_client = DeepgramClient(api_key = deepgram_api_key)
    return client, llm, deepgram_client

store = {}

def generate_response(prompt, llm, parser, question, session_id: str):
    """
    Generate a response using a prompt, LLM, and parser, while maintaining session chat history.

    Args:
        prompt: A Runnable prompt (or chain component).
        llm: The language model to use.
        parser: A parser for post-processing.
        question: The user question to respond to.
        session_id: A unique identifier for the chat session.

    Returns:
        The AI's response.
    """

    # Retrieve or initialize the chat history for the session
    def get_by_session_id(session_id: str):
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]

    session_history = get_by_session_id(session_id)

    # Add the user's question to the chat history
    session_history.add_message(HumanMessage(content=question))

    # Create the chain
    chain = prompt | llm | parser

    # Define a callable to retrieve session history
    def get_session_history():
        return session_history

    # Wrap the chain with RunnableWithMessageHistory
    memory_model = RunnableWithMessageHistory(chain, get_session_history)

    # Define configuration for the session
    config = {"configurable": {"session_id": session_id}}

    # Invoke the chain with the user's question
    answer = memory_model.invoke([HumanMessage(content=question)], config=config)

    # Add the AI's response to the chat history
    session_history.add_message(AIMessage(content=answer))

    return answer

def main():
    client, llm, deepgram_client = initialize_clients(groq_api_key, deepgram_api_key)

    prompt=ChatPromptTemplate.from_messages(
    [
        ("system","You are a helpful assistant in handling customer queries related online shopping. Please respond to user queries. Don't use emojis."),
        ("user","Question:{question}")
    ]
    )

    parser=StrOutputParser()

    input_audio = "input.wav"
    output_audio = "output.wav"
    
    while True:
        try:
            record_audio(input_audio)

            user_input = transcribe_audio(client, input_audio)
            logging.info(Fore.GREEN + "User: " + user_input + Style.RESET_ALL)

            response = generate_response(prompt, llm, parser, user_input, session_id="user123")
            time.sleep(1)
            logging.info(Fore.CYAN + "Bot: " + response + Style.RESET_ALL)

            text_to_speech(deepgram_client, output_audio, response)
            play_audio(output_audio)
        
        except Exception as e:
            # Log the specific error and traceback for debugging
            logging.error(Fore.RED + "An error occurred:")
            logging.error(Fore.RED + traceback.format_exc())

            # Optionally, you can break the loop or continue based on the error
            break 

if __name__ == "__main__":
    main()