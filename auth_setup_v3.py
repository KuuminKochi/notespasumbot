import pty
import os
import time
import select

password = "-af29426101"
pub_key_path = "/home/kuumin/.ssh/notespasumbot_deploy.pub"

with open(pub_key_path, "r") as f:
    pub_key_content = f.read().strip()

# Command to run on server to install key
remote_cmd = f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{pub_key_content}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo 'KEY_INSTALLED_SUCCESS'"

# SSH command - Force password auth
cmd = f'ssh -o PubkeyAuthentication=no -o StrictHostKeyChecking=no root@152.42.245.71 "{remote_cmd}"'

print(f"Running: {cmd}")
pid, fd = pty.fork()

if pid == 0:
    os.execv("/bin/sh", ["sh", "-c", cmd])
else:
    output = b""
    while True:
        r, _, _ = select.select([fd], [], [], 3)
        if not r:
            break
        try:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            output += chunk
            text = chunk.decode(errors="ignore")
            print(f"Read: {text}", end="")

            if "password:" in text.lower():
                print("\n>>> Sending password...")
                os.write(fd, (password + "\n").encode())
                time.sleep(1)
        except OSError:
            break

    print("\nDone.")
