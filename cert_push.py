import paramiko
import os
import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Configuration
SOURCE_CERT = "test.crt"
SOURCE_KEY = "test.key"
REMOTE_HOST = "192.168.221.163"
REMOTE_USER = "ubuntu"
REMOTE_PATH = "/home/ubuntu/"  # Where the certs will land initially
KEY_FILE = "/home/kali/.ssh/id_rsa_automation"


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
        # Tell Nginx to reload the new configuration
        print("Reloading Nginx in Taiwan...")
        # Use 'reload' instead of 'restart' to avoid dropping active connections
        ssh.exec_command("sudo systemctl reload nginx")
        print("Pushing test.key...")
        sftp.put(SOURCE_KEY, REMOTE_PATH + "test.key")
        # Tell Nginx to reload the new configuration
        print("Reloading Nginx in Taiwan...")
        # Use 'reload' instead of 'restart' to avoid dropping active connections
        ssh.exec_command("sudo systemctl reload nginx")

        sftp.close()

        # 4. Verification (The 'Engineer' touch)
        stdin, stdout, stderr = ssh.exec_command(f"ls -l {REMOTE_PATH}test.*")
        print("\nVerification on Taiwan Server:")
        print(stdout.read().decode())

        ssh.close()
        print("Successfully synchronized certificates.")

    except Exception as e:
        print(f"Error: {e}")


def check_remote_expiry(ssh, cert_path):
    # Retrieve the cert content from the remote Ubuntu server
    stdin, stdout, stderr = ssh.exec_command(f"cat {cert_path}")
    cert_data = stdout.read()

    if not cert_data:
        print("No certificate found in Taiwan. Proceeding with initial push.")
        return True  # Needs renewal/push

    # Parse the certificate
    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    expiry_date = cert.not_valid_after

    # Old logic: days_left < 30
    #days_left = (expiry_date - datetime.datetime.now()).days
    #print(f"Taiwan Certificate expires in: {days_left} days.")
    #return days_left < 30  # Returns True if renewal is needed (e.g., < 30 days left)

    # New logic: minutes_left < 45 (to trigger a renewal since we only have 30 mins)
    minutes_left = (expiry_date - datetime.datetime.now()).total_seconds() / 60
    print(f"Taiwan Certificate expires in: {minutes_left:.2f} minutes.")
    return minutes_left < 45

if __name__ == "__main__":
    push_certificates()