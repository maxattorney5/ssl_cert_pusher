import paramiko
import os
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import subprocess
from datetime import datetime, timedelta, timezone
import ssl
import hashlib

# Configuration
SOURCE_CERT = "test.crt"
SOURCE_KEY = "test.key"
REMOTE_HOST = "192.168.221.163"
REMOTE_USER = "ubuntu"
REMOTE_PATH = "/home/ubuntu/"  # Where the certs will land initially
KEY_FILE = "/home/kali/.ssh/id_rsa_automation"


def push_certificates():
    # 1. Configuration (ensure these are correct)
    REMOTE_CERT_PATH = f"{REMOTE_PATH}test.crt"

    try:
        # 2. Connect to Taiwan
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, key_filename=KEY_FILE)

        # 3. Check if we actually NEED to renew
        needs_renewal = check_remote_expiry(ssh, REMOTE_CERT_PATH)

        if needs_renewal:
            print("Action Required: Certificate is expiring or missing.")

            # 4. Generate the new cert locally on Kali
            generate_new_cert()

            # 5. Push the new files via SFTP
            sftp = ssh.open_sftp()
            print("Pushing updated test.crt...")
            sftp.put(SOURCE_CERT, REMOTE_PATH + "test.crt")
            print("Pushing updated test.key...")
            sftp.put(SOURCE_KEY, REMOTE_PATH + "test.key")
            sftp.close()

            # 6. Reload the webserver to apply changes
            print("Reloading Nginx in Taiwan...")
            ssh.exec_command("sudo systemctl restart nginx")
            # use this line instead if command permission on server is not allowed, change param "YOUR_PASSWORD" to the actual password of your target server
            # ssh.exec_command("echo 'YOUR_PASSWORD' | sudo -S systemctl restart nginx")

            # We give Nginx 2 seconds to finish restarting before we check
            import time
            time.sleep(2)

            live_fp = verify_live_sync(REMOTE_HOST)

            local_cmd = f"openssl x509 -in {SOURCE_CERT} -noout -sha256 -fingerprint"
            local_fp_raw = subprocess.check_output(local_cmd, shell=True).decode()
            local_fp = local_fp_raw.split('=')[1].strip()

            print(f"Local Source: {local_fp}")
            print(f"Live Server:  {live_fp}")

            if live_fp == local_fp:
                print("✅ SUCCESS: Live server is now using the new certificate!")
            else:
                print("❌ CRITICAL ERROR: Live server is still using an OLD certificate (Desync).")

            print("Full renewal cycle complete.")
        else:
            print("Status: Taiwan certificate is still valid. No action taken.")

        ssh.close()

    except Exception as e:
        print(f"Pipeline Error: {e}")


def check_remote_expiry(ssh, cert_path):
    stdin, stdout, stderr = ssh.exec_command(f"cat {cert_path}")
    cert_data = stdout.read()

    if not cert_data:
        return True

    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    expiry_date = cert.not_valid_after_utc
    now_utc = datetime.now(timezone.utc)

    # Old logic: days_left < 30
    #days_left = (expiry_date - datetime.datetime.now()).days
    #print(f"Taiwan Certificate expires in: {days_left} days.")
    #return days_left < 30  # Returns True if renewal is needed (e.g., < 30 days left)

    # New logic: minutes_left < 45 (to trigger a renewal since we only have 30 mins)

    minutes_left = (expiry_date - now_utc).total_seconds() / 60
    print(f"Taiwan Certificate expires in: {minutes_left:.2f} minutes.")
    return minutes_left < 45


def generate_new_cert():
    print("Generating new 30-minute certificate locally...")
    # Fix: Use timezone.utc to avoid the offset/negative minute bug
    now_utc = datetime.now(timezone.utc)
    expiry_ts = (now_utc + timedelta(minutes=30)).strftime("%Y%m%d%H%M%SZ")

    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:4096",
        "-keyout", "test.key", "-out", "test.crt",
        "-nodes", "-days", "1",
        "-subj", "/C=SG/ST=Singapore/L=Singapore/O=Lab/CN=test.local",
        "-not_after", expiry_ts
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("New certificate generated successfully.")
    else:
        print(f"Error generating cert: {result.stderr}")

def verify_live_sync(ip):
    print(f"Verifying live synchronization for {ip}...")
    try:
        # Connect to the live port and grab the certificate
        context = ssl._create_unverified_context()
        cert_pem = ssl.get_server_certificate((ip, 443), ssl_context=context)
        cert_der = ssl.pem_to_der_certificate(cert_pem)
        live_fingerprint = hashlib.sha256(cert_der).hexdigest().upper()

        # Format it with colons like OpenSSL does: 1A:2B:3C...
        formatted_fp = ":".join(live_fingerprint[i:i + 2] for i in range(0, len(live_fingerprint), 2))
        print(f"Live Fingerprint: {formatted_fp}")
        return formatted_fp
    except Exception as e:
        print(f"Verification failed: {e}")
        return None

if __name__ == "__main__":
    push_certificates()