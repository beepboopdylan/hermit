from dotenv import load_dotenv
load_dotenv()

import subprocess
from openai import OpenAI

client = OpenAI()
MODEL = "gpt-4o-mini"

def get_command(user_input: str) -> str:
    """
    
    Asking OpenAI to generate a shell command
    
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role":"system",
            "content":"You're a Linux shell expert. Convert user requests into shell commands. Reply with ONLY the command, no explanation, no markdown, no code blocks."
        }, {
            "role":"user",
            "content":user_input
        }],
        max_tokens=256
    )
    return response.choices[0].message.content.strip()

def execute_unsafe(command: str) -> str:
    """Execute command and return output."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout + result.stderr

def execute_sandboxed(command: str) -> str:
    full_command = [
        "unshare",
        "--mount",
        "--pid",
        "--fork",
        "--mount-proc",
        "sh", "-c", command
    ]
    
    result = subprocess.run(
        full_command,
        capture_output=True,
        text=True
    )
    return result.stdout + result.stderr

def main():
    import sys
    sandboxed = "--sandbox" in sys.argv

    if sandboxed:
        print(f"🔒 Sandboxed Agent (using {MODEL})")
        print("   Running in PID namespace isolation")
    else:
        print(f"🔓 Unsafe Agent (using {MODEL})")
        print("   No sandbox yet - be careful!")
    print("   Type 'exit' to quit\n")

    while True:
        user_input = input("> ")
        
        if user_input.lower() in ['exit', 'quit']:
            break

        command = get_command(user_input)
        print(f"Command: {command}") 

        confirm = input("Execute? [y/N] ")
        if confirm.lower() == 'y':
            if sandboxed:
                output = execute_sandboxed(command)
            else:
                output = execute_unsafe(command)
            print(output)

if __name__ == "__main__":
    main()


    

