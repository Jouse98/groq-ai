import tkinter as tk
from tkinter import ttk
from groq import Groq
import os
import re
import keyboard
import subprocess
import threading
import sys
import json
from datetime import datetime
import sqlite3
import hashlib
import ast
import io
from contextlib import redirect_stdout, redirect_stderr

class AIAssistant:
    def __init__(self):
        # Main window configuration
        self.window = tk.Tk()
        self.window.title("AI")
        self.window.geometry("600x600")
        
        # Database configuration
        self.db_file = "assistant_data.db"
        self.init_database()
        
        # Groq API client initialization
        self.client = Groq(
            api_key='API_KEY_HERE'
        )
        
        # GUI Elements
        self.create_gui_elements()
        
        # Event bindings
        self.window.bind('<Return>', lambda event: self.process_input())
        
        # Initialize conversation history
        self.load_previous_conversations()
        
        # Display welcome message
        self.add_to_output("System: Enhanced AI Assistant initialized. How can I help you today?\n\n")

        # Add code execution environment
        self.code_globals = {}
        self.code_locals = {}

    def init_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            role TEXT,
            message TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_storage (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        conn.commit()
        conn.close()

    def create_gui_elements(self):
        # Create a notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(expand=True, fill="both")

        # Chat tab
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="Chat")

        self.input_box = tk.Text(self.chat_frame, width=60, height=3)
        self.input_box.pack(pady=10)
        
        self.send_button = tk.Button(self.chat_frame, text="Send", command=self.process_input)
        self.send_button.pack(pady=5)
        
        self.output_box = tk.Text(self.chat_frame, width=60, height=25)
        self.output_box.pack(pady=10)
        self.output_box.config(state=tk.DISABLED)

        # Data Management tab
        self.data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="Data Management")

        self.data_tree = ttk.Treeview(self.data_frame, columns=("Key", "Value"), show="headings")
        self.data_tree.heading("Key", text="Key")
        self.data_tree.heading("Value", text="Value")
        self.data_tree.pack(pady=10, expand=True, fill="both")

        self.refresh_button = tk.Button(self.data_frame, text="Refresh Data", command=self.refresh_data_view)
        self.refresh_button.pack(pady=5)

        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")

        self.api_key_label = tk.Label(self.settings_frame, text="Groq API Key:")
        self.api_key_label.pack(pady=5)
        self.api_key_entry = tk.Entry(self.settings_frame, width=50, show="*")
        self.api_key_entry.pack(pady=5)
        self.api_key_entry.insert(0, self.client.api_key)

        self.save_settings_button = tk.Button(self.settings_frame, text="Save Settings", command=self.save_settings)
        self.save_settings_button.pack(pady=5)

        # Code Execution tab
        self.code_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.code_frame, text="Code Execution")

        self.code_input = tk.Text(self.code_frame, width=60, height=10)
        self.code_input.pack(pady=10)

        self.execute_button = tk.Button(self.code_frame, text="Execute Code", command=self.execute_code)
        self.execute_button.pack(pady=5)

        self.code_output = tk.Text(self.code_frame, width=60, height=10)
        self.code_output.pack(pady=10)
        self.code_output.config(state=tk.DISABLED)

    def save_conversation(self, role, message, command=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO conversations (timestamp, role, message)
        VALUES (?, ?, ?)
        ''', (timestamp, role, message))
        conn.commit()
        conn.close()

    def load_previous_conversations(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT timestamp, role, message
        FROM conversations
        ORDER BY id DESC
        LIMIT 50
        ''')
        conversations = cursor.fetchall()
        conn.close()

        for conversation in reversed(conversations):
            timestamp, role, message = conversation
            self.add_to_output(f"[{timestamp}] {role}: {message}\n")
        self.add_to_output("\n--- Current Session ---\n\n")

    def handle_command(self, command, content):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if command == "store":
            try:
                key, value = content.split(":", 1)
                key = key.strip()
                value = value.strip()
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR REPLACE INTO data_storage (key, value)
                VALUES (?, ?)
                ''', (key, value))
                conn.commit()
                conn.close()
                self.refresh_data_view()
                return f"[{timestamp}] Stored information under key: {key}"
            except ValueError:
                return f"[{timestamp}] Invalid storage format. Use 'store key: value'"
        
        elif command == "retrieve":
            key = content.strip()
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM data_storage WHERE key = ?', (key,))
            result = cursor.fetchone()
            conn.close()
            if result:
                return f"[{timestamp}] {key}: {result[0]}"
            return f"[{timestamp}] No information found for key: {key}"
        
        elif command == "delete":
            key = content.strip()
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM data_storage WHERE key = ?', (key,))
            conn.commit()
            conn.close()
            self.refresh_data_view()
            return f"[{timestamp}] Deleted information for key: {key}"
        
        elif command == "clear_history":
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations')
            conn.commit()
            conn.close()
            return f"[{timestamp}] Conversation history cleared"
        
        return None

    def refresh_data_view(self):
        # Clear existing items
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)

        # Fetch and display data
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM data_storage')
        for row in cursor.fetchall():
            self.data_tree.insert("", "end", values=row)
        conn.close()

    def save_settings(self):
        new_api_key = self.api_key_entry.get()
        if new_api_key != self.client.api_key:
            self.client.api_key = new_api_key
            self.add_to_output("System: API key updated.\n\n")

    def execute_code(self):
        code = self.code_input.get("1.0", tk.END).strip()
        if not code:
            return

        # Clear previous output
        self.code_output.config(state=tk.NORMAL)
        self.code_output.delete("1.0", tk.END)
        self.code_output.config(state=tk.DISABLED)

        try:
            # Parse the code to check for potentially harmful operations
            tree = ast.parse(code)

            # Redirect stdout and stderr
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                exec(code, self.code_globals, self.code_locals)

            # Display the output
            self.code_output.config(state=tk.NORMAL)
            self.code_output.insert(tk.END, output.getvalue())
            self.code_output.config(state=tk.DISABLED)

        except Exception as e:
            self.code_output.config(state=tk.NORMAL)
            self.code_output.insert(tk.END, f"Error: {str(e)}")
            self.code_output.config(state=tk.DISABLED)

    def process_input(self):
        input_text = self.input_box.get("1.0", "end-1c").strip()
        if not input_text:
            return
        
        self.input_box.delete("1.0", tk.END)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.add_to_output(f"[{timestamp}] You: {input_text}\n")
        self.save_conversation("You", input_text)
        
        response = self.talk(input_text)
        
        if response.startswith("!"):
            command_parts = response[1:].split(" ", 1)
            command = command_parts[0]
            content = command_parts[1] if len(command_parts) > 1 else ""
            
            if command == "pip":
                threading.Thread(
                    target=self.install_package,
                    args=(content,),
                    daemon=True
                ).start()
                return
            
            if command == "git":
                threading.Thread(
                    target=self.install_package_git,
                    args=(content,),
                    daemon=True
                ).start()
                return
            
            if command == "execute_code":
                code = content.strip()
                self.code_input.delete("1.0", tk.END)
                self.code_input.insert(tk.END, code)
                self.execute_code()
                self.add_to_output(f"[{timestamp}] Assistant: I've executed the code. Please check the Code Execution tab for the output.\n\n")
                self.save_conversation("Assistant", "Code execution completed.")
                return
            
            command_response = self.handle_command(command, content)
            if command_response:
                self.add_to_output(f"{command_response}\n\n")
                self.save_conversation("Assistant", command_response.split("] ", 1)[1], command=True)
                return
        
        self.add_to_output(f"[{timestamp}] Assistant: {response}\n\n")
        self.save_conversation("Assistant", response)

    def talk(self, user_input):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM data_storage')
            data = dict(cursor.fetchall())
            conn.close()

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a helpful assistant with special commands:
                        - If user asks to remember/store something, respond with "!store key: value"
                        - If user asks to recall something, respond with "!retrieve key"
                        - If user asks to forget/delete something, respond with "!delete key"
                        - If user asks to install something with pip, respond only with "!pip package_name"
                        - If user asks to clone a git repository, respond only with "!git repository_url"
                        - If user asks to clear conversation history, respond with "!clear_history"
                        - If user asks to execute Python code, respond with "!execute_code" followed by the code on new lines
                        """ + str(data)
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                model="llama3-8b-8192"
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"

    def add_to_output(self, text):
        self.output_box.config(state=tk.NORMAL)
        self.output_box.insert(tk.END, text)
        self.output_box.see(tk.END)
        self.output_box.config(state=tk.DISABLED)

    def install_package(self, package_name):
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            returncode = process.wait()
            
            if returncode == 0:
                self.add_to_output("Package installation completed.\n\n")
            else:
                error = process.stderr.read()
                self.add_to_output("Package installation failed.\n\n")
                
        except Exception as e:
            self.add_to_output("Installation error occurred.\n\n")
    def install_package_git(self, repo_url):
        if not self.check_git_installed():
            self.add_to_output("Error: Git is not installed on your system.\n\n")
            return

        clone_dir = os.path.join(os.getcwd(), "git_repos")
        os.makedirs(clone_dir, exist_ok=True)

        try:
            os.chdir(clone_dir)
            process = subprocess.Popen(
                ['git', 'clone', repo_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                success_msg = f"Successfully cloned repository: {repo_url}\n"
                self.add_to_output(success_msg)
            else:
                error_msg = f"Failed to clone repository. Error: {stderr}\n"
                self.add_to_output(error_msg)
                
        except Exception as e:
            self.add_to_output(f"Error during Git clone: {str(e)}\n\n")
        finally:
            os.chdir(os.path.dirname(os.path.dirname(clone_dir)))

    def check_git_installed(self):
        try:
            subprocess.run(['git', '--version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

if __name__ == "__main__":
    app = AIAssistant()
    app.window.mainloop()
