import json
import requests
import pyttsx3
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import os
import time
import subprocess

# Define the models you want to use
models = ["llama3.1", "llama3.1"]
current_model_index = 0

# Get voices once
temp_engine = pyttsx3.init()
voices = temp_engine.getProperty('voices')
voice_ai1 = voices[0].id
voice_ai2 = voices[1].id
temp_engine.stop()

# Separate memories for each AI
memories = {}

preset_prompts = {
    "Prompt 1": "Hello {ai1_name}! I'm {ai2_name}. Let's have a talkative conversation. Maybe we can talk about our favorite things. What do you think?",
    "Prompt 2": "Hello {ai1_name}! I'm {ai2_name}. Let's have a talkative conversation. Maybe we can give each other names and talk about our favorite things. What do you think?",
}

def chat(model, messages):
    try:
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        )
        r.raise_for_status()
    except Exception as err:
        print(f"[ERROR] Request failed: {err}")
        return None

    output = ""
    message = {"role": "assistant", "content": ""}

    for line in r.iter_lines():
        if not line:
            continue

        try:
            body = json.loads(line.decode('utf-8'))
        except:
            continue

        if "error" in body:
            print("[ERROR]", body["error"])
            return None

        if "message" in body:
            content = body["message"].get("content", "")
            output += content

        if body.get("done", False):
            message["content"] = output
            return message

    # fallback if "done" never comes
    if output:
        message["content"] = output
        return message

    return None


def save_conversation(all_messages):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = "ollama_talk_convos"
    filename = f"{folder}/conversation_{timestamp}.txt"
    os.makedirs(folder, exist_ok=True)

    with open(filename, 'w', encoding='utf-8') as file:
        for message in all_messages:
            role = "User" if message["role"] == "user" else "Assistant"
            file.write(f"{role}: {message['content']}\n")


def speak(text, voice_id):
    # Clean text
    text_to_speak = re.sub(r'\*[^*]*\*', '', text)
    text_to_speak = re.sub(r'[\U00010000-\U0010FFFF]', '', text_to_speak)
    text_to_speak = re.sub(r'_', ' ', text_to_speak)

    # Escape for command line
    text_to_speak = text_to_speak.replace('"', '')

    # Windows built-in TTS (PowerShell)
    ps_command = f'''
    Add-Type -AssemblyName System.Speech;
    $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;
    $speak.Rate = 5;
    $speak.Volume = 100;
    $speak.Speak("{text_to_speak}");
    '''

    subprocess.run(["powershell", "-Command", ps_command])


def start_conversation(prompt, ai1_name, ai2_name):
    global current_model_index

    if ai1_name not in memories:
        memories[ai1_name] = []
    if ai2_name not in memories:
        memories[ai2_name] = []

    messages = []
    all_messages = []

    if prompt in preset_prompts:
        user_input = preset_prompts[prompt].format(ai1_name=ai1_name, ai2_name=ai2_name)
    else:
        user_input = prompt

    messages.append({"role": "user", "content": user_input})
    all_messages.append({"role": "user", "content": user_input})

    speak(user_input, voice_ai1)

    try:
        conversation_active = True
        while conversation_active:

            if current_model_index == 0:
                model = models[current_model_index]
                model_label = ai1_name
                next_voice = voice_ai2
            else:
                model = models[current_model_index]
                model_label = ai2_name
                next_voice = voice_ai1

            current_model_index = (current_model_index + 1) % 2

            current_memory = memories[model_label]
            merged_messages = current_memory + messages

            message = chat(model, merged_messages)

            if not message:
                print(f"[ERROR] No response from {model}")
                continue

            print(f"\n{model_label}: {message['content']}\n")
            speak(message['content'], next_voice)

            messages.append({"role": "assistant", "content": message['content']})
            all_messages.append({"role": "assistant", "content": message['content']})

            current_memory.append({"role": "assistant", "content": message['content']})

            next_message = {"role": "user", "content": message["content"]}
            messages = [next_message]

            if len(all_messages) >= 20:
                conversation_active = False

    finally:
        save_conversation(all_messages)


def create_gui():
    global ai1_type_entry, ai2_type_entry

    root = tk.Tk()
    root.title("AI Conversation Starter")
    root.geometry("600x400")

    label = tk.Label(root, text="Choose a prompt to start the conversation:")
    label.pack(pady=10)

    name_frame = tk.Frame(root)
    name_frame.pack(pady=10)

    ai1_name_entry = tk.Entry(name_frame)
    ai1_name_entry.insert(0, "Bob")
    ai1_name_entry.grid(row=0, column=1)

    ai2_name_entry = tk.Entry(name_frame)
    ai2_name_entry.insert(0, "Joey")
    ai2_name_entry.grid(row=1, column=1)

    ai1_type_entry = tk.Entry(name_frame)
    ai1_type_entry.insert(0, "llama3.1")
    ai1_type_entry.grid(row=0, column=3)

    ai2_type_entry = tk.Entry(name_frame)
    ai2_type_entry.insert(0, "llama3.1")
    ai2_type_entry.grid(row=1, column=3)

    for prompt_name, prompt_text in preset_prompts.items():
        tk.Button(
            root,
            text=prompt_name,
            command=lambda pn=prompt_name: start_conversation_wrapper(
                root, pn, ai1_name_entry.get(), ai2_name_entry.get()
            )
        ).pack(pady=5)

    custom_prompt_entry = tk.Entry(root, width=50)
    custom_prompt_entry.pack(pady=5)

    tk.Button(
        root,
        text="Custom Prompt",
        command=lambda: start_conversation_wrapper(
            root,
            custom_prompt_entry.get(),
            ai1_name_entry.get(),
            ai2_name_entry.get()
        )
    ).pack(pady=5)

    root.mainloop()


def start_conversation_wrapper(root, prompt, ai1_name, ai2_name):
    global models
    global ai1_type_entry, ai2_type_entry

    models[0] = str(ai1_type_entry.get())
    models[1] = str(ai2_type_entry.get())

    root.destroy()
    start_conversation(prompt, ai1_name, ai2_name)


if __name__ == "__main__":
    create_gui()