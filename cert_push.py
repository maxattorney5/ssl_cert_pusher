import paramiko
import os

# Configuration
SOURCE_CERT = "test.crt"
SOURCE_KEY = "test.key"
REMOTE_HOST = "192.168.221.163"
REMOTE_USER = "ubuntu"
REMOTE_PATH = "/home/ubuntu/"  # Where the certs will land initially
KEY_FILE = os.path.expanduser("~/.ssh/id_rsa_automation")


def push_certificates():
    try:
        # 1. Establish the SSH Client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 2. Connect using the automation key
        print(f"Connecting to Taiwan Server ({REMOTE_HOST})...")
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, key_filename=KEY_FILE)

        # 3. Use SFTP to push the files
        sftp = ssh.open_sftp()
        print("Pushing test.crt...")
        sftp.put(SOURCE_CERT, REMOTE_PATH + "test.crt")
        print("Pushing test.key...")
        sftp.put(SOURCE_KEY, REMOTE_PATH + "test.key")

        sftp.close()

        # 4. Verification (The 'Engineer' touch)
        stdin, stdout, stderr = ssh.exec_command(f"ls -l {REMOTE_PATH}test.*")
        print("\nVerification on Taiwan Server:")
        print(stdout.read().decode())

        ssh.close()
        print("Successfully synchronized certificates.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    push_certificates()